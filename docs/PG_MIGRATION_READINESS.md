# PostgreSQL 迁移就绪度审查 + 演练清单（Option 2）

> 目标：评估从 SQLite 切到 PostgreSQL 的跨方言就绪度，并给出可复用的验证/回归清单。
> 硬约束说明：**本机无 PostgreSQL、无 Docker、无 psycopg2 同步驱动**；已验证 asyncpg 驱动已安装且
> dialect/URL 解析路径正确（见 §4 冒烟结论），因此本报告结论基于静态审计 + 链路验证，**未做 live 压测**。
> 生产库 `backend/data/managesys.db` 未触碰，生产 uvicorn(8000) 未停止。

---

## 1. 结论速览

| 维度 | 结论 |
|---|---|
| 驱动/URL 链路 | ✅ asyncpg 已装；`postgresql+asyncpg://` 解析正确，报错止于"无服务器"，非配置/方言错误 |
| 占位符 `?` | ✅ `compat_sql.q()` 把 `?`→`:pN`，SQLAlchemy 按方言翻译为 `$1`（PG） |
| 时间函数 | ✅ `translate_sql()` 把 `datetime('now','localtime')`→`CURRENT_TIMESTAMP`（非 SQLite 方言才启用） |
| LIKE 大小写 | ✅ 所有原始 LIKE 均 `LOWER(...) LIKE ?`；ORM `ilike` 翻译为 PG ILIKE |
| 保留字列名 | ✅ 无冲突：`status/level/condition/network/vlan/sort` 均非 PG 保留字；`user` 仅作 relationship 非列 |
| 自增主键 | ✅ 全部走 model (Integer autoincrement=true) → create_all 在 PG 编译为 SERIAL/IDENTITY |
| 原生迁移路径 | ✅ 两处原始 DDL 块已改为 dialect-aware（§2 / §7），SQLite 全链路 alembic 到 head 通过，现亦支持空 PG 独立建库 |
| live 压测 | ⛔ 本机无 PG，无法执行；给出可复用脚本与对比基线 |

---

## 2. 静态审计发现（可验证依据）

### ✅ 已就绪（无需改动即可迁移）
- **占位符桥接**：`backend/app/db/compat_sql.py` 的 `q()` 与 `exec_sql()`。原始 SQL 集中在
  `auto_rules.py / inspection.py / knowledge.py / work_orders.py`（api/v1/）与 `ai_tools.py`（services/）。
  已 grep 确认：**无 `?` 出现在字符串字面量内**，占位符替换不会误伤。
- **时间函数翻译**：`translate_sql()` 仅对非 SQLite 方言启用（`IS_SQLITE` 判断），对现有 SQLite 运行零影响。
  有 `datetime('now')` 变体（含空格差异）全覆盖。
- **参数一致性**：`work_orders.py:343-346` 超长 INSERT：12 个 `?` ↔ 12 个参数，2 个 datetime 被翻译为
  CURRENT_TIMESTAMP，计数一致；`plan_date` 传 `date` 对象/None，PG 的 Date/可空列均接受。
- **日期比较**：`inspection.py:455-460` 的 `scheduled_date = ?` 传 `date.today().isoformat()`（字符串），
  与 model 的 Date 列一致，PG 接受字符串形式 ISO 日期。
- **聚合**：`inspection.py` 的 `SUM(CASE WHEN ...)` PG 兼容。
- **会话/连接池**：`backend/app/db/session.py` 已按方言分支——SQLite 走 PRAGMA 优化，非 SQLite 走
  asyncpg 池配置（`command_timeout` 代替 busy_timeout），`DB_POOL_SIZE=30 / MAX_OVERFLOW=50 / POOL_TIMEOUT=5s / RECYCLE=3600`。
- **Alembic 异步迁移**：`backend/alembic/env.py` 直接用 async 引擎 + asyncpg 跑在线迁移，**无需 psycopg2**。
  迁移脚本基线带守卫：`5c9d0be78b8c` 在 `data_centers` 已存在时跳过整段 create_table（防 create_all 后重复建表）。

### ⚠️ 需注意（迁移真正的潜在坑点）
1. **`c3d0be78b8c9_consolidate_manual_ddl.py` 的 `_columns_definition()`**：✅ 已修复为 dialect-aware
   （`dt_t = "TIMESTAMP" if dialect_name == "postgresql" else "DATETIME"`）。SQLite 生产路径保持 `DATETIME`，零影响。
2. **`d4e5f6a7b8c9_alert_lifecycle.py` 两个裸 `CREATE TABLE`**：✅ 已改为 `op.create_table(...)`
   （dialect-aware，`sa.Integer`/`sa.DateTime(timezone=True)`），原 `AUTOINCREMENT`/`DATETIME` 已消除。

> 结论：**按项目标准启动路径（create_all → alembic）迁移是安全的**；两处原始 SQLite 风格 DDL 已改为
> dialect-aware（已验证 SQLite 下全链路 alembic 到 head 通过 + 强制命中新分支通过），现亦支持"空 PG 直接 alembic 建全库"。

