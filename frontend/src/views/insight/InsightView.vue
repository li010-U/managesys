<template>
  <div class="insight-view">
    <div class="page-header">
      <div class="title">
        <h2>AI 智能分析</h2>
        <span class="sub">自学习基线 · 趋势预测 · 容量规划 · 可靠性 · 告警根因 · AI 巡检</span>
      </div>
      <div class="header-actions">
        <el-select v-model="selectedRoomId" placeholder="选择机房" clearable style="width: 220px" @change="onRoomChange">
          <el-option v-for="r in rooms" :key="r.id" :label="roomLabel(r)" :value="r.id" />
        </el-select>
        <el-button type="primary" :loading="globalLoading" @click="reloadAll">刷新</el-button>
      </div>
    </div>

    <div class="cards">
      <div class="card">
        <div class="card-label">系统可用率</div>
        <div class="card-value">{{ fmtPct(reliability.availability_pct) }}</div>
        <div class="card-extra">{{ reliability.alert_count }} 条告警 / 近 {{ reliability.days }} 天</div>
      </div>
      <div class="card">
        <div class="card-label">平均修复时长 MTTR</div>
        <div class="card-value">{{ reliability.avg_mttr_hours ?? '--' }}<small>h</small></div>
        <div class="card-extra">预估故障 {{ reliability.estimated_outage_hours ?? '--' }}h</div>
      </div>
      <div class="card">
        <div class="card-label">紧急 / 严重告警</div>
        <div class="card-value">{{ reliability.emergency_count }} / {{ reliability.serious_count }}</div>
        <div class="card-extra">告警总量 {{ reliability.alert_count }}</div>
      </div>
      <div class="card">
        <div class="card-label">频发对象类型</div>
        <div class="card-value ellipsis">{{ reliability.top_failure_target_type || '--' }}</div>
        <div class="card-extra">按 MTBF 排序</div>
      </div>
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-header">
              <span>自学习基线（按时段 IQR）</span>
              <el-select v-model="baselineSensorId" placeholder="选择传感器" filterable size="small" style="width: 210px" @change="loadBaseline">
                <el-option v-for="s in tempSensors" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </div>
          </template>
          <el-alert v-if="baseline?.assessment" :title="baseline.assessment.msg" :type="baselineAlertType" :closable="false" show-icon style="margin-bottom: 8px" />
          <div ref="baselineChartEl" class="chart"></div>
          <div v-if="baseline && baseline.samples === 0" class="empty">暂无历史数据</div>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-header">
              <span>短时趋势预测</span>
              <el-select v-model="forecastSensorId" placeholder="选择传感器" filterable size="small" style="width: 210px" @change="loadForecast">
                <el-option v-for="s in tempSensors" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </div>
          </template>
          <el-alert v-if="forecast?.direction" title="预测提示" :description="forecastHint" type="info" :closable="false" show-icon style="margin-bottom: 8px" />
          <div ref="forecastChartEl" class="chart"></div>
          <div v-if="forecast && forecast.forecast === null" class="empty">历史数据不足，无法预测</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card shadow="never" class="panel">
          <template #header><span>机柜容量规划</span></template>
          <el-table :data="capacity.racks || []" size="small" max-height="380" stripe>
            <el-table-column prop="rack_code" label="机柜" width="170" />
            <el-table-column label="U位" width="90">
              <template #default="{ row }">{{ row.used_units }}/{{ row.total_units }}</template>
            </el-table-column>
            <el-table-column label="U位利用率" min-width="140">
              <template #default="{ row }">
                <el-progress :percentage="row.utilization_pct" :stroke-width="8" :color="utilColor(row.utilization_pct)" />
              </template>
            </el-table-column>
            <el-table-column prop="power_used_kw" label="功率kW" width="80" />
            <el-table-column label="功率趋势" min-width="150">
              <template #default="{ row }">
                <div class="trend-value">{{ row.power_trend_kw ?? row.power_used_kw }} kW</div>
                <div v-if="row.power_growth_monthly_kw" class="trend-sub">月增 {{ fmtKw(row.power_growth_monthly_kw) }}</div>
              </template>
            </el-table-column>
            <el-table-column label="供电负载" min-width="140">
              <template #default="{ row }">
                <el-progress :percentage="row.power_util_pct" :stroke-width="8" :color="utilColor(row.power_util_pct)" />
              </template>
            </el-table-column>
            <el-table-column label="满载预估" width="150">
              <template #default="{ row }">
                <div>{{ row.estimate_full_date || '--' }}</div>
                <div v-if="row.estimate_is_estimate" class="est-note">无历史，经验估算</div>
                <div v-else-if="row.monthly_growth_units" class="est-note">月增{{ row.monthly_growth_units }}U</div>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-if="!capacity.racks?.length" description="暂无机柜数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="10">
        <el-card shadow="never" class="panel">
          <template #header><span>告警根因关联</span></template>
          <div v-if="correlate">
            <div class="correlate-summary">
              开放告警 <b>{{ correlate.active_alert_count }}</b> 条 · 温度 {{ correlate.temperature_count }} · 湿度 {{ correlate.humidity_count }} · 功率 {{ correlate.power_count }}
            </div>
            <el-alert v-if="correlate.root_cause_hint" :title="correlate.root_cause_hint" type="warning" :closable="false" show-icon style="margin-top: 8px" />
            <div class="correlate-list">
              <div v-for="level in ['emergency','serious','general']" :key="level">
                <div v-if="(correlate.by_level?.[level] || []).length" class="correlate-level">{{ levelLabel(level) }}</div>
                <el-tag v-for="a in (correlate.by_level?.[level] || []).slice(0, 8)" :key="a.id" size="small" :type="levelTagType(level)" class="correlate-tag">
                  {{ a.title }}<b v-if="a.occurrences > 1"> ×{{ a.occurrences }}</b>
                </el-tag>
              </div>
            </div>
          </div>
          <el-empty v-else description="选择机房后查看" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="panel-header">
              <span>AI 辅助巡检清单</span>
              <el-button size="small" :loading="inspLoading" @click="loadInspection">生成清单</el-button>
            </div>
          </template>
          <el-empty v-if="!inspection?.found" description="选择机房后生成" :image-size="80" />
          <template v-else>
            <div class="inspection-meta">机房 {{ inspection.room_name }} · 近 {{ inspection.days }} 天 · {{ inspection.clue_count }} 条线索</div>
            <div v-if="inspection.llm_note" class="llm-note">🤖 {{ inspection.llm_note }}</div>
            <el-timeline v-if="inspection.checklist?.length">
              <el-timeline-item v-for="c in inspection.checklist" :key="c.title" :type="timelineType(c.priority)">
                <div class="check-item">
                  <el-tag size="small" :type="tagType(c.priority)">{{ c.priority }}</el-tag>
                  <span class="check-title">{{ c.title }}</span>
                  <span v-if="c.occurrences > 1" class="occ">×{{ c.occurrences }}</span>
                </div>
              </el-timeline-item>
            </el-timeline>
          </template>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="panel">
          <template #header><span>数据追溯查询</span></template>
          <div class="trace-search">
            <el-input v-model="traceQuery" placeholder="如：某设备上周为何告警 / 最近一周告警 / 同类故障Top5" clearable @keyup.enter="runTrace">
              <template #append><el-button :loading="traceLoading" @click="runTrace">查询</el-button></template>
            </el-input>
          </div>
          <template v-if="trace">
            <div class="trace-meta">命中 {{ trace.matched }} 条（{{ trace.since }} 起）</div>
            <div v-if="trace.top_recurrent_titles?.length" class="trace-section">
              <div class="trace-section-title">同类复发 Top</div>
              <el-tag v-for="t in trace.top_recurrent_titles.slice(0, 6)" :key="t.title" size="small" class="correlate-tag">{{ t.title }}<b> ×{{ t.count }}</b></el-tag>
            </div>
            <el-table :data="trace.alerts" size="small" max-height="280" stripe>
              <el-table-column prop="title" label="告警" min-width="160" show-overflow-tooltip />
              <el-table-column label="级别" width="70">
                <template #default="{ row }"><el-tag size="small" :type="levelTagType(row.level)">{{ levelLabel(row.level) }}</el-tag></template>
              </el-table-column>
              <el-table-column label="状态" width="80">
                <template #default="{ row }"><el-tag size="small" :type="statusTagType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
              </el-table-column>
              <el-table-column prop="created_at" label="时间" width="155" />
            </el-table>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from "vue"
