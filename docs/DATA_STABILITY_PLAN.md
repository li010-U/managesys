# 数据稳定性方案（P0 + P1）— 可评审稿

> 目标：只加固稳定性、不加新功能、不碰生产代码。所有结论基于实测/代码核实，标注"已完成 vs 真实缺口"。
> 生产库 \`backend/data/managesys.db\`（77.6 万 sensor_data）未触碰；生产 uvicorn(8000) 未动。

---

## 0. 先说清"哪些已解决"（避免方案建立在过时前提上）

经代码核实，以下**在本项目已经实现**，不属于缺口：

| 项 | 现状（代码位置） | 结论 |
|---|---|---|
| "按时间保留"（改行数→按时间） | \`sensor_anomaly_service.py:138-155 run_retention\` 用 \`recorded_at < cutoff\`，分批 5000+逐批提交；144000 行数逻辑已全部清零 | ✅ 已完成 |
| "近24h 只显示十几分钟" | \`sensor_service.py:121-177\`：hours 查询整窗流式降采样到 MAX_TREND_POINTS=240，内存恒定、整窗覆盖 | ✅ 已完成 |
| 趋势查询性能 | 已有 \`ix_sensor_data_sensor_id_recorded_at\` 组合索引（e6f7a8b9c0d1） | ✅ 已完成 |
| 清理任务启用 | \`DATA_RETENTION_TASK_ENABLED=True\`（生产 .env 未覆盖，用默认），清理 \`sensor_data\` + \`sensor_anomaly_gap\` | ✅ 已启用 |

> 因此 P1 的真实缺口**不是**"改按时间"或"加降采样"，而是**分层留存与写路径**（见 §2）。

---

## 1. P0 — PostgreSQL 迁移（根治并发写瓶颈）【唯一真正到物理上限项】

### 1.1 为什么是它
压测实测（隔离库）：混合读写 ≤5 并发 100% 成功；≥8 并发写即触发
\`QueuePool limit size 30 overflow 50 reached, connection timed out\`（500），\`database is locked\`=0。
根因 = SQLite **单一写者**在并发写事务下串行持连接 → 连接池(30+50=80)被慢写占满。这是架构上限，非 bug。

### 1.2 方案要点（复用已做完的适配，不重写）
- **DB 层**：按 \`DATABASE_URL\` 切 `postgresql+asyncpg://...\`，业务零改动。
  已就绪：\`compat_sql\`（?→$1、datetime 翻译）、\`session.py\` PG 分支（command_timeout）、
  \`alembic env.py\` async+asyncpg（无需 psycopg2）、两处原始 DDL 已 dialect-aware（上轮已修）。
- **写路径**（可选，配合单写者让位 PG 更稳）：写入 HTTP 层批量/串行化可选，非强制。
- **pool 参数**（PG 下更从容）：\`DB_POOL_SIZE\` 可上调（如 30→50）、\`DB_POOL_TIMEOUT\` 5→10s，PG 多写者下连接不再被写锁憋死。

### 1.3 验证/回滚
- 起 PG → \`_migration/pg_smoke.py\`（连通+create_all）→ 全量 220 用例 → 同套压测对比（§5.3 基线已归档）。
- 回滚：\`DATABASE_URL\` 指回 sqlite，代码已双轨，零改动回退。

### 1.4 取舍
- 收益：真正多写者并发、消除 8 并发写即 500、长期稳定。
- 代价：需维护一套 PG 实例；投入一次迁移+回归。读写均快（PG 读用 shared_buffers 更稳）。

---

## 2. P1 — sensor_data 分层留存与写加固

### 2.1 真实缺口（非"改按时间"）
1. **无冷热分层**：现在 \`sensor_data\` 明细全留 180 天（\`DATA_RETENTION_DAYS=180\`）。77.6 万行/4 天、约 19 万行/天。
   "异常保留 180 天"的需求，现状是**全部**保留 180 天（含正常点），主表随运行持续膨胀。
2. **写入是单条 INSERT**（\`sensors.py:151 record_sensor_data\` 逐条落库）→ 高频传感器在 SQLite 下加剧连接竞争。

### 2.2 目标形态（最小、可回滚）
- **正常明细：保留较短（如 7~30 天）**，满足"24h/最近一周"曲线。
- **异常/告警关联数据：保留 180 天**（满足你确认的"异常数据需 180 天"）。
- **写入：支持批量落库**（单写者友好），对现有逐条接口零破坏（新增批量内部路径，或仅给高频来源用）。

### 2.3 具体改动点（不新增功能，仅调整保留口径）
- **方案 A（推荐，改动最小）**：调整 \`run_retention\`，按 \`source_mark\` 分层 cutoff——
  \`normal\` 数据按 30 天、\`abnormal\` 数据按 180 天分别清理（\`source_mark\` 已存在于 e6f7 迁移）。
  - 改动位置：\`sensor_anomaly_service.py:131-155\`，把单 cutoff 改成按 source_mark 双 cutoff。
  - 现有 \`sensor_anomaly_gap\` 已是异常专用表，其 180 天保留不变。
- **方案 B（更大，可后置）**：正常明细迁入\`sensor_data\`热表+异常明细入\`sensor_data_archive\`归档表。
  查询多一个分支，改动面大，**建议非必要不先做**。

### 2.4 写入批量化（可选，P1 副项）
- 新增 \`POST /sensors/{id}/data/batch\` 或内部批量 ORM 写入，减少高频写入的来回。若传感器来源走接口单点上报且频率低，亦可先不做。

### 2.5 验证
- 造 30 天前的 normal + abnormal 各若干 → 跑保留 → normal 被清、abnormal 保留；边界用 BUFFER 防误删。
- 回归趋势接口：24h/7d 曲线点数、倒序契约不变（\`sensor_service.get_recent_data\` 单测）。

---

## 2.6 P1-A 落地记录（已完成 + 已回归）
- 改动：\`config.py\` 新增 \`DATA_RETENTION_NORMAL_DAYS=30\`；\`sensor_anomaly_service.py\` 的
  \`run_retention\` 改为按 \`source_mark\` 分层（normal 按 30 天、非 normal 按 180 天），
  返回字段向后兼容（ResponseSchema 不变，新增明细字段在序列化时被忽略）。
- 新增 2 条测试（正常点短留 / 异常点长留 / 边界安全）。全量 **222 用例通过**，零回归。
- 生产库与运行进程未受影响。

---

## 2.7 P0 执行清单（PostgreSQL 迁移）— 就差一台 PG 实例
前置：任选 本机 PG(>=12) / \`docker run -e POSTGRES_PASSWORD=... -p 5432:5432 postgres:16-alpine\` / 云 RDS。
\`\`\`sql
CREATE USER managesys WITH PASSWORD '...';
CREATE DATABASE managesys OWNER managesys;
\`\`\`
\`\`\`powershell
$env:DATABASE_URL='postgresql+asyncpg://managesys:...@127.0.0.1:5432/managesys'
$env:DATABASE_URL_SYNC=$env:DATABASE_URL
# 1) 连通 + create_all 冒烟
& D:/managesys/.venv/Scripts/python.exe _migration/pg_smoke.py   # 预期 CONNECTED OK
# 2) 启动（create_all + alembic 自动建表/迁移）；观察启动日志无 DDL 报错
& .venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# 3) 全量回归
& .venv/Scripts/python.exe -m pytest backend/tests -q            # 预期 222 passed
# 4) 同套压测对比（对照 _migration/PG_MIGRATION_READINESS.md §5.3 基线）
& powershell -File _loadtest/run_load.ps1 30
\`\`\`
回滚：\`DATABASE_URL\` 指回 sqlite 即可（代码已双轨），无需改代码。
数据迁移（存量）：PG 空库建好后，用一次性脚本按列类型映射导入 \`sensor_data/alerts\` 等核心表；
纯新增系统可忽略存量。

---

## 3. 优先级与顺序建议
1. **先 P0**（PG 迁移）：根治写压缩测硬瓶颈，属于"不演进就会在更高并发下出 503/500"。
2. **再 P1-A**（source_mark 分层留存）：控制主表膨胀，改动量小（一个函数内），风险低。
3. **P1-B / 批量写**：视 PG 迁移后的实际写入量与查询表现再决定，避免过度设计。

---

## 4. 明确不做的（避免"加功能/过度设计"）
- 不引入时序 DB / 消息队列 / 独立日志库（当前量级 19 万行/天在 PG 下完全可扛，SSD 索引即可）。
- 不做告警/审计冷热归档分库（\`alerts\` 5.5 万、\`audit_logs\` 382 行，量级太小无需动）。
- 不为降采样新建物化视图/聚合表（应用内流式降采样已够用，避免重复投资）。