---

## 3. 架构演进建议与取舍（结合高并发写场景）

| 方案 | 适用 | 收益 | 代价/风险 |
|---|---|---|---|
| a. SQLite 调优（已做：WAL + busy_timeout=30s + pool 30/50） | 现状缓解 | 并发写从"database is locked"清零 | 单写者上限仍在，队列满则 503（护栏，非 bug） |
| b. 连接池/框架调参（已调） | 现状 | 减少 QueuePool 打满 | 受进程 & 写锁上限约束 |
| **c. 迁移 PostgreSQL（本任务）** | 多人/长期写 | 真正多写者并发、持久稳定、运维成熟 | 需一套 PG 实例；迁移 + 回归成本（本清单覆盖） |

推荐路径：**先用 SQLite 调优（已落地）支撑现状 → 在压测/并发需求明确超标时，按本清单切 PG**，两者可并存（按
`DATABASE_URL` 切换，代码已方言适配，业务侧零改动）。

---

## 4. 已执行的验证（可在本机复现）

```powershell
# 1) 无服务器冒烟：证明 asyncpg 链路配置正确（报错止于"连不上服务器"）
$env:DATABASE_URL='postgresql+asyncpg://user:pass@127.0.0.1:5432/managesys'
& D:/managesys/.venv/Scripts/python.exe _migration/pg_smoke.py
# 输出：EXPECTED-FAILURE type=ConnectionRefusedError  ← 预期（非方言/配置错误）
```

---

## 5. 迁移在真实 PG 上的执行清单

### 5.1 前置
- 任选其一：本机安装 PostgreSQL(≥12) / Docker `postgres:16-alpine` / 云 RDS。
- 建库与账号：
  ```sql
  CREATE USER managesys WITH PASSWORD '****';
  CREATE DATABASE managesys OWNER managesys;
  ```

### 5.2 冒烟 + 全量回归（推荐顺序）
```powershell
$env:DATABASE_URL='postgresql+asyncpg://managesys:****@127.0.0.1:5432/managesys'
$env:DATABASE_URL_SYNC=$env:DATABASE_URL
# 1) 冒烟连通 + 建表
& D:/managesys/.venv/Scripts/python.exe _migration/pg_smoke.py   # 预期 CONNECTED OK
# 2) 启动应用（create_all + alembic 自动建表/迁移），确认启动日志无 DDL 错误
& D:/managesys/.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
# 3) 跑全量测试（若项目有 pytest 套件，约 220 用例）
& D:/managesys/.venv/Scripts/python.exe -m pytest backend/tests -q
# 4) 同套压测对比（复用 _loadtest/）：
& powershell -File _loadtest/run_load.ps1
& powershell -File _loadtest/run_load_login.ps1
```

### 5.3 前后对比取证（证明问题消除）
- SQLite 基线（已测得）：20 路并发登录 500 从 170→68；`database is locked` 清零；残余 500 全为 QueuePool 超时。
- **混合读写实测基线（30 并发 / 50% 写，隔离库）**：RPS≈28，200≈70、500≈170、503≈137；日志核对
  `database is locked`=0、`OperationalError`=0、全部 500 为 `QueuePool limit size 30 overflow 50 reached, connection timed out`。
- **纯只读对照（40 并发）**：RPS≈62、200=1126/1127，几乎 100% 成功 → 证明瓶颈是**写事务串行占连接耗尽连接池**，
  而非读能力或连接池绝对大小。
- **健康阈值**：≤5 并发混合读写 100% 成功（200 全绿）；≥8 并发混合写开始出现 QueuePool 超时。
- PG 目标：同套压测下 **`500` 应显著下降，`database is locked` 天然不存在**，`QueuePool timed out` 随并发写让位。
- 服务端日志核对项：`sqlite3.OperationalError: database is locked`（PG 下不再出现）、
  `connection timed out`、并发中间件 503（护栏，属预期不算异常）。

### 5.4 回归测试建议（防止引入新 bug）
- 巡检/工单/告警三个多表原始 SQL 接口（inspection.py / work_orders.py / alerts.py）全覆盖。
- 时间相关：`datetime('now')` 翻译后与 `CURRENT_TIMESTAMP` 时区一致性（生产用 Asia/Shanghai，建议统一用 UTC 落库、展示层转本地，PG 的 timestamptz 更稳）。
- 日期比较：`scheduled_date`、`plan_date` 的字符串/date 对象混传。
- 空值与批量写入（sensor_data 高频写入）在 PG 的 `command_timeout=30s` 下是否满足并发写。

### 5.5 监控/告警（防复发）
- 连接池占用：`pool_size + max_overflow` 上限时的 `connection timed out` 计数。
- 锁等待/长事务：PG 侧 `pg_stat_activity` 中 `wait_event`、`now()-xact_start` 超阈值告警。
- 并发中间件 503 计数（作为容量护栏观测，非故障）。

