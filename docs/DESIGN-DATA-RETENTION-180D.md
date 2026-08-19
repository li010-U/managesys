# 数据接入与 180 天保留设计文档

> 目标：后续接入数据后，最低保留 **180 天**；传感器约**大几十台（数量待定）**，**每台每小时一条**；对"数据异常且不在采集点"的情况要**特殊标记**。
> 本文档为设计稿，落地前需确认文末"待确认项"。

---

## 1. 需求解读

| 需求 | 含义 |
|---|---|
| 最低保留 180 天 | 业务数据（尤指传感器时序数据）至少可回溯 180 天；到期后可裁剪 |
| 传感器数量待定 | 现约大几十台，可能增长，设计需考虑扩容 |
| 每台每小时一条 | 单台 24 点/天，属于**低频**数据 |
| 异常且不在采集点需标记 | 出现异常时刻但该时刻**没有采集记录**（如偶发丢点/告警落在两次采集之间），要能定位并留痕 |

---

## 2. 容量估算（关键结论：SQLite 足够，无需上时序库）

以"大几十台、每小时一条"估算：

| 项 | 估算 |
|---|---|
| 单台每天 | 24 条 |
| 总量（设 70 台） | 24 × 70 ≈ **1,680 条/天** |
| 180 天总量 | 1,680 × 180 ≈ **30 万条** |
| 单行体积（约 60B） | 30 万 × 60B ≈ **~18MB / 180 天** |
| 按 1,000 台上限推算 | 24 × 1000 × 180 ≈ 432 万条 ≈ ~260MB |

**结论**:在本频率下，180 天数据量级为数十万到数百万行，**当前 SQLite 完全能够承受**，不构成性能瓶颈。因此**不需要**降采样聚合表、也不需迁移 ClickHouse/TimescaleDB/InfluxDB（那些是针对"每台每秒一条、上亿行"的高频场景）。设计重心放在**正确的索引、滚动清理、异常标记**上，并为未来扩容预留升级路径。

> 若未来单台频率提升到分钟级或秒级，再评估方案 C（迁移时序库）；本文不改动采集频率本身。

---

## 3. 数据模型设计

### 3.1 现有 `sensor_data` 表（`backend/app/models/sensor.py`）
```text
id, sensor_id(FK), value(float), recorded_at(datetime)
```
问题：`recorded_at` 和 `sensor_id` **无索引**，按时间删除/查询会全表扫；无异常标记；无清理机制。

### 3.2 建议改动

**a) 新增复合索引 `(sensor_id, recorded_at)`**
- 作用：按传感器+时间查询、以及"删 180 天前"的删除都走索引，避免全表扫描。
- 建索引 SQL：
  ```sql
  CREATE INDEX idx_sensor_data_sensor_time ON sensor_data(sensor_id, recorded_at);
  ```
- 该索引对现有小数据量、以及未来几十万~几百万行都足够。

**b) `sensor_data` 增加可选异常来源标记列（`source_mark`）**
用于区分"采集点正常数据 / 采集点异常数据 / 非采集点异常(补记/拟制)"：
```sql
ALTER TABLE sensor_data ADD COLUMN source_mark VARCHAR(16) DEFAULT 'normal';
-- 取值：normal | abnormal | derived
```
| 取值 | 含义 |
|---|---|
| `normal` | 正常采集点数据 |
| `abnormal` | 该采集点本身值越过阈值（告警源数据） |
| `derived` | 因"异常但不在采集点"而由系统补记/拟制的记录 |

> 说明：若你认为不应把"非采集点异常"写进 `sensor_data`（因为它并非真实采集），可改用 **3.3 的独立异常留痕表**，二者可同时使用：`sensor_data` 只放真实采集点，异常留痕单独成表。