import echarts from "../../lib/echarts"
import { getAllRoomsApi, type RoomInfo } from "../../api/facility"
import { getAllSensorsApi, type SensorInfo } from "../../api/sensor"
import {
  getSensorBaselineApi, getSensorForecastApi, getRackCapacityApi, getReliabilityApi,
  getCorrelateRoomApi, getInspectionChecklistApi, getAlertTraceApi,
  type BaselineResult, type ForecastResult, type CapacityResult, type ReliabilityResult,
  type InspectionChecklist, type TraceResult,
} from "../../api/insight"

const rooms = ref<RoomInfo[]>([])
const selectedRoomId = ref<number | undefined>(undefined)
const tempSensors = ref<SensorInfo[]>([])
const globalLoading = ref(false)

const reliability = ref<ReliabilityResult>({ days: 90, alert_count: 0, emergency_count: 0, serious_count: 0, avg_mttr_hours: null, availability_pct: 100, estimated_outage_hours: 0, device_health: [], type_health: [] })
const capacity = ref<CapacityResult>({ count: 0, racks: [], room_id: null })
const correlate = ref<any>(null)
const inspection = ref<InspectionChecklist>({ found: false })
const inspLoading = ref(false)

const baselineSensorId = ref<number>(0)
const forecastSensorId = ref<number>(0)
const baseline = ref<BaselineResult | null>(null)
const forecast = ref<ForecastResult | null>(null)

