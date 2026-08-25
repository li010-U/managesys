# -*- coding: utf-8 -*-
"""一键启停开发环境的后端(uvicorn:8000)与前端(vite:5173)。

用法:
    python dev_server.py start     # 启动两个服务(已占用则跳过)
    python dev_server.py stop      # 关闭两个服务
    python dev_server.py status    # 查看状态
    python dev_server.py restart   # 重启两个服务
"""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 仓库根目录(scripts 的上一级)
BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
STATE_DIR = os.path.join(ROOT, ".dev")
LOG_DIR = os.path.join(STATE_DIR, "logs")
PID_FILE = os.path.join(STATE_DIR, "pids.json")

_VENV_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "Scripts", "python.exe")
if os.path.exists(_VENV_PY):
    PYTHON = _VENV_PY
else:
    PYTHON = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python314", "python.exe")
    if not os.path.exists(PYTHON):
        PYTHON = "python"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

# 实时数据模拟器（告警生命周期去重/自动恢复驱动）
DEV_TOOLS_DIR = os.path.join(BACKEND_DIR, "dev_tools")
SIM_SCRIPT = os.path.join(DEV_TOOLS_DIR, "simulate_realtime.py")
# 默认随 start 一起启动实时模拟器；设 START_SIMULATOR=0 可关闭
SIM_ENABLED = os.environ.get("START_SIMULATOR", "1") not in ("0", "false", "False")
SIM_ARGS_DEFAULT = ["--interval", "1.0", "--per-cycle", "0", "--consecutive", "3", "--keep-hours", "24"]


def _pid_by_port(port):
    """通过 netstat 找到监听指定端口的进程 PID。"""
    try:
        if sys.platform == "win32":
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                                 capture_output=True, text=True, timeout=10).stdout or ""
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3].upper() == "LISTENING":
                    return int(parts[4])
        return None
    except Exception:
        return None


def ensure_dirs():
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def load_pids():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_pids(pids):
    ensure_dirs()
    with open(PID_FILE, "w", encoding="utf-8") as f:
        json.dump(pids, f)


def is_alive(pid):
    if not pid:
        return False
    if sys.platform == "win32":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=5,
            ).stdout or ""
            return str(pid).strip() in out and "INFO" not in out
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def spawn_service(name, cmd, cwd, log_name, env=None):
    log_path = os.path.join(LOG_DIR, log_name)
    out = open(log_path, "ab", buffering=0)
    # CREATE_NO_WINDOW = 0x08000000
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=out,
            stderr=subprocess.STDOUT,
            env=proc_env,
            creationflags=subprocess.CREATE_NO_WINDOW,
            shell=False,
        )
    except Exception as e:
        print(f"  [失败] {name} 启动异常: {e}")
        return None
    print(f"  [启动] {name} (PID={proc.pid}), 日志: {log_path}")
    return proc.pid


def start():
    ensure_dirs()
    pids = load_pids()
    print("=== 数据中心资源智能管理系统 · 开发环境启动 ===")

    # 后端
    if port_in_use(BACKEND_PORT):
        print(f"  [跳过] 后端已在运行 (端口 {BACKEND_PORT})")
    else:
        print("  [检查] 后端依赖...")
        if pids.get("backend") and is_alive(pids["backend"]):
            print(f"  [信息] 后端进程存活 PID={pids['backend']}")
        cmd = [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
               "--port", str(BACKEND_PORT), "--reload", "--log-level", "warning"]
        pid = spawn_service("后端", cmd, BACKEND_DIR, "backend.log")
        if pid:
            pids["backend"] = pid

    # 前端
    if port_in_use(FRONTEND_PORT):
        print(f"  [跳过] 前端已在运行 (端口 {FRONTEND_PORT})")
    else:
        if not os.path.exists(os.path.join(FRONTEND_DIR, "node_modules")):
            print("  [安装] 前端 npm 依赖中，请稍候...")
            subprocess.run(["npm", "install"], cwd=FRONTEND_DIR, check=False)
        node_exe = shutil.which("node") or "node"
        vite_js = os.path.join(FRONTEND_DIR, "node_modules", "vite", "bin", "vite.js")
        if os.path.exists(vite_js):
            vue_cli = [node_exe, vite_js, "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)]
        else:
            vue_cli = ["npx", "vite", "--host", "127.0.0.1", "--port", str(FRONTEND_PORT)]
        pid = spawn_service("前端", vue_cli, FRONTEND_DIR, "frontend.log")
        if pid:
            pids["frontend"] = pid

    # 实时数据模拟器（告警生命周期驱动）
    if SIM_ENABLED:
        sim_pid = pids.get("simulator")
        if sim_pid and is_alive(sim_pid):
            print(f"  [跳过] 实时模拟器已在运行 (PID={sim_pid})")
        elif os.path.exists(SIM_SCRIPT):
            sim_env = {"ALLOW_DEV_TOOL_WRITE": "1"}
            cmd = [PYTHON, SIM_SCRIPT] + SIM_ARGS_DEFAULT
            pid = spawn_service("实时模拟器", cmd, DEV_TOOLS_DIR, "simulator.log", env=sim_env)
            if pid:
                pids["simulator"] = pid
    else:
        print("  [跳过] 实时模拟器未启用 (START_SIMULATOR=0)")

    save_pids(pids)
    if sys.platform == "win32":
        print("  前端: http://127.0.0.1:5173")
        print("  后端: http://127.0.0.1:8000")
        print("  API文档: http://127.0.0.1:8000/docs")


def stop():
    pids = load_pids()
    print("=== 关闭开发环境服务 ===")
    for name, pid in pids.items():
        if pid and is_alive(pid):
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                   capture_output=True, text=True, timeout=10)
                else:
                    os.kill(pid, signal.SIGTERM)
                print(f"  [停止] {name} (PID={pid})")
            except Exception as e:
                print(f"  [警告] {name} 停止失败: {e}")
        else:
            print(f"  [信息] {name} 未在运行")
    save_pids({})
    # 兜底：若端口仍被占用，定位监听进程并结束（这些通常是旧/手动启动的实例）
    for port, name in [(BACKEND_PORT, "后端"), (FRONTEND_PORT, "前端")]:
        if port_in_use(port):
            pid = _pid_by_port(port)
            if pid and pid != os.getpid():
                print(f"  [提示] {name} 端口 {port} 被 PID={pid} 占用，正在结束...")
                try:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                       capture_output=True, text=True, timeout=10)
                    else:
                        os.kill(pid, signal.SIGTERM)
                except Exception as e:
                    print(f"  [警告] 结束 PID={pid} 失败: {e}")
            else:
                print(f"  [提示] {name} 端口 {port} 仍被占用，请手动排查")


def status():
    pids = load_pids()
    print("=== 服务状态 ===")
    for port, name in [(BACKEND_PORT, "后端"), (FRONTEND_PORT, "前端")]:
        if port_in_use(port):
            print(f"  [运行] {name} (端口 {port})")
        else:
            print(f"  [停止] {name} (端口 {port})")
    for name, pid in pids.items():
        if pid and is_alive(pid):
            print(f"  [PID] {name} = {pid} (存活)")
        else:
            print(f"  [PID] {name} = {pid} (已退出)")
    if SIM_ENABLED:
        spid = pids.get("simulator")
        if spid and is_alive(spid):
            print(f"  [运行] 实时模拟器 (PID={spid})")
        else:
            print(f"  [停止] 实时模拟器")


def restart():
    stop()
    import time
    time.sleep(2)
    start()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        restart()
    else:
        status()


if __name__ == "__main__":
    main()
