"""实时数据流模拟 + 并发稳定性压测脚本（数据中心资源智能管理系统）
用途: 在接近真实生产的实时数据负载下验证系统稳定性与并发处理能力。
安全: 默认直接连现有后端会污染真实库; 推荐 --spawn-server 使用隔离一次性实例。
依赖: 仅 requests (项目 venv 已内置). CPU/内存采样不依赖 psutil.
"""
from __future__ import annotations
import argparse, csv, json, math, os, random, socket, subprocess, sys
import threading, time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
try:
    import requests
except ImportError:
    print("[错误] 缺少 requests"); raise SystemExit(2)

RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_MARK = f"gen_loadtest_{RUN_ID}"
LEVELS = ["general", "serious", "emergency"]
SENSOR_TYPES = {"temperature": ("C", 18, 40), "humidity": ("%", 30, 80), "power": ("kW", 0, 120)}

DEFAULT_MIX = {
    "sensor_data_write": 0.34, "sensor_update": 0.10, "alert_create": 0.06,
    "work_order_create": 0.02, "sensor_poll": 0.16, "sensor_data_read": 0.10,
    "alert_poll": 0.08, "dashboard_poll": 0.08, "insight_poll": 0.04,
}
OP_REQUIRED_PERM = {
    "sensor_data_write": "monitor:handle_alert", "sensor_update": "device:edit",
    "alert_create": "monitor:handle_alert", "work_order_create": "work:create",
    "sensor_poll": "device:view", "sensor_data_read": "device:view",
    "alert_poll": "monitor:view_alerts", "dashboard_poll": "monitor:view_dashboard",
    "insight_poll": "monitor:view_dashboard",
}