const traceQuery = ref("")
const trace = ref<TraceResult | null>(null)
const traceLoading = ref(false)

const baselineChartEl = ref<HTMLElement>()
const forecastChartEl = ref<HTMLElement>()
let baselineChart: echarts.ECharts | null = null
let forecastChart: echarts.ECharts | null = null

const baselineAlertType = computed(() => {
  const s = baseline.value?.assessment?.status
  return s === "high" ? "error" : s === "low" ? "warning" : "success"
})
const forecastHint = computed(() => {
  const d = forecast.value?.direction
  const f = forecast.value?.forecast
  if (!f?.length) return ""
  return `${d === "up" ? "预计上升" : d === "down" ? "预计下降" : "预计平稳"}至约 ${f[f.length - 1].value}`
})

function roomLabel(r: RoomInfo) { return `${r.name} (${r.code || ""})` }
function levelLabel(l: string) { return ({ general: "一般", serious: "严重", emergency: "紧急" } as any)[l] || l }
function levelTagType(l: string) { return l === "emergency" ? "danger" : l === "serious" ? "warning" : "info" }
function statusLabel(s: string) { return ({ new: "待处理", acknowledged: "已确认", resolved: "已解决", ignored: "已忽略" } as any)[s] || s }
function statusTagType(s: string) { return s === "new" ? "danger" : s === "acknowledged" ? "warning" : s === "resolved" ? "success" : "info" }
function utilColor(p: number) { return p >= 80 ? "#f56c6c" : p >= 60 ? "#e6a23c" : "#67c23a" }
function tagType(p: string) { return p === "高" ? "danger" : p === "中" ? "warning" : "info" }
function timelineType(p: string) { return p === "高" ? "danger" : p === "中" ? "warning" : "primary" }
function fmtPct(v: any) { return v === null || v === undefined ? "--" : Number(v).toFixed(2) + "%" }
function fmtKw(v: any) { const n = Number(v); return isNaN(n) ? "--" : n.toFixed(2) + " kW" }

