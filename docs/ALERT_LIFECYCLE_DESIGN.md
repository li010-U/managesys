# 设备告警：自动恢复 / 去重防抖 / 偶发故障与环境关联统计 方案

> 批次实现文档。目标：让告警具备完整生命周期管理（自动关闭、去重限频、短时自愈
> 识别、故障-环境关联统计），并产出可独立打开的 HTML 可视化关联报表。

---

## 1. 确定性口径（需求映射）

| 需求 | 规则实现 |
| --- | --- |
| 自动恢复（已解决） | 同一设备参数**连续正常 >= 30 分钟**才将告警置为「已解决」；期间再次异常则不落地、继续挂起 |
| 去重 | 以**同一设备**为去重维度；故障未解决期间再次异常只刷新 `last_abnormal_at`/累加 `occurrences`，不新增告警 |
| 短时自愈（偶发） | 故障在 `ALERT_TRANSIENT_MAX_SECONDS`（默认 300s）内恢复 ⇒ 记为偶发，写入 `transient_failure_events`，**不推送**；随后按 30 分钟规则自动解决 |
| 解决后可持续 | 进入「已解决」后再次异常允许再告警，但受 `ALERT_COOLDOWN_MINUTES`（默认 5 分钟）冷却防抖约束 |
| 关联统计 | 偶发事件按 小时 / 天气类型 / 温度湿度风速区间 聚合频次、占比与时间分布 |

配置项（`backend/app/core/config.py`）：

- `ALERT_AUTO_RESOLVE_MINUTES`（默认 30）
- `ALERT_TRANSIENT_MAX_SECONDS`（默认 300）
- `ALERT_COOLDOWN_MINUTES`（默认 5）
- `ALERT_LIFECYCLE_TASK_ENABLED` / `ALERT_LIFECYCLE_INTERVAL_SECONDS`
- `ENV_RETENTION_DAYS`（默认 180）

---

## 2. 数据模型

### `Alert`（`backend/app/models/alert.py`）新增字段
- `last_abnormal_at`：最近异常时间
- `normal_since_at`：恢复正常时间（累计“连续正常时长”的锚点）
- `auto_resolve_minutes`：该告警的自动恢复阈值（默认 30）
- `duration_seconds`：持续时长（秒，解决时回填）
- `is_transient`：是否偶发（短时自愈）故障
- `cooldown_until`：冷却到期时间（去重防抖）
- `lifecycle_action`：处置方式（`auto_resolve` / `transient` / `cooldown` / `recovered`…）

### `EnvWeatherRecord`（`backend/app/models/env_weather.py`）
温度 / 湿度 / 天气 / 风速 / 位置 + 记录时间，供关联统计。

### `TransientFailureEvent`（`backend/app/models/env_weather.py`）
偶发故障事件留痕：开始/恢复时间、持续时长、关联告警 ID，以及发生时点的
环境/气象快照（温/湿/天气/风速/位置）。

---

## 3. 核心服务

### `AlertLifecycleService`（`backend/app/services/alert_lifecycle_service.py`）
统一信号入口 `register_signal(target_type, target_id, is_abnormal, ...)` 的状态机：

```
异常信号：
  - 存在开放告警     -> updated（去重归并，刷新 last_abnormal_at，occurrences+1）
  - 已解决且在冷却期 -> suppressed_cooldown（防抖抑制）
  - 无开放告警       -> created（新告警）

恢复信号：
  - 无开放告警 -> nothing
  - 有开放告警：
      距 first_seen <= transient 窗口 -> transient_created（偶发：只记录不推送）
      否则                                -> recovered（记录 normal_since_at）

后台扫描 sweep_auto_resolve()：
  开放告警且 normal_since_at 距今 >= auto_resolve_minutes -> status=resolved，
  resolved_at/cooldown_until/duration_seconds 回填，lifecycle_action=auto_resolve
```

进程内后台任务在 `backend/app/main.py` 的 `_alert_lifecycle_loop()` 中周期执行
（间隔 `ALERT_LIFECYCLE_INTERVAL_SECONDS`，默认 60s）。

### `EnvWeatherService`（`backend/app/services/environment_service.py`）
- `record(...)`：摄入环境/气象数据
- `attach_nearest_env(event)`：为偶发事件补全发生时点最近的环境快照
- `correlation_by_hour / correlation_by_weather / correlation_by_env_bucket / severity_summary / correlation_report`

### `AlertCorrelationReportService`（`backend/app/services/alert_report_service.py`）
- `build(days)`：汇总关联统计数据
- `render_html(data)`：生成内嵌 Chart.js 的可独立打开 HTML 报表（逐小时 / 天气 / 环境区间）

---