# ---------------------------------------------------------------------------
# 系统指标采样(不依赖 psutil)
# ---------------------------------------------------------------------------
class SystemMonitor:
    def __init__(self, pid=None, auto_probe=False):
        self.pid = pid or 0
        self.auto_probe = auto_probe
        self.cpu_percent = None
        self.mem_rss_mb = None
        self.cores = max(os.cpu_count() or 1, 1)
        self._last = None
        if self.auto_probe:
            self.probe_pid()

    def probe_pid(self):
        candidates = []
        try:
            if os.name == "nt":
                ps = ("Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' "
                      "-and $_.CommandLine -like '*uvicorn*app.main*' } | Select-Object -ExpandProperty ProcessId")
                out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                                     capture_output=True, text=True, timeout=15)
                for tok in (out.stdout or "").split():
                    tok = tok.strip()
                    if tok.isdigit():
                        candidates.append(int(tok))
        except Exception:
            candidates = []
        best_pid, best_ws = None, -1
        for pid in candidates:
            ws = self._working_set(pid)
            if ws is not None and ws > best_ws:
                best_ws, best_pid = ws, pid
        if best_pid:
            self.pid = best_pid

    def _working_set(self, pid):
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            h = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
            if not h:
                return None
            try:
                class PMC(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
                pmc = PMC()
                pmc.cb = ctypes.sizeof(PMC)
                if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                    return pmc.WorkingSetSize
            finally:
                kernel32.CloseHandle(h)
        except Exception:
            return None
    def sample(self):
        if not self.pid:
            return self
        if os.name == "nt":
            self._sample_windows()
        else:
            self._sample_linux()
        return self

    def _sample_windows(self):
        try:
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.windll.kernel32
            psapi = ctypes.windll.psapi
            handle = kernel32.OpenProcess(0x0400 | 0x0010, False, self.pid)
            if not handle:
                return
            try:
                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]
                ctime, etime, ktime, utime = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                now = time.time()
                if kernel32.GetProcessTimes(handle, ctypes.byref(ctime), ctypes.byref(etime),
                                            ctypes.byref(ktime), ctypes.byref(utime)):
                    def to_ticks(ft):
                        return (ft.dwHighDateTime << 32) | ft.dwLowDateTime
                    total = to_ticks(ktime) + to_ticks(utime)
                    if self._last:
                        dticks, dtime = self._last
                        dt = max(now - dtime, 1e-6)
                        pct = ((total - dticks) / 1e7) / dt / self.cores * 100.0
                        self.cpu_percent = max(0.0, min(pct, 100.0 * self.cores))
                    self._last = (total, now)
                class PMC(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
                pmc = PMC()
                pmc.cb = ctypes.sizeof(PMC)
                if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
                    self.mem_rss_mb = pmc.WorkingSetSize / (1024 * 1024)
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            pass

    def _sample_linux(self):
        try:
            with open(f"/proc/{self.pid}/stat") as f:
                parts = f.read().split()
            total = int(parts[13]) + int(parts[14])
            now = time.time()
            if self._last:
                dticks, dtime = self._last
                dt = max(now - dtime, 1e-6)
                self.cpu_percent = max(0.0, min(((total - dticks) / 100.0) / dt / self.cores * 100.0, 100.0 * self.cores))
            self._last = (total, now)
            with open(f"/proc/{self.pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        self.mem_rss_mb = int(line.split()[1]) / 1024.0
                        break
        except Exception:
            pass

# ---------------------------------------------------------------------------
# 数据生成器
# ---------------------------------------------------------------------------
class DataGenerator:
    def __init__(self, scale=1.0):
        self.scale = max(1.0, float(scale))
        self.sensors = []
        self._values = {}
        self.device_ids = []
        self._loaded = False

    def load_meta(self, get, base_url, headers):
        if self._loaded:
            return
        try:
            r = get(f"{base_url}/sensors/all", headers=headers, timeout=10)
            if r.status_code == 200:
                self.sensors = r.json()
        except Exception:
            self.sensors = []
        if not self.sensors:
            self.sensors = [{"id": i, "sensor_type": "temperature",
                             "threshold_min": 18, "threshold_max": 40} for i in range(1, 21)]
        for s in self.sensors:
            sid = int(s.get("id"))
            lo = float(s.get("threshold_min") or 18)
            hi = float(s.get("threshold_max") or 40)
            self._values[sid] = (lo + hi) / 2 + random.uniform(-(hi - lo) / 6, (hi - lo) / 6)
        self._loaded = True

    def sensor_ids(self):
        return [int(s["id"]) for s in self.sensors]

    def pick(self):
        if self.sensors:
            return self.sensors[random.randrange(len(self.sensors))]
        return {"id": 1, "sensor_type": "temperature", "threshold_min": 18, "threshold_max": 40}

    def next_value(self, sensor):
        sid = int(sensor.get("id"))
        lo = float(sensor.get("threshold_min") or 18)
        hi = float(sensor.get("threshold_max") or 40)
        cur = self._values.get(sid, (lo + hi) / 2)
        step = (hi - lo) / 8
        drift = random.uniform(-step, step)
        if random.random() < 0.05:
            drift = random.uniform((hi - lo) / 3, (hi - lo) / 2)
        nv = cur + drift
        if random.random() < 0.12:
            nv = hi + random.uniform(0, (hi - lo) / 5)
        elif random.random() < 0.08:
            nv = lo - random.uniform(0, (hi - lo) / 5)
        nv = max(lo - (hi - lo), min(hi + (hi - lo), nv))
        self._values[sid] = nv
        return round(nv, 2), hi


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------
def discover_captcha_enabled(base_url):
    try:
        r = requests.get(f"{base_url}/auth/captcha", timeout=8)
        if r.status_code == 200:
            return r.json().get("captcha_id") != "disabled"
    except Exception:
        pass
    return False


def acquire_token(base_url, username, password):
    if discover_captcha_enabled(base_url):
        raise RuntimeError(
            "登录接口启用了验证码(ENABLE_CAPTCHA=true)。\n"
            "请任选其一:\n"
            "  1) 推荐: --spawn-server 自动启动验证码关闭的独立实例;\n"
            "  2) 传入已签发 token: --token <JWT>;\n"
            "  3) 在测试实例上临时设置 ENABLE_CAPTCHA=false 后重启后端。")
    r = requests.post(f"{base_url}/auth/login",
                      json={"username": username, "password": password}, timeout=15)
    if r.status_code == 200:
        return r.json()["access_token"]
    raise RuntimeError(f"登录失败 HTTP {r.status_code}: {r.text[:300]}")

# ---------------------------------------------------------------------------
# 并发负载引擎
# ---------------------------------------------------------------------------
class LoadEngine:
    def __init__(self, base_url, token, mix, scale, max_error_rate=0.05, max_p99_ms=1000.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.mix = mix
        self.scale = scale
        self.max_error_rate = max_error_rate
        self.max_p99_ms = max_p99_ms
        self.stop = threading.Event()
        self._lock = threading.Lock()
        self.sent = 0
        self.ok = 0
        self.timeouts = 0
        self.latencies = deque(maxlen=200000)
        self.status_counter = defaultdict(int)
        self.cat_counter = defaultdict(int)
        self.cat_lat = defaultdict(lambda: deque(maxlen=200000))
        self.cat_errors = defaultdict(int)
        self.gen = DataGenerator(scale)
        self._paths = []
        self._sessions = {}
        self._sess_lock = threading.Lock()
        self.out = {}

    def _get_session(self, wid):
        with self._sess_lock:
            s = self._sessions.get(wid)
            if s is None:
                s = requests.Session()
                s.headers.update({"Authorization": f"Bearer {self.token}",
                                  "Content-Type": "application/json"})
                self._sessions[wid] = s
            return s

    def _record(self, category, ok, status, latency_ms, timeout):
        with self._lock:
            self.sent += 1
            self.latencies.append(latency_ms)
            self.cat_counter[category] += 1
            self.cat_lat[category].append(latency_ms)
            if timeout:
                self.timeouts += 1
                self.cat_errors[category] += 1
                self.status_counter["timeout"] += 1
                return
            self.status_counter[status] += 1
            if ok:
                self.ok += 1
            else:
                self.cat_errors[category] += 1

    def _build_paths(self):
        g = self.gen
        paths = []
        for _ in range(40):
            s = g.pick()
            sid = int(s["id"])
            def mk_data(s=s, sid=sid):
                v, _ = g.next_value(s)
                return f"{self.base_url}/sensors/{sid}/data", {"params": {"value": v}}
            paths.append(("sensor_data_write", "POST", mk_data))
            def mk_read(sid=sid):
                return f"{self.base_url}/sensors/{sid}/data", {"params": {"limit": random.choice([10, 20, 50])}}
            paths.append(("sensor_data_read", "GET", mk_read))
            def mk_update(s=s, sid=sid):
                v, _ = g.next_value(s)
                unit = SENSOR_TYPES.get(s.get("sensor_type"), ("", 0, 100))[0]
                body = {"current_value": {"value": v, "unit": unit},
                        "status": "online", "last_update_time": datetime.now().isoformat()}
                return f"{self.base_url}/sensors/{sid}", {"json": body}
            paths.append(("sensor_update", "PUT", mk_update))

        def mk_alert(seq=[0]):
            seq[0] += 1
            body = {"target_type": random.choice(["sensor", "device", "rack"]),
                    "target_id": str(random.randint(1, 10000)),
                    "title": f"{RUN_MARK} alert {seq[0]}",
                    "description": f"{RUN_MARK} 稳定性测试告警 {datetime.now().isoformat()}",
                    "level": random.choice(LEVELS), "source": "loadtest"}
            return f"{self.base_url}/alerts", {"json": body}
        paths.append(("alert_create", "POST", mk_alert))

        def mk_wo(seq=[0]):
            seq[0] += 1
            body = {"title": f"{RUN_MARK} order {seq[0]}",
                    "description": f"{RUN_MARK} 稳定性测试工单",
            "priority": random.choice(["low", "normal", "high", "urgent"]),
                    "device_id": g.device_ids[0] if g.device_ids else None,
                    "facility_id": None, "assignee_id": None,
                    "estimated_hours": random.randint(1, 12),
                    "plan_date": (datetime.now() + timedelta(days=random.randint(1, 5))).date().isoformat()}
            return f"{self.base_url}/work-orders", {"json": body}
        paths.append(("work_order_create", "POST", mk_wo))

        def poll(rel, params=None):
            def mk():
                return f"{self.base_url}{rel}", {"params": params if params is not None else {}}
            return mk

        paths.append(("sensor_poll", "GET", poll("/sensors", {"page": 1, "page_size": 20})))
        paths.append(("sensor_poll", "GET", poll("/sensors/all")))
        paths.append(("alert_poll", "GET", poll("/alerts", {"page": 1, "page_size": 20})))
        paths.append(("dashboard_poll", "GET", poll("/dashboard/activities", {"limit": 12})))
        paths.append(("insight_poll", "GET", poll("/insight/capacity", {"days": 7})));
        # 注: /sensors/retention-status 被 /{sensor_id} 路由遮蔽(后端路由顺序缺陷)返回 422, 故不纳入混合负载
        self._paths = paths

    def _dispatch(self, wid):
        cats = list(self.mix.keys())
        weights = [self.mix[c] for c in cats]
        chosen = random.choices(cats, weights=weights, k=1)[0]
        cand = [p for p in self._paths if p[0] == chosen] or self._paths
        cat, method, mk = random.choice(cand)
        url, kwargs = mk()
        sess = self._get_session(wid)
        t0 = time.perf_counter()
        ok = False
        status = 0
        timeout = False
        try:
            if method == "GET":
                r = sess.get(url, timeout=10, **kwargs)
            elif method == "PUT":
                r = sess.put(url, timeout=10, **kwargs)
            else:
                r = sess.post(url, timeout=10, **kwargs)
            status = r.status_code
            ok = 200 <= status < 300
        except requests.exceptions.Timeout:
            timeout = True
        except Exception:
            status = -1
        elapsed = (time.perf_counter() - t0) * 1000.0
        self._record(cat, ok, status, round(elapsed, 1), timeout)

    def _worker(self, wid, interval, jitter):
        time.sleep(random.uniform(0, 0.8))
        nxt = time.perf_counter()
        while not self.stop.is_set():
            self._dispatch(wid)
            if interval > 0:
                nxt += interval * random.uniform(1 - jitter, 1 + jitter)
                wait = nxt - time.perf_counter()
                if wait > 0:
                    self.stop.wait(wait)
                else:
                    nxt = time.perf_counter()

    def run(self, duration, users, rps, warmup):
        self.gen.load_meta(requests.get, self.base_url,
                           {"Authorization": f"Bearer {self.token}"})
        self._build_paths()
        self.out["start"] = time.time()
        interval = (users / rps) if (rps and users) else 0.0
        with ThreadPoolExecutor(max_workers=max(users, 1)) as ex:
            futs = [ex.submit(self._worker, w, interval, 0.3) for w in range(users)]
            deadline = time.time() + warmup
            while time.time() < deadline and not self.stop.is_set():
                time.sleep(0.1)
            self.out["measure_start"] = time.time()
            end = self.out["measure_start"] + duration
            while time.time() < end and not self.stop.is_set():
                time.sleep(0.1)
            self.stop.set()
            self.out["end"] = time.time()
            for f in futs:
                try:
                    f.result(timeout=5)
                except Exception:
                    pass
        return self.out

    def snapshot(self):
        with self._lock:
            n = max(self.sent, 1)
            lat = list(self.latencies)
            ms = self.out.get("measure_start")
            elapsed = (self.out.get("end") or time.time()) - ms if ms else 0.0
            cat_stats = {}
            for c in self.mix:
                cl = list(self.cat_lat[c])
                cat_stats[c] = (self.cat_counter[c], self.cat_errors[c],
                                _percentile(cl, 90) if cl else 0.0)
            return {"sent": self.sent, "ok": self.ok, "timeouts": self.timeouts,
                    "error_rate": (self.sent - self.ok) / n,
                    "p50": _percentile(lat, 50), "p90": _percentile(lat, 90),
                    "p95": _percentile(lat, 95), "p99": _percentile(lat, 99),
                    "status": dict(self.status_counter), "cat_stats": cat_stats,
                    "throughput_rate": (self.sent / elapsed) if elapsed >= 0.5 else 0.0}

    def close(self):
        self.stop.set()
        for s in self._sessions.values():
            try:
                s.close()
            except Exception:
                pass


def _percentile(data, p):
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return s[int(k)]
    return s[f] * (c - k) + s[c] * (k - f)

# ---------------------------------------------------------------------------
# 一次性隔离后端
# ---------------------------------------------------------------------------
def pick_free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]




RESET_ADMIN_PASSWORD = "admin@123456"


def _reset_admin_password(db_path):
    """在隔离临时库副本上，把 admin 密码重置为已知值，保证测试可登录。"""
    try:
        from passlib.context import CryptContext
        ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed = ctx.hash(RESET_ADMIN_PASSWORD)
    except Exception:
        hashed = None
    import sqlite3
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        tab = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if not tab:
            return
        if hashed:
            c.execute("UPDATE users SET hashed_password=?, is_active=1, is_super_admin=1, must_change_password=0, login_attempts=0, locked_until=NULL WHERE username=?",
                      (hashed, "admin"))
            if c.rowcount == 0:
                c.execute("INSERT INTO users (username, hashed_password, is_active, is_super_admin, must_change_password, created_at, updated_at) "
                          "VALUES (?,?,1,1,0,datetime('now','localtime'),datetime('now','localtime'))",
                          ("admin", hashed))
        conn.commit()
    finally:
        conn.close()


def spawn_server(backend_dir, python, db_dir, seed_source=None, fresh=False):
    db_dir = Path(db_dir).resolve()
    db_path = db_dir / f"loadtest_{RUN_ID}.db"
    port = pick_free_port()
    env = os.environ.copy()
    env["ENABLE_CAPTCHA"] = "false"
    env["ENFORCE_SECURITY"] = "false"
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    env["DATABASE_URL_SYNC"] = f"sqlite:///{db_path.as_posix()}"
    env["DEBUG"] = "false"
    if (not fresh) and seed_source and os.path.exists(seed_source):
        try:
            import sqlite3
            _src = sqlite3.connect(seed_source)
            _dst = sqlite3.connect(str(db_path))
            with _dst:
                _src.backup(_dst)
            _src.close(); _dst.close()
            print(f"[spawn] 已从 {seed_source} 备份复制真实数据到隔离临时库 (WAL 安全)")
            _reset_admin_password(db_path)
            print("[spawn] admin 密码已重置为已知测试值, 便于自动登录")
        except Exception as e:
            print(f"[spawn] 备份复制失败 {e}, 退回普通文件拷贝")
            import shutil
            shutil.copy2(seed_source, db_path)
            _reset_admin_password(db_path)
    else:
        _reset_admin_password(db_path)
    log_path = db_dir / f"loadtest_server_{RUN_ID}.log"
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        cwd=str(backend_dir), env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return proc, port, db_path
def wait_ready(base_url, timeout=90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{base_url}/auth/captcha", timeout=3)
            return True
        except Exception:
            time.sleep(1.0)
    return False


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def build_report(engine, sysmon, args, cpu_series, mem_series, baseline=None):
    snap = engine.snapshot()
    error_rate = snap["error_rate"]
    p99 = snap["p99"]
    passed = error_rate <= engine.max_error_rate and p99 <= engine.max_p99_ms
    cpu_v = [c for c in cpu_series if c is not None]
    mem_v = [m for m in mem_series if m is not None]
    report = {
        "run_id": RUN_ID, "mark": RUN_MARK,
        "config": {"base_url": args.base_url, "users": args.users,
                   "frequency": args.frequency, "scale": args.scale,
                   "duration": args.duration,
                   "instance": "隔离一次性(--spawn-server)" if args.spawn_server else "现有后端"},
        "totals": {"sent": snap["sent"], "ok": snap["ok"], "timeouts": snap["timeouts"],
                   "error_rate": error_rate, "throughput_ops_s": snap["throughput_rate"]},
        "latency": {"p50": snap["p50"], "p90": snap["p90"], "p95": snap["p95"], "p99": snap["p99"]},
        "status_dist": snap["status"],
        "cat_stats": [{"category": c, "count": v[0], "errors": v[1], "p90": v[2]}
                      for c, v in snap["cat_stats"].items()],
        "system": {"cpu_min": _f(min(cpu_v)) if cpu_v else None,
                   "cpu_avg": _f(sum(cpu_v) / len(cpu_v)) if cpu_v else None,
                   "cpu_max": _f(max(cpu_v)) if cpu_v else None,
                   "mem_min_mb": _f(min(mem_v)) if mem_v else None,
                   "mem_avg_mb": _f(sum(mem_v) / len(mem_v)) if mem_v else None,
                   "mem_max_mb": _f(max(mem_v)) if mem_v else None},
        "verdict": {"passed": passed, "error_rate": error_rate,
                    "max_error_rate": engine.max_error_rate, "p99": p99,
                    "max_p99": engine.max_p99_ms,
                    "reason": ("通过" if passed else
                               ("错误率 %.2f%% 超阈值 %.2f%%" % (error_rate * 100, engine.max_error_rate * 100)
                                if error_rate > engine.max_error_rate else
                                "P99 %.0fms 超阈值 %.0fms" % (p99, engine.max_p99_ms)))},
    }
    if baseline:
        report["compare"] = compare_reports(baseline, report)
    return report


def _f(v):
    return round(v, 2) if v is not None else None


def compare_reports(base, cur):
    def pct(old, new):
        if old in (None, 0):
            return None
        return round((new - old) / old * 100.0, 1)
    return {"throughput_delta_pct": pct(base["totals"]["sent"], cur["totals"]["sent"]),
            "p50_delta_pct": pct(base["latency"]["p50"], cur["latency"]["p50"]),
            "p99_delta_pct": pct(base["latency"]["p99"], cur["latency"]["p99"]),
            "error_rate_delta_ppt": round((cur["totals"]["error_rate"] - base["totals"]["error_rate"]) * 100, 2)}


def write_csv(path, engine, cpu_series, mem_series, sample_times):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_s", "ops_since_start", "ok", "errors", "error_rate",
                    "p50_ms", "p90_ms", "p95_ms", "p99_ms", "cpu_pct", "mem_mb"])
        base_t = engine.out.get("measure_start", time.time())
        for i, t in enumerate(sample_times):
            lat = list(engine.latencies)
            w.writerow([round(t - base_t, 1), engine.sent, engine.ok,
                        engine.sent - engine.ok,
                        round((engine.sent - engine.ok) / max(engine.sent, 1), 4),
                        _percentile(lat, 50) if lat else 0,
                        _percentile(lat, 90) if lat else 0,
                        _percentile(lat, 95) if lat else 0,
                        _percentile(lat, 99) if lat else 0,
                        cpu_series[i] if i < len(cpu_series) else "",
                        mem_series[i] if i < len(mem_series) else ""])

def write_markdown(path, r):
    L = []
    L.append("# 稳定性测试报告")
    L.append("")
    L.append(f"- 运行标识: `{r['run_id']}` (数据标记: `{r['mark']}`)")
    L.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    L.append(f"- 测试目标: `{r['config']['base_url']}`")
    L.append(f"- 实例来源: {r['config']['instance']}")
    L.append("")
    L.append("## 1. 测试配置")
    L.append("")
    L.append("| 参数 | 值 |")
    L.append("|---|---|")
    for k, v in r["config"].items():
        L.append(f"| {k} | {v} |")
    L.append("")
    L.append("## 2. 总体结果")
    L.append("")
    t = r["totals"]
    L.append(f"- 请求总数: {t['sent']}, 成功: {t['ok']}, 超时: {t['timeouts']}")
    L.append(f"- 总错误率: {t['error_rate']*100:.2f}%")
    L.append(f"- 有效吞吐: {t['throughput_ops_s']:.2f} ops/s")
    L.append("")
    L.append("### 响应时间(ms)")
    L.append("")
    L.append("| p50 | p90 | p95 | p99 |")
    L.append("|---|---|---|---|")
    lat = r["latency"]
    L.append(f"| {lat['p50']:.1f} | {lat['p90']:.1f} | {lat['p95']:.1f} | {lat['p99']:.1f} |")
    L.append("")
    L.append("### HTTP 状态分布")
    L.append("")
    L.append("| 状态码 | 次数 | 占比 |")
    L.append("|---|---|---|")
    status = r["status_dist"]
    total = max(sum(status.values()), 1)
    for code in sorted(status, key=lambda c: -status[c]):
        L.append(f"| {code} | {status[code]} | {status[code]/total*100:.2f}% |")
    L.append("")
    L.append("## 3. 分类明细")
    L.append("")
    L.append("| 操作 | 次数 | 错误 | 错误率 | P90(ms) | 需权限 |")
    L.append("|---|---|---|---|---|---|")
    for c in r["cat_stats"]:
        perm = OP_REQUIRED_PERM.get(c["category"], "-")
        L.append(f"| {c['category']} | {c['count']} | {c['errors']} | {c['errors']/max(c['count'],1)*100:.2f}% | {c['p90']:.1f} | {perm} |")
    L.append("")
    L.append("## 4. 系统资源")
    L.append("")
    L.append("| 指标 | 最小值 | 平均值 | 最大值 |")
    L.append("|---|---|---|---|")
    s = r["system"]
    L.append(f"| CPU % | {s['cpu_min']} | {s['cpu_avg']} | {s['cpu_max']} |")
    L.append(f"| 内存 MB | {s['mem_min_mb']} | {s['mem_avg_mb']} | {s['mem_max_mb']} |")
    L.append("")
    if r.get("compare"):
        L.append("## 5. 与基线对比")
        L.append("")
        L.append("| 指标 | 变化 |")
        L.append("|---|---|")
        c = r["compare"]
        L.append(f"| 吞吐 | {c['throughput_delta_pct']}% |" if c['throughput_delta_pct'] is not None else "| 吞吐 | - |")
        L.append(f"| P50 | {c['p50_delta_pct']}% |" if c['p50_delta_pct'] is not None else "| P50 | - |")
        L.append(f"| P99 | {c['p99_delta_pct']}% |" if c['p99_delta_pct'] is not None else "| P99 | - |")
        L.append(f"| 错误率 | {c['error_rate_delta_ppt']} 个百分点 |")
        L.append("")
    L.append("## 6. 稳定性判定")
    L.append("")
    v = r["verdict"]
    L.append(f"- **结论: {'通过 OK' if v['passed'] else '未通过 FAIL'}**")
    L.append(f"- 判定依据: 错误率 {v['error_rate']*100:.2f}% (阈值 {v['max_error_rate']*100:.2f}%), P99 {v['p99']:.0f}ms (阈值 {v['max_p99']:.0f}ms)")
    L.append(f"- 说明: {v['reason']}")
    L.append("")
    L.append("## 7. 异常统计")
    L.append("")
    L.append(f"- 超时请求数: {r['totals']['timeouts']}")
    L.append(f"- 5xx 错误数: {sum(x for k, x in status.items() if isinstance(k, int) and 500 <= k < 600)}")
    L.append(f"- 4xx 错误数: {sum(x for k, x in status.items() if isinstance(k, int) and 400 <= k < 500)}")
    L.append("")
    L.append("> 说明: 系统为 SQLite + 线程池架构, 无独立任务队列; 本报告以 503/超时/并发限制命中数及请求等待 as 积压代理指标.")
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))

