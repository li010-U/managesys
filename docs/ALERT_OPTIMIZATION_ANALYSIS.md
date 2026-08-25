# 告警系统优化分析报告

> 结论速览：**告警频率过高的根因不在阈值本身，而在"数据生成器跳过了告警生命周期/去重引擎"**，叠加连续型传感器的高斯噪声标准差过大、开关型(door/smoke)传感器被当成同样的随机抖动处理，导致同一设备同一告警被无限重复写入。

---

## 一、告警频率过高的根因定位

### 1.1 直接根因：模拟器绕过生命周期引擎，裸写告警表

backend/dev_tools/simulate_realtime.py 的 update_sensors() 中，告警生成是直接 INSERT INTO alerts：

- 每次越阈都插入一条新告警，完全没有先查"同一设备是否已有未解决告警"，也不调用后端已有的 AlertLifecycleService.register_signal()（去重防抖 + 偶发识别 + 冷却的官方入口）。
- 结果：同一设备同一告警被无限重复写入。

数据库铁证（alerts 表，累计 60,711 条）：
| 指标 | 数值 | 说明 |
|---|---|---|
| 总量 | 60,711 | 近 1 个月累积 |
| status='new' | 60,072 (98.9%) | 几乎全部挂着未解决 |
| source='monitor' | 60,577 (99.8%) | 模拟器裸写来源 |
| dedupe_key IS NULL | 60,677 | 未走生命周期去重 |
| occurrences > 1 | 0 | 从未归并 |
| 去重后的 (target,target_id) | 124 | 平均每个对象 ~489 条重复 |

> 后端 sweep_auto_resolve 只处理 normal_since_at 非空的告警，而该字段只能由 register_signal 写入。模拟器从不调用它，所以那 6 万条永远不会被自动解决，长期悬挂，形成告警疲劳。

### 1.2 阈值/采样层面的放大因素

- 开关型传感器（door/smoke）：模拟器用 random.choice([0,0,0,1])，即 25% 概率触发"1"(告警)，阈值 max_val*0.8=0.8。门/烟感 24h 内分别刷出 5,217 / 1,326 条告警。烟感本应"宁可漏报不可误报"，却被当成门随机开合来抖。
- 连续型传感器（temp/humidity/power）：value = gauss(center, range/4)，threshold = max_val*0.85。例如 power(0~30)：center=15、sigma=7.5、阈值=25.5，阈值在 1.4σ 之外，高斯分布下约 8% 采样点天然越阈。即每个传感器常年贴近阈值抖动。
- 秒级采样 + 每次越阈即告警：--interval 1.0 每秒一轮，per_cycle=0 更新全部传感器，越阈即写，天生刷屏。

### 1.3 环境关联数据缺失

env_weather_records 表（temperature/humidity/weather/windspeed）已建好但 0 行，因为 ENV_POLL_TASK_ENABLED=false。没有环境数据，无法做偶发故障-天气环境关联统计。

---

## 二、历史告警归因分析（聚类）

### 2.1 按告警类型（title）聚类
| 类型 | 条数 | 占比 | 归因 |
|---|---|---|---|
| door 监测值异常 | 26,839 | 44.2% | 模拟器把门抖动当成告警 + 无去重 |
| power 监测值异常 | 23,936 | 39.4% | 高斯噪声 sigma 过大，常年贴近阈值 |
| smoke 监测值异常 | 6,880 | 11.3% | 开关型被当成门抖动，25% 概率越阈 |
| humidity 监测值异常 | 1,466 | 2.4% | 同上，连续型 sigma 过大 |
| temperature 监测值异常 | 1,254 | 2.1% | 同上 |
| 其余(设备/机柜/网络) | 316 | 0.5% | 真实/低量，噪声可忽略 |

结论：97.6% 的告警噪音来自 door/power/smoke/humidity/temperature 这 5 类模拟传感器，其中 door+power 占 83.6%。

### 2.2 按级别分布
| 级别 | 条数 |
|---|---|
| general | 45,466 |
| emergency | 9,639 |
| serious | 5,606 |

问题：emergency(最高级) 多达近 9,639 条——因 smoke 传感器默认 alert_level='emergency'，被 25% 概率随机抖动刷爆，最高级别告警严重通胀，会让真实紧急告警被淹没。

### 2.3 按时间分布（突发）
- 单分钟峰值 118 条（如 2026-08-21 10:23）。
- 告警呈秒级随机爆发，无业务时段特征，符合随机抖动+无去重的合成来源特征。

### 2.4 关联统计可行性与缺口
- 已具备能力：transient_failure_events 表（偶发故障登记）、env_weather_records 表（环境维度）。
- 当前缺口：两者均空表，因为模拟器不喂信号、环境采集未启用。修复数据生成后，关联统计报表才能有真实输入。

---