---

## 6. 演进到迁移的过渡
- 本方案（SQLite 调优）是**缓解**；当持续多写、数据量增长或需长期稳定运行时，**应迁移 PG**。
- 过渡策略：代码已方言自适应（compat_sql / session / alembic env），**业务代码零改动**；只需
  `CREATE DATABASE` + 切 `DATABASE_URL` + 跑 §5 验证。数据迁移：存量 SQLite 数据可用 `alembic` 建 PG 空库后，
  用一次性脚本（dump → 类型映射）导入；纯新增系统可忽略存量。

---

## 7. 落地记录（含真实 PG 实测）

### 本机 PG 环境（已建，项目本地实例，非系统服务）
- 二进制：\`_pg/extract/pgsql\`（PG 17.11，ZIP 解压，无安装器）；数据目录 \`pgdata\`。
- 启动：\`postgres -D pgdata -p 5433 -h 127.0.0.1\`（端口 5433，避默认 5432）；识别：角色 \`managesys\` / 库 \`managesys\`。
- \`max_connections=300\`（已调），连接串 \`postgresql+asyncpg://managesys:<pw>@127.0.0.1:5433/managesys\`。

### 已验证通过的 PG 迁移链路（真实执行）
- ✅ \`pg_smoke.py\`：CONNECTED OK + SELECT 1。
- ✅ create_all + \`alembic upgrade head\` → 42 张表，版本到 \`e6f7a8b9c0d1\`。
- ✅ 全应用启动（builtin 数据/权限/admin/默认机房）→ /health 200。
- ✅ 运行时 API 冒烟（ORM + 原始 SQL 的 compat_sql 路径）：登录、facilities、sensors、devices、alerts、work-orders、kb、audit-logs 全 200。
- ✅ 写读回环：20 条并发 sensor 写入全 200，24h 趋势降采样查询正确。

### 迁移中发现并修复的真实 PG 方言 bug（关键）
- **\`c3d0be78b8c9\` 的 \`DROP INDEX uq_ip_address_subnet_addr\` 在 PG 上必失败**：
  PG 上该索引是唯一约束的支撑索引，\`DROP INDEX\` 报 \`cannot drop index ... requires it\`，且在同一事务内使整个 alembic 迁移中止。
  已改为 dialect-aware：PG 分支只做 \`CREATE UNIQUE INDEX IF NOT EXISTS uq_ip_address_addr\`（约束已存在时幂等 no-op），不再 DROP。SQLite 保持原逻辑。
- 教训：仅靠静态审查 + SQLite 测不过不出的问题，真实 PG 才暴露——本项验证正是这类问题的价值。

### 压测对比（PG pool 200/100、PG max_connections=300）
| 并发 | SQLite（旧基线） | PostgreSQL（本次） |
|---|---|---|
| 8 混合写 | 47% 失败(76×500, QueuePool 超时) | **0×500**，全 200 |
| 15 混合写 | 58% 失败(200×500) | **0×DB 错误**；超载走 503 并发护栏 |
- 关键：PG 下不再有 \`database is locked\` / \`QueuePool timed out\`(500)；超载由 503 护栏优雅限流。
- 压测残余的 503/重复用户名/空 Bearer 均为测试客户端副作用，非 DB 问题。

### 运维要点（重要）
- **连接池必须与 PG 的 max_connections 匹配**：app 池(\`DB_POOL_SIZE+DB_MAX_OVERFLOW\`)须 \$leq\$ PG \`max_connections\`，否则 app 起池子时报 \`TooManyConnectionsError\`。建议 \`DB_POOL_SIZE=200\`、\`DB_MAX_OVERFLOW=100\`（总额 300 匹配 PG 300），并调 \`DB_POOL_TIMEOUT=10\`。
- 生产迁移时：确保 PG \`max_connections\` ≥ 连接池总额，否则不可用。

1. ✅ **已完成**两处原始 DDL 加固（c3d0be78b8c9 / d4e5f6a7b8c9），改为 dialect-aware
   （PG 用 `TIMESTAMP`，SQLite 保持 `DATETIME`/原有 CREATE 语义）。验证方式：
   - 全新 SQLite 库 `alembic upgrade head` 全链路通过（exit=0）。
   - 合成"缺列/缺表"库 + `stamp c3d0be78b8c9` 后 `upgrade d4e5f6a7b8c9`，强制命中
     ALTER + op.create_table 两个新分支，均执行成功，列/主键正确。
   - 对当前 SQLite 生产零影响（原始路径本就由 `_has_column`/`_has_table` 守卫跳过）。
2. 生产选择：当前 SQLite 是否继续作为生产，或近期安排迁移 PG——决定投入优先级。

> 注：若未来在真实 PG 上执行，仍建议按 §5 冒烟 + 全量回归走一遍，覆盖真实方言下完整启动（create_all + alembic）时序。