**c) 新增"异常且不在采集点"留痕表 `sensor_anomaly_gap`（推荐）**
专门记录"两采集点之间发生异常、但采集点无记录"的事件，独立于正常时序，便于审计/展示，不污染报表口径：
```sql
CREATE TABLE sensor_anomaly_gap (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  sensor_id     INTEGER NOT NULL REFERENCES sensors(id) ON DELETE CASCADE,
  detected_at   DATETIME NOT NULL,          -- 检测/发现时刻
  window_start  DATETIME,                   -- 覆盖的时间窗起（如上一采集点）
  window_end    DATETIME,                   -- 覆盖的时间窗止（如下一采集点）
  anomaly_type  VARCHAR(32),                -- 如 threshold/offline/missing_point
  expected_value FLOAT,                     -- 如该时刻理论/插值估计值（可选）
  actual_state  VARCHAR(64),                -- 描述（可选）
  severity      VARCHAR(16) DEFAULT 'warning',  -- info/warning/emergency
  remark        TEXT,                       -- 备注/人工确认
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
-- 推荐索引
CREATE INDEX idx_anomaly_gap_sensor_time ON sensor_anomaly_gap(sensor_id, detected_at);
```
- 该表同样纳入 180 天保留清理。
- 相比写入 `sensor_data` 的优点：不虚构采集数据、可独立查询、不破坏告警/统计口径。

### 3.3 检测与标记的触发时机
在**采集写入路径 `record_data()`** 及**可选的一个轻量巡检任务**中触发：

1. 正常采集点写入 `sensor_data`（`source_mark='normal'`）。
2. 若该值越过该传感器阈值（由 `sensors.threshold_min/threshold_max` 判定），则标记该条 `source_mark='abnormal'`（现有告警逻辑 `alerts` 仍并行工作）。
3. **"异常但不在采集点"**：当发现
   - 某传感器下一采集点的时间间隔明显大于预期（缺点了），或
   - 从其它信号/上报判定"两采集点之间存在异常而在采集点未体现"，
   则向 `sensor_anomaly_gap` 写入一条留痕（`anomaly_type` 区分），不改写正常数据。
4. 异常留痕与告警的关系：`sensor_anomaly_gap` 属于**留痕/说明**，`alerts` 属于**告警事件**，二者互补。

---

## 4. 180 天保留 & 滚动清理

### 4.1 保留策略（建议，按表分类）
| 表 | 保留期 | 说明 |
|---|---|---|
| `sensor_data` | **180 天** | 到期删除原始点 |
| `sensor_anomaly_gap` | **180 天** | 异常留痕与数据同周期 |
| `alerts` / `alert_actions` | **>180 天（建议长期）** | 告警审计，量小 |
| `audit_logs` / `login_logs` | 180~365 天（可配） | 合规类 |
| `chat_messages` | 180 天（可配） | 非必须 |
| 工单/巡检/设备台账 | 长期 | 业务记录，不受影响 |

> 用户明确"传感器数据 180 天"为核心；其余表提供**可配置开关**，默认按上表执行，避免误伤业务数据。

### 4.2 清理任务（每日，声明式 TTL 的 SQLite 实现）
- 新增后台定时任务（每日一次，可参考现有并发/lifespan 机制或独立脚本 + 系统计划任务）。
- 核心 SQL：
  ```sql
  DELETE FROM sensor_data
   WHERE recorded_at < datetime('now','-180 days');
  DELETE FROM sensor_anomaly_gap
   WHERE detected_at < datetime('now','-180 days');
  ```
- 执行要点：
  - 建议按 `recorded_at < now-183天`（留 3 天安全余量），避免时区/闰秒边界误删刚好满 180 天的数据。
  - 删除走 `(sensor_id, recorded_at)` 索引，量不大，秒级完成。
  - 每次执行记录清理行数与耗时到日志/审计表，便于核查"确实保留满 180 天"。
- 缺省频率：每小时采集 → 每天删除约 1,680 行，无压力。

### 4.3 保底（防止任务未运行导致无限增长）
- 若定时任务长期未执行，180 天数据会积累。建议：
  - 在**启动时（lifespan）**也触发一次"补齐清理"（幂等），保证即使定时器挂了，每次重启也会回收超期数据。
  - 记录"最后一次清理时间"，可在管理界面查看。

---

## 5. 兼容性与迁移