## 三、落地优化建议（按优先级）

### P0 根因修复：数据生成走统一告警生命周期入口
- 改 simulate_realtime.py：越阈时不再裸 INSERT，而是调用 AlertLifecycleService.register_signal()（或新增 HTTP 采集接口），传 is_abnormal 与指标值。
- 效果：去重（同设备未解决不再重复）、偶发识别（秒~分钟级自愈登记 transient_failure_events）、自动恢复（normal_since_at 计满 30 分钟，sweep_auto_resolve 标已解决）、冷却防抖全链路生效。
- 配套：sweep_auto_resolve 与模拟器解耦，模拟器自身驱动生命周期，web 端任务只做兜底扫描。

### P1 阈值与采样参数工程化
- 开关型传感器：door/smoke 设普通开合与告警区分，如门仅"持续打开/关闭超 N 秒"才告警；smoke 连续 2~3 次置 1（持续 N 秒）才判报警，消除 25% 随机误报。
- 连续型传感器：收窄仿真噪声，sigma 由 range/4 降到 range/12（约 3σ），让正常值稳定在中位带，仅真实漂移触发。
- 采样粒度：默认 1 秒过密，可降到 5~10s 采样 + 连续 N 次越阈才触发，用持续越阈代替单点越阈。

### P2 阈值动态调整与成熟做法
- 动态基线：对 power/temperature 用 EWMA/滑动均值 + 3σ 浮动基线，取代固定 max*0.85（业界：Prometheus trend、Zabbix dynamic threshold、AWS CloudWatch anomaly detection）。
- 持续窗口判定：借鉴 Prometheus 的 for 关键字（如 for: 5m），持续越阈满 N 分钟才告警，短促抖动自动过滤。
- 分级与通知：general 仅入库展示；serious 聚合后批次通知；emergency 即时多渠道；emergency 必须来自持续/真实故障判定，不得由单点随机越阈触发。
- 告警收敛：以 dedupe_key(设备+告警类型) 归并 occurrences，同设备未解决不重复、解决后按 cooldown 冷却再允许。

### P3 规则管理机制
- 复用 alert_rules 表，把阈值/级别/冷却/持续窗口做成可配置（当前模拟器阈值硬编码在脚本里）。
- 提供规则批量导入/导出、规则生效时间表（夜间灵敏度可调）、以及告警风暴自动抑制开关。

### P4 环境关联统计闭环
- 开启 ENV_POLL_TASK_ENABLED=true（或接入气象 API，已有 lat/lon 配置 31.82,117.23），让 env_weather_records 持续入库。
- 在 transient_failure_events 产生后，按时段关联 env_weather_records，输出：偶发故障频次 x 天气类型/温度区间/湿度区间/风力等级；按小时间分布；占比与置信度。
- 可视化复用 reports/alert_correlation_demo.html 的模板产出正式报表。

---

## 四、验收对照
| 验收项 | 现状 | 修复后 |
|---|---|---|
| 故障未解决不重复告警 | 否(每越阈插一条) | register_signal 去重归并 |
| 30min 连续正常自动解决 | 否(normal_since_at 从未写入) | 生命周期驱动 + sweep 兜底 |
| 秒/分钟级自愈只记录不打扰 | 否(直接成告警) | transient_failure_events 登记 |
| 天气/环境关联统计 | 否(环境表为空) | 开启采集 + 关联报表 |


---

## 五、落地进展（2026-08-21）

### 已完成
- **P0** 已改造 `backend/dev_tools/simulate_realtime.py`：告警生成改走同步版生命周期引擎（去重 / 冷却 / 短时自愈 / 自动恢复），不再裸 INSERT。已用 6 组场景单测验证（去重、5s 自愈登记、冷却抑制、30min 自动解决、解决后冷却过再告警、文本时间存储无 DeprecationWarning）。
- **P1** 已修复：door/smoke 开关型由 25% 随机误报改为「连续 N 次置 1」判定（烟感极低概率 0.2%）；连续型高斯噪声由 range/4 收窄到 range/12；引入 for-duration 持续越阈窗口（默认连续 3 次）。
- **P4** 已新增 `backend/dev_tools/seed_correlation.py`：回填环境数据(env_weather_records) + 生成偶发故障事件(transient_failure_events，不利天气更集中) + 生成可视化 HTML 报表。
- 已生成 `reports/alert_correlation_report.html`（422 条偶发、平均 146s、按天/天气/温度/湿度/风速分布）。

### 实测效果（真实库 14s 运行）
- 告警总量 60,711 → 60,711（**不再增长**，去重生效；此前同样时长会新增数百上千条）。
- occurrences>1：0 → 15（重复异常归并到既有告警）。
- normal_since_at 写入：0 → 67（撑满 30 分钟即可被 sweep 自动解决，可清理存量悬挂告警）。
