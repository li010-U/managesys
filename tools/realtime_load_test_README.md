# 实时数据流模拟 + 并发稳定性压测脚本

脚本：`tools/realtime_load_test.py`
用途：在接近真实生产的实时数据负载下，验证《数据中心资源智能管理系统》的稳定性与并发处理能力。

## 功能
- 可配置数据生成频率（ops/s）、数据规模（scale）、模拟并发用户数（users）、运行时长（duration）。
- 覆盖系统核心资源数据维度：传感器时序写入/读取、传感器状态更新、告警产生、工单创建、监控大屏/洞察/告警轮询（读多写少混合）。
- 运行中实时监控：请求数、成功率、错误率、响应延迟分位（p50/p90/p95/p99）、吞吐、CPU%、内存、HTTP 状态分布、超时数。
- 按预设时长稳定运行后输出稳定性测试报告：终端摘要 + `Markdown` + `CSV` 采样 + `JSON`，支持与基线报告对比。
- 稳定性判定：错误率 ≤ `--max-error-rate` 且 P99 ≤ `--max-p99` 即通过（退出码 0），否则失败（退出码 1）。

## 快速开始（推荐，安全）
`--spawn-server` 会自动启动一个一次性隔离后端实例：
- 关闭验证码（`ENABLE_CAPTCHA=false`）、使用独立随机端口；
- 用 SQLite 备份 API 从真实库 `backend/data/managesys.db` 复制一份数据（WAL 安全，不丢数据）；
- 把测试库的 admin 密码重置为已知值，自动登录；
- 测试结束自动终止进程并删除临时库 / `-wal` / `-shm` / 日志，完全不影响现有系统与数据。

```powershell
# 8 并发用户、40 ops/s、运行 60 秒
python tools/realtime_load_test.py --spawn-server --duration 60 --users 8 --frequency 40

# 全新空库（冷启动）压测
python tools/realtime_load_test.py --spawn-server --spawn-fresh --duration 60 --users 8 --frequency 40
```

## 连接现有后端
> 现有后端若开了验证码（`ENABLE_CAPTCHA=true`），自动登录会失败，请传 `--token` 或临时关闭验证码。

```powershell
# 传入已签发 token
python tools/realtime_load_test.py --base-url http://127.0.0.1:8000/api/v1 --token <JWT> --duration 120 --users 50 --frequency 100

# 验证码已关闭时用账号密码
python tools/realtime_load_test.py --base-url http://127.0.0.1:8000/api/v1 --username admin --password <pw> --duration 60 --users 20 --frequency 50
```

> ⚠️ 直连现有后端会向真实库写入测试数据。跑前请备份数据库；或用 `--safety-cleanup` 自动删除本次打标（`gen_loadtest_*`）的告警/工单/传感器数据；或改用 `--spawn-server` 隔离实例。

## 完整参数
| 参数 | 默认 | 说明 |
|---|---|---|
| `--base-url` | `http://127.0.0.1:8000/api/v1` | 被测后端 API 根地址 |
| `--users` | `10` | 模拟并发用户/客户端数 |
| `--frequency` | `20` | 目标数据生成频率 ops/s（0=不节流） |
| `--rps` | 空 | 目标吞吐（覆盖 `--frequency`） |
| `--scale` | `1.0` | 模拟规模系数 |
| `--duration` | `60` | 稳定运行秒数 |
| `--warmup` | `5.0` | 预热秒数（不计统计） |
| `--interval` | `0.5` | 系统指标采样间隔秒数 |
| `--max-error-rate` | `0.05` | 通过阈值：错误率上限 |
| `--max-p99` | `1000` | 通过阈值：P99 延迟 ms |
| `--token` | 空 | 预签发 JWT（推荐直连模式） |
| `--username` / `--password` | admin | 登录凭据（验证码关闭时） |
| `--pid` | 自动探测 | 监控的进程 PID（0=自动探测活跃 uvicorn） |
| `--spawn-server` | 关 | 自动启动一次性隔离后端 |
| `--spawn-fresh` | 关 | 隔离实例用全新空库（不复制真实数据） |
| `--seed-db` | 自动 | 复制真实数据的来源库路径 |
| `--report` / `--csv` | 自动 | Markdown 报告 / CSV 采样输出路径 |
| `--safety-cleanup` | 关 | 测试后清理本次打标数据 |
| `--baseline` | 空 | 基线报告 JSON 路径（用于对比） |
| `--db-url` | 空 | `--safety-cleanup` 用数据库 URL |

## 输出
- `loadtest_report_<时间戳>.md` —— 稳定性报告（配置/总体/延迟/状态分布/分类明细/系统资源/对比/判定/异常统计）。
- `loadtest_samples_<时间戳>.csv` —— 逐采样点指标序列。
- `loadtest_report_<时间戳>.json` —— 结构化报告（可作下次 `--baseline`）。
- 退出码：`0`=通过，`1`=未通过，`2`=参数/环境错误。

## 设计说明
- **并发引擎**：线程池 + 每虚拟用户独立 keep-alive 会话；token 复用（登录有 10/min 限流，故不每个并发单独登录）。
- **数据生成器**：传感器数值做随机游走，约 20% 故意越阈以触发告警；告警/工单标题带 `gen_loadtest_<时间戳>` 标记以便清理。
- **系统监控**：不依赖 psutil。Windows 用 ctypes/psapi 读进程 CPU/内存，Linux 用 `/proc`；自动探测时选工作集最大的活跃 uvicorn 进程。
- **“队列积压”代理指标**：系统为 SQLite + 线程池架构，无独立任务队列；报告以 503/超时/请求等待时间作为积压代理。
- **SQLite WAL**：复制真实库用 `sqlite3.Connection.backup` 而非文件拷贝，避免丢未 checkpoint 数据。

## 实测中发现的问题（供后续优化参考）
1. 高并发写入下错误率与 P99 显著劣化：SQLite 单写者串行化，`sensor_data` 高频写入在 10 用户 / 40 ops/s 时出现约 20% 超时、P99≈10s。若要支持更高并发，建议迁移 PostgreSQL 或多写库。
- [已修复] `GET /sensors/retention-status` 曾因路由注册顺序被 `/{sensor_id}` 遮蔽而返回 422。已为 5 处 `/sensors/{sensor_id}...` 路径参数路由加 `:int` 路径转换器（`{sensor_id:int}`），字面量路由 `retention-status` / `anomaly-gaps` / `retention` / `all` 现均正常（实测 200）。
- [已修复] 传感器不存在时 `POST /sensors/{id}/data` 曾因外键约束在 `flush` 时抛 `IntegrityError` 返回 500。现 `SensorService.record_data` 在传感器不存在时返回 `None`，路由转为 404 `{"detail":"传感器不存在"}`。