- 现有 `data/managesys.db` 为 SQLite，改动通过已有的 `_ensure_columns()` 幂等迁移机制（`main.py`）补齐：
  - `ALTER TABLE sensor_data ADD COLUMN source_mark ...`
  - `CREATE INDEX IF NOT EXISTS idx_sensor_data_sensor_time ...`
  - `CREATE TABLE IF NOT EXISTS sensor_anomaly_gap ...`
- 均可重复执行、不影响存量数据；老数据统一回填 `source_mark='normal'`（默认）。
- 新增模型 `SensorAnomalyGap` 注册到 `Base.metadata` 即可。

---

## 6. 落地步骤（建议顺序）

1. **模型与迁移**：新增 `sensor_data.source_mark`、`sensor_anomaly_gap` 表、(sensor_id, recorded_at) 索引；接入 `_ensure_columns`。
2. **写入改造**：`record_data()` 判定阈值并写 `source_mark`；缺点/异状触发异常留痕写入。
3. **清理任务**：新建 `service：data_retention.py`，提供 `run_retention(days=180)`；接入每日定时 + 启动时兜底。
4. **保留期可配置**：`core/config.py` 增加 `DATA_RETENTION_DAYS=180`、各表开关。
5. **查询/展示**：历史曲线接口按需标注 `source_mark` 与异常留痕；管理页展示最后清理时间与数量。
6. **测试**：索引生效、180 天边界删除、异常标记三类 source、非采集点异常留痕、幂等迁移。

---

## 7. 待确认项

1. **"异常且不在采集点"的标准定义**：是指①该传感器在应有时刻**缺勤/没上报**（缺失点），还是②检测到两次采集之间发生了越阈值等异常但采集点总是正常值？两者检测逻辑不同，需要明确（本设计已兼容并用 `anomaly_type` 区分，但你要确认口径）。
2. **异常留痕落库方式**：独立表 `sensor_anomaly_gap`（推荐，不污染报表） vs 写入 `sensor_data` 的 `derived` 标记 —— 选哪种？
3. **告警与留痕的关系**：现有的 `alerts` 告警是否继续独立工作、异常留痕仅作补充说明？（建议：互补）
4. **清理执行方式**：每日内部定时（进程内）vs 外部系统计划任务脚本 —— 选哪种部署形态？
5. **聚合/降采样**：本频率下不需要；是否仍要预留（如未来分钟级）以便无缝升级？

---

## 8. 规模升级预案（本次不实施，仅记录）

若未来频率提升（分钟/秒级）或传感器上千台，180 天数据进入数亿行：
- 将 `sensor_data` 迁至 **TimescaleDB**（`drop_chunks` + continuous aggregates）或 **ClickHouse**（`TTL + 降采样`），与 Zabbix 的 history/trends 双轨模型一致。
- 业务读写通过 service 层隔离，迁移只改存储后端，前端/接口不变。

---

## 9. 落地状态（已实现）

> 以下已按确认口径（两采集点之间越阈、但采集点总为正常值 → 独立表 + 进程内每日定时 + 与告警互补）完成落地：

- **模型/迁移**：sensor_data.source_mark(normal/abnormal)、独立表 sensor_anomaly_gap、索引 idx_sensor_data_sensor_time 与 idx_anomaly_gap_sensor_time 已接入 _ensure_columns 并在真实库生效。
- **写入改造**：ecord_data() 判定阈值并写 source_mark；新服务 sensor_anomaly_service.py 以传感器告警为信号检测"两采集点之间越阈、采集点正常"并写独立表，按 alert_id 幂等去重。
- **清理任务**：进程内每日定时（启动即跑一次兜底 + 每 24h 一次），按 DATA_RETENTION_DAYS=180 + BUFFER 3天 滚动清理 sensor_data 与 sensor_anomaly_gap。
- **配置**：core/config.py 新增 DATA_RETENTION_DAYS/BUFFER/EXPECTED_INTERVAL/GAP_TOLERANCE/TASK_ENABLED。
- **接口**：GET /sensors/anomaly-gaps（device:view）查看留痕；POST /sensors/retention（仅 super_admin）手动触发清理。
- **测试**：	est_sensor_retention.py 4 项测试通过；后端共 **107 passed**。