## 4. API（`backend/app/api/v1/alert_lifecycle.py`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/v1/alert-lifecycle/signal` | 设备参数异常/恢复信号（去重/防抖/偶发识别） |
| POST | `/api/v1/alert-lifecycle/sweep` | 手动触发自动恢复扫描 |
| POST | `/api/v1/alert-lifecycle/env` | 摄入环境/气象数据 |
| GET | `/api/v1/alert-lifecycle/env/recent` | 最近环境数据 |
| GET | `/api/v1/alert-lifecycle/transient` | 偶发故障事件列表 |
| GET | `/api/v1/alert-lifecycle/correlation` | 关联统计 JSON |
| GET | `/api/v1/alert-lifecycle/correlation/report` | HTML 可视化报表 |

权限：使用 `monitor:handle_alert` / `monitor:view_alerts`（与既有告警一致）。

---

## 5. 偶发故障识别规则（汇总）

1. 设备参数由“异常”恢复为“正常”时，判断自“首次异常（`first_seen_at`）”到恢复时刻的时长。
2. 若 `0 < 时长 <= ALERT_TRANSIENT_MAX_SECONDS（300s）` ⇒ 判定为**短时自愈的偶发故障**。
3. 偶发故障：将 `Alert.is_transient=True`、`lifecycle_action='transient'`，**写入**
   `transient_failure_events`（含发生时刻与持续时长），**不推送/不打扰**。
4. 偶发告警仍按 30 分钟连续正常规则自动置为「已解决」，时长在 `_finalize_transient_event`
   中回填 `recovered_at` / `duration_seconds`。

---

## 6. 环境关联统计（输出）

- 逐小时分布：24 小时偶发故障频次与占比。
- 天气类型分布：晴/多云/阴/雨/雪/风… 频次与占比。
- 环境区间分布：温度（<15 / 15~25 / 25~32 / 32~38 / >=38°C）、
  湿度（<40 / 40~60 / 60~80 / >=80%RH）、风速（<3 / 3~6 / 6~10 / >=10 m/s）。
- 汇总：总数、平均/最长/最短/累计时长。
- 可视化：`GET /api/v1/alert-lifecycle/correlation/report` 返回内嵌 Chart.js 直方图与饼图的
  HTML 报表，可直接在浏览器打开。

---

## 7. 验收对照

| 验收项 | 落地 |
| --- | --- |
| 同一设备未解决时不重复告警 | `register_signal` 去重归并（单测覆盖） |
| 参数连续 30 分钟正常 -> 已解决 | `sweep_auto_resolve`（单测覆盖） |
| 秒/分钟级自愈 -> 记录且不打扰 | `transient_created` + `transient_failure_events`（单测覆盖） |
| 解决后可再告警 + 冷却防抖 | `cooldown_until` 抑制 + 冷却过期重建（单测覆盖） |
| 关联统计结果/可视化 | `correlation` API + HTML 报表（单测 + E2E 覆盖） |

---

## 8. 迁移

新增 Alembic 迁移 `backend/alembic/versions/d4e5f6a7b8c9_alert_lifecycle.py`
（守卫式 ADD COLUMN / CREATE TABLE IF NOT EXISTS），
兼容新库与存量库；启动时由 `Base.metadata.create_all` + `alembic upgrade head` 收敛。

---

## 9. 环境数据自动轮询采集工具

`backend/dev_tools/collect_env_weather.py`：周期采集环境/气象数据写入 `env_weather_records`。

- `--source sim`（默认）：本地生成贴近真实天气的演示值，无网络依赖。
- `--source real`：调用 Open-Meteo 开放接口（无需 API Key）拉取真实天气，通过 `--lat/--lon` 指定位置。
- `--dry-run`（默认）/ `--really-write`（需 `ALLOW_DEV_TOOL_WRITE=1`），与其它 dev_tools 一致的安全护栏。
- `--interval` 轮询间隔（秒，默认 300）、`--once` 单次采集。

示例：
```bash
# 演示值，每 5 分钟采集一次
ALLOW_DEV_TOOL_WRITE=1 python collect_env_weather.py --source sim --interval 300 --really-write

# 真实天气（合肥），单次采集
ALLOW_DEV_TOOL_WRITE=1 python collect_env_weather.py --source real --lat 31.82 --lon 117.23 --once --really-write
```

### 后台常驻采集（可选）

除命令行工具外，后端也内置了进程内环境采集轮询任务（与告警生命周期任务同款机制），
默认**关闭**，避免在测试/无网环境误跑：

- 新增 `backend/app/services/environment_service.py::EnvPoller`（sim/real 双源，与 dev_tool 同口径）。
- 后台循环 `_env_poll_loop` 已接入 `backend/app/main.py` 生命周期。
- 开关/参数见 `backend/.env.example`：
  - `ENV_POLL_TASK_ENABLED`（默认 false，置 true 开启）
  - `ENV_POLL_INTERVAL_SECONDS`（默认 300）
  - `ENV_POLL_SOURCE`（sim/real）、`ENV_POLL_LAT/LON`、`ENV_POLL_LOCATION_NAME/ID`
- 测试：`backend/tests/test_env_poller.py`（验证 sim 写库、多条累计），conftest 已强制关闭避免挂起。