async function loadRooms() {
  try { const rr = await getAllRoomsApi(); rooms.value = rr.data || [] } catch { rooms.value = [] }
}
async function loadSensors(roomId?: number) {
  try { const sr = await getAllSensorsApi({ room_id: roomId }); tempSensors.value = sr.data || [] } catch { tempSensors.value = [] }
  if (tempSensors.value.length) {
    if (!baselineSensorId.value) baselineSensorId.value = tempSensors.value[0].id
    if (!forecastSensorId.value) forecastSensorId.value = tempSensors.value[0].id
    loadBaseline()
    loadForecast()
  }
}
async function onRoomChange() {
  loadRoomScoped()
}
async function loadRoomScoped() {
  const roomId = selectedRoomId.value
  loadSensors(roomId)
  loadCapacity(roomId)
  loadReliability(roomId)
  if (roomId) {
    loadCorrelate(roomId)
    loadInspection()
  } else {
    correlate.value = null
    inspection.value = { found: false }
  }
}
async function loadReliability(roomId?: number) {
  try { const rl = await getReliabilityApi(roomId, selectedRoomId.value ? 90 : 90); reliability.value = rl.data } catch { /* ignore */ }
}
async function loadCapacity(roomId?: number) {
  try { const cp = await getRackCapacityApi(roomId); capacity.value = cp.data } catch { /* ignore */ }
}
async function loadCorrelate(roomId: number) {
  try { const co = await getCorrelateRoomApi(roomId); correlate.value = co.data } catch { correlate.value = null }
}
async function loadInspection() {
  if (!selectedRoomId.value) return
  inspLoading.value = true
  try { const ic = await getInspectionChecklistApi(selectedRoomId.value, 7); inspection.value = ic.data } catch { inspection.value = { found: false } }
  finally { inspLoading.value = false }
}
async function loadBaseline() {
  if (!baselineSensorId.value) return
  try {
    const bl = await getSensorBaselineApi(baselineSensorId.value, 30); baseline.value = bl.data
    await nextTick()
    renderBaseline()
  } catch { baseline.value = null }
}
async function loadForecast() {
  if (!forecastSensorId.value) return
  try {
    const fc = await getSensorForecastApi(forecastSensorId.value, 120, 6); forecast.value = fc.data
    await nextTick()
    renderForecast()
  } catch { forecast.value = null }
}
async function runTrace() {
  if (!traceQuery.value.trim()) return
  traceLoading.value = true
  try { const tr = await getAlertTraceApi(traceQuery.value.trim(), 20); trace.value = tr.data }
  catch { trace.value = null }
  finally { traceLoading.value = false }
}
async function reloadAll() {
  globalLoading.value = true
  try {
    await loadRooms()
    await loadRoomScoped()
  } finally { globalLoading.value = false }
}