# ---------------------------------------------------------------------------
# 清理(仅删除打标记录)
# ---------------------------------------------------------------------------
def safety_cleanup(db_url, mark, start_ts):
    try:
        import sqlite3
    except Exception:
        print("[提示] 无法清理: 缺少 sqlite3。")
        return
    path = db_url
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if db_url.startswith(prefix):
            path = db_url[len(prefix):]
            break
    if path.startswith("."):
        path = os.path.join(os.getcwd(), path.lstrip("./"))
    if not os.path.exists(path):
        print(f"[提示] 清理跳过: 找不到数据库 {path}")
        return
    conn = sqlite3.connect(path)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM alerts WHERE title LIKE ?", (f"%{mark}%",))
        alerts = c.rowcount
        c.execute("DELETE FROM work_orders WHERE title LIKE ?", (f"%{mark}%",))
        orders = c.rowcount
        rows_mark = 0
        try:
            c.execute("DELETE FROM sensor_data WHERE source_mark LIKE ?", (f"%{mark}%",))
            rows_mark = c.rowcount
        except Exception:
            pass
        conn.commit()
        print(f"[清理] 已删除 {alerts} 条告警, {orders} 条工单, {rows_mark} 条传感器数据 (标记 {mark})。")
    except Exception as e:
        conn.rollback()
        print(f"[警告] 清理失败: {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="数据中心资源智能管理系统 - 实时数据流/并发稳定性压测")
    p.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    p.add_argument("--users", type=int, default=10, help="模拟并发用户/客户端数")
    p.add_argument("--frequency", type=int, default=20, help="目标数据生成频率 ops/s")
    p.add_argument("--rps", type=float, default=None, help="目标吞吐(覆盖 --frequency)")
    p.add_argument("--scale", type=float, default=1.0, help="模拟规模系数")
    p.add_argument("--duration", type=int, default=60, help="稳定运行时长秒数")
    p.add_argument("--warmup", type=float, default=5.0, help="预热时长秒数")
    p.add_argument("--interval", type=float, default=0.5, help="系统指标采样间隔秒数")
    p.add_argument("--max-error-rate", type=float, default=0.05, help="错误率通过阈值")
    p.add_argument("--max-p99", type=float, default=1000.0, help="P99 延迟通过阈值 ms")
    p.add_argument("--token", default=None, help="预签发 JWT token")
    p.add_argument("--username", default="admin")
    p.add_argument("--password", default=None, help="登录密码(验证码关闭时可用)")
    p.add_argument("--pid", type=int, default=None, help="监控的后端进程 PID(0=自动探测)")
    p.add_argument("--spawn-server", action="store_true", help="自动启动一次性隔离后端")
    p.add_argument("--backend-dir", default=None, help="--spawn-server 后端目录")
    p.add_argument("--spawn-fresh", action="store_true", help="--spawn-server 使用全新空库(不复制真实数据)")
    p.add_argument("--seed-db", default="", help="--spawn-server 复制真实数据的来源库路径(默认 backend/data/managesys.db)")
    p.add_argument("--report", default=None, help="Markdown 报告输出路径")
    p.add_argument("--csv", default=None, help="CSV 采样输出路径")
    p.add_argument("--safety-cleanup", action="store_true", help="测试后清理本次产生的数据")
    p.add_argument("--baseline", default=None, help="基线报告 JSON 路径")
    p.add_argument("--db-url", default=None, help="--safety-cleanup 用数据库 URL")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    sysmon = SystemMonitor(pid=args.pid if args.pid else 0, auto_probe=(args.pid == 0))
    spawned = None
    try:
        base_url = args.base_url.rstrip("/")
        token = args.token
        password = args.password or "admin@123456"

        if args.spawn_server:
            backend_dir = Path(args.backend_dir or "backend").resolve()
            python = sys.executable
            db_dir = Path("data")
            seed_db = args.seed_db or str(backend_dir / "data" / "managesys.db")
            if not args.spawn_fresh and not os.path.exists(seed_db):
                print(f"[spawn] 未找到来源库 {seed_db}, 将用全新空库")
                seed_db = ""
            proc_obj, port, db_path = spawn_server(backend_dir, python, db_dir, seed_source=seed_db, fresh=args.spawn_fresh)
            base_url = f"http://127.0.0.1:{port}/api/v1"
            spawned = (proc_obj, base_url, db_path)
            sysmon.pid = proc_obj.pid   # 监控被测隔离实例而非生产进程
            sysmon.auto_probe = False
            print(f"[spawn] 已启动隔离后端 {base_url} (临时库 {db_path.name})")
            if not wait_ready(base_url):
                print("[错误] 隔离后端启动超时, 查看 data/loadtest_server_*.log")
                return 2
            if not token:
                print("[认证] 隔离实例登录…")
                token = acquire_token(base_url, args.username or "admin", password)
        else:
            if not token:
                print("[认证] 尝试登录获取 token…")
                token = acquire_token(base_url, args.username or "admin", password)


        args.base_url = base_url   # 报告/清理使用实际生效地址(如隔离实例端口)
        if not token:
            print("[错误] 未能获取 token")
            return 2
        print(f"[认证] token 前16位 {token[:16]}…")

        if sysmon.pid == 0:
            sysmon.probe_pid()
            if sysmon.pid:
                print(f"[监控] 自动定位后端进程 PID={sysmon.pid}")
            else:
                print("[监控] 未定位到后端进程, CPU/内存不可用 (可用 --pid <N>)")

        engine = LoadEngine(base_url, token, dict(DEFAULT_MIX), args.scale,
                            max_error_rate=args.max_error_rate, max_p99_ms=args.max_p99)

        cpu_series, mem_series, sample_times = [], [], []
        stop_mon = threading.Event()

        def sampler():
            while not stop_mon.is_set():
                sysmon.sample()
                cpu_series.append(sysmon.cpu_percent if sysmon.pid else None)
                mem_series.append(sysmon.mem_rss_mb if sysmon.pid else None)
                sample_times.append(time.time())
                snap = engine.snapshot()
                cp = f"{sysmon.cpu_percent:.1f}" if sysmon.cpu_percent is not None else "n/a"
                mp = f"{sysmon.mem_rss_mb:.0f}" if sysmon.mem_rss_mb is not None else "n/a"
                print(f"[{datetime.now().strftime('%H:%M:%S')}] sent={snap['sent']} "
                      f"ok={snap['ok']} err%={snap['error_rate']*100:.2f} "
                      f"p50={snap['p50']:.0f} p90={snap['p90']:.0f} p99={snap['p99']:.0f} "
                      f"cpu={cp}% mem={mp}MB tput={snap['throughput_rate']:.1f}ops/s")
                stop_mon.wait(args.interval)

        mon = threading.Thread(target=sampler, daemon=True)
        mon.start()

        rps = args.rps if args.rps is not None else float(args.frequency)
        engine.run(args.duration, args.users, rps, args.warmup)
        stop_mon.set()
        mon.join(timeout=5)

        baseline = None
        if args.baseline and os.path.exists(args.baseline):
            with open(args.baseline, encoding="utf-8") as f:
                baseline = json.load(f)
        report = build_report(engine, sysmon, args, cpu_series, mem_series, baseline)

        report_path = args.report or f"loadtest_report_{RUN_ID}.md"
        csv_path = args.csv or f"loadtest_samples_{RUN_ID}.csv"
        write_markdown(report_path, report)
        write_csv(csv_path, engine, cpu_series, mem_series, sample_times)
        with open(f"loadtest_report_{RUN_ID}.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("\n========== 稳定性测试报告摘要 ==========")
        tt = report["totals"]
        print(f"请求总数 {tt['sent']}  成功 {tt['ok']}  错误率 {tt['error_rate']*100:.2f}%  "
              f"吞吐 {tt['throughput_ops_s']:.2f} ops/s")
        lt = report["latency"]
        print(f"延迟(ms) p50={lt['p50']:.1f} p90={lt['p90']:.1f} p95={lt['p95']:.1f} p99={lt['p99']:.1f}")
        sy = report["system"]
        print(f"系统 CPU(avg)={sy['cpu_avg']}% 内存(avg)={sy['mem_avg_mb']}MB")
        v = report["verdict"]
        print(f"稳定性判定 {'通过 OK' if v['passed'] else '未通过 FAIL'}  依据: {v['reason']}")
        print("状态分布: " + ", ".join(f"{k}={x}" for k, x in
                                        sorted(report["status_dist"].items(), key=lambda i: -i[1])))
        print(f"\n报告: {report_path}\nCSV : {csv_path}\nJSON: loadtest_report_{RUN_ID}.json")

        if args.safety_cleanup:
            db_url = args.db_url
            if not db_url and spawned:
                db_url = f"sqlite:///{spawned[2].as_posix()}"
            if db_url:
                safety_cleanup(db_url, RUN_MARK, time.time())
            else:
                print("[提示] 未指定 --db-url 且未使用隔离实例, 跳过清理。")

        engine.close()
        return 0 if v["passed"] else 1
    except SystemExit:
        raise
    except RuntimeError as e:
        print(f"[错误] {e}")
        return 2
    except KeyboardInterrupt:
        print()
        print("[中断] 测试被手动终止。")
    finally:
        if spawned:
            proc, url, db_path = spawned
            if proc.poll() is None:
                print(f"[spawn] 停止隔离后端 PID={proc.pid} …")
                try:
                    proc.terminate()
                    proc.wait(timeout=15)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            try:
                for suffix in ["", "-wal", "-shm"]:
                    pth = Path(str(db_path) + suffix)
                    if pth.exists():
                        pth.unlink()
            except Exception:
                pass
if __name__ == "__main__":
    raise SystemExit(main())