function renderBaseline() {
  const el = baselineChartEl.value
  if (!el) return
  if (!baselineChart) baselineChart = echarts.init(el)
  const slots = baseline.value?.baseline ? Object.values(baseline.value.baseline) : []
  const hours = slots.map((s) => s.hour + ":00")
  const means = slots.map((s) => s.mean)
  const lows = slots.map((s) => s.low)
  const highs = slots.map((s) => s.high)
  baselineChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["均值", "正常区间"], top: 0 },
    grid: { left: 45, right: 15, top: 30, bottom: 25 },
    xAxis: { type: "category", data: hours, name: "时段" },
    yAxis: { type: "value", name: "数值" },
    series: [
      { name: "均值", type: "line", data: means, smooth: true, lineStyle: { width: 2 } },
      { name: "正常区间", type: "line", data: lows, lineStyle: { type: "dashed", opacity: 0.3 }, symbol: "none" },
      { name: "正常区间", type: "line", data: highs, lineStyle: { type: "dashed", opacity: 0.3 }, symbol: "none", areaStyle: { opacity: 0.08 } },
    ],
  }, true)
}
function renderForecast() {
  const el = forecastChartEl.value
  if (!el) return
  if (!forecastChart) forecastChart = echarts.init(el)
  const his = forecast.value?.history || []
  const times = his.map((h) => h.ts?.slice(11, 16) || "")
  const vals = his.map((h) => h.value)
  const f = forecast.value?.forecast || []
  const fTimes = f.map(() => "未来")
  const fVals = f.map((p) => p.value)
  const fLow = f.map((p) => p.low)
  const fHigh = f.map((p) => p.high)
  forecastChart.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["历史", "预测", "预测区间"], top: 0 },
    grid: { left: 45, right: 15, top: 30, bottom: 25 },
    xAxis: { type: "category", data: [...times, ...fTimes] },
    yAxis: { type: "value", name: "数值" },
    series: [
      { name: "历史", type: "line", data: vals, smooth: true, lineStyle: { width: 2 } },
      { name: "预测", type: "line", data: [...vals.slice(-1), ...fVals], smooth: true, lineStyle: { width: 2, type: "dashed" }, itemStyle: { color: "#e6a23c" } },
      { name: "预测区间", type: "line", data: [...vals.slice(-1), ...fHigh], symbol: "none", lineStyle: { type: "dashed", opacity: 0.2 } },
      { name: "预测区间", type: "line", data: [...vals.slice(-1), ...fLow], symbol: "none", lineStyle: { type: "dashed", opacity: 0.2 }, areaStyle: { opacity: 0.05 } },
    ],
  }, true)
}

function handleResize() {
  baselineChart?.resize()
  forecastChart?.resize()
}

onMounted(async () => {
  await loadRooms()
  await reloadAll()
  window.addEventListener("resize", handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize)
  baselineChart?.dispose()
  forecastChart?.dispose()
})
</script>

<style scoped>
.insight-view { padding: 4px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 8px; }
.title h2 { margin: 0; font-size: 20px; }
.sub { color: #909399; font-size: 13px; margin-left: 8px; }
.header-actions { display: flex; gap: 8px; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 16px; }
.card { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 16px; }
.card-label { color: #909399; font-size: 13px; margin-bottom: 8px; }
.card-value { font-size: 26px; font-weight: 600; }
.card-value small { font-size: 14px; color: #909399; font-weight: 400; margin-left: 2px; }
.card-extra { color: #909399; font-size: 12px; margin-top: 6px; }
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.panel { margin-bottom: 16px; }
.panel-header { display: flex; justify-content: space-between; align-items: center; }
.chart { height: 300px; }
.empty { text-align: center; color: #909399; padding: 20px 0; }
.correlate-summary { font-size: 14px; color: #303133; }
.correlate-list { margin-top: 8px; }
.correlate-level { font-size: 13px; color: #909399; margin: 8px 0 4px; }
.correlate-tag { margin: 0 6px 6px 0; }
.trend-value { font-weight: 600; color: #303133; }
.trend-sub { font-size: 12px; color: #909399; }
.est-note { font-size: 11px; color: #b88230; margin-top: 2px; }
.trace-meta { color: #909399; font-size: 12px; margin: 8px 0; }
.trace-section { margin-bottom: 8px; }
.trace-section-title { font-size: 13px; color: #909399; margin-bottom: 4px; }
.inspection-meta { color: #909399; font-size: 13px; margin-bottom: 10px; }
.llm-note { background: #f0f9eb; border: 1px solid #e1f3d8; color: #529b2e; padding: 8px 12px; border-radius: 6px; margin-bottom: 10px; font-size: 13px; }
.check-item { display: flex; align-items: center; gap: 8px; }
.check-title { font-size: 14px; }
.occ { color: #e6a23c; font-size: 12px; }
@media (max-width: 1200px) { .cards { grid-template-columns: repeat(2, 1fr); } }
</style>