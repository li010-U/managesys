<template>
  <div class="monitor-dashboard">
    <!-- Page Header -->
    <div class="page-header">
      <div>
        <h3 class="page-title">可视化监控看板</h3>
        <p class="page-desc">数据中心环境监控数据可视化大屏，实时掌握机房运行状态</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" @click="refreshAll" :loading="loading">刷新数据</el-button>
      </div>
    </div>

    <!-- KPI Summary Cards -->
    <el-row :gutter="16" class="kpi-row">
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="kpi-card kpi-total">
          <div class="kpi-item">
            <div class="kpi-icon-box" style="background:#e3f2fd"><el-icon :size="24" color="#1976d2"><ColdDrink /></el-icon></div>
            <div class="kpi-info">
              <span class="kpi-num">{{ sensors.length }}</span>
              <span class="kpi-label">传感器总数</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="kpi-card kpi-online">
          <div class="kpi-item">
            <div class="kpi-icon-box" style="background:#e8f5e9"><el-icon :size="24" color="#27ae60"><Check /></el-icon></div>
            <div class="kpi-info">
              <span class="kpi-num">{{ onlineCount }}</span>
              <span class="kpi-label">在线</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="kpi-card kpi-alert">
          <div class="kpi-item">
            <div class="kpi-icon-box" style="background:#fef3e2"><el-icon :size="24" color="#e67e22"><Warning /></el-icon></div>
            <div class="kpi-info">
              <span class="kpi-num">{{ alertCount }}</span>
              <span class="kpi-label">告警中</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="6">
        <el-card shadow="never" class="kpi-card kpi-offline">
          <div class="kpi-item">
            <div class="kpi-icon-box" style="background:#fce4ec"><el-icon :size="24" color="#e74c3c"><Connection /></el-icon></div>
            <div class="kpi-info">
              <span class="kpi-num">{{ offlineCount }}</span>
              <span class="kpi-label">离线</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row 1: Pie + Bar -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :sm="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">传感器类型分布</span></template>
          <div ref="pieChartRef" class="chart-container" style="height:320px"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-card shadow="never" class="chart-card">
          <template #header><span class="chart-title">各机房传感器数量</span></template>
          <div ref="barChartRef" class="chart-container" style="height:320px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts Row 2: Line chart -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="24">
        <el-card shadow="never" class="chart-card">
          <template #header>
            <div class="line-chart-header">
              <span class="chart-title">传感器数据趋势</span>
              <el-select v-model="trendSensorId" placeholder="选择传感器" size="small" style="width:200px" @change="loadTrendData">
                <el-option v-for="s in sensors" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </div>
          </template>
          <div ref="lineChartRef" class="chart-container" style="height:320px"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Sensor List Table -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="table-header">
          <span class="chart-title">传感器清单</span>
          <el-input v-model="searchKeyword" placeholder="搜索传感器名称..." prefix-icon="Search" clearable size="small" style="width:240px" @input="applySearch" />
        </div>
      </template>
      <el-table :data="paginatedData" stripe border size="small" style="width:100%" v-loading="loading">
        <el-table-column prop="name" label="名称" min-width="120" />
        <el-table-column prop="code" label="编号" width="110" />
        <el-table-column prop="sensor_type" label="类型" width="80" :formatter="fmtType" />
        <el-table-column prop="room_name" label="所属机房" width="120" />
        <el-table-column label="当前值" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.current_value" :style="{ color: valueColor(row), fontWeight: 700 }">{{ row.current_value.value }}{{ unitText(row.sensor_type) }}</span>
            <span v-else style="color:#999">--</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 'online' ? 'success' : 'info'" size="small">{{ row.status === 'online' ? '在线' : '离线' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后更新" width="160" align="center">
          <template #default="{ row }">{{ row.last_update_time ? fmtTime(row.last_update_time) : '--' }}</template>
        </el-table-column>
        <el-table-column label="告警" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="isAlerting(row)" type="danger" size="small">告警</el-tag>
            <span v-else style="color:#999">正常</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredSensors.length"
        :page-sizes="[5, 10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        small
        style="margin-top:12px;justify-content:center"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from "vue"
import * as echarts from "echarts"
import { ElMessage } from "element-plus"
import { Refresh, Search, Warning, ColdDrink, Check, Connection } from "@element-plus/icons-vue"
import { getSensorsApi, getSensorDataApi, getAllSensorsApi } from "../../api/sensor"
import { getRoomsApi } from "../../api/facility"
import type { SensorInfo } from "../../api/sensor"

const loading = ref(false)
const sensors = ref<SensorInfo[]>([])
const rooms = ref<any[]>([])
const trendSensorId = ref<number | null>(null)
const searchKeyword = ref("")
const page = ref(1)
const pageSize = ref(10)

// Chart refs
const pieChartRef = ref<HTMLDivElement>()
const barChartRef = ref<HTMLDivElement>()
const lineChartRef = ref<HTMLDivElement>()

let pieChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null
let lineChart: echarts.ECharts | null = null

// Computed
const onlineCount = computed(() => sensors.value.filter(s => s.status === "online").length)
const offlineCount = computed(() => sensors.value.filter(s => s.status === "offline").length)
const alertCount = computed(() => sensors.value.filter(s => {
  if (!s.current_value) return false
  const v = s.current_value.value
  return (s.threshold_min != null && v < s.threshold_min) || (s.threshold_max != null && v > s.threshold_max)
}).length)

const filteredSensors = computed(() => {
  if (!searchKeyword.value) return sensors.value
  const kw = searchKeyword.value.toLowerCase()
  return sensors.value.filter(s => s.name.toLowerCase().includes(kw) || s.code.toLowerCase().includes(kw))
})

const paginatedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredSensors.value.slice(start, start + pageSize.value)
})

// Helper functions
function fmtType(_row: any, _col: any, val: string) {
  const map: Record<string, string> = { temperature: "温度", humidity: "湿度", smoke: "烟感", water: "水浸", door_magnetic: "门磁" }
  return map[val] || val
}
function unitText(type: string) {
  return ({ temperature: "°C", humidity: "%RH", smoke: "", water: "", door_magnetic: "" } as any)[type] || ""
}
function valueColor(s: SensorInfo): string {
  if (!s.current_value) return "#999"
  const v = s.current_value.value
  if (s.threshold_min != null && v < s.threshold_min) return "#3498db"
  if (s.threshold_max != null && v > s.threshold_max) return "#e74c3c"
  return "#27ae60"
}
function isAlerting(s: SensorInfo): boolean {
  if (!s.current_value) return false
  const v = s.current_value.value
  return (s.threshold_min != null && v < s.threshold_min) || (s.threshold_max != null && v > s.threshold_max)
}
function fmtTime(t: string) {
  try { const d = new Date(t); return d.getFullYear()+"/"+(d.getMonth()+1)+"/"+d.getDate()+" "+d.getHours().toString().padStart(2,"0")+":"+d.getMinutes().toString().padStart(2,"0") } catch { return t }
}
function applySearch() { page.value = 1 }

// Data fetching
async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([fetchSensors(), fetchRooms()])
    nextTick(() => updateAllCharts())
  } catch { ElMessage.error("数据加载失败") }
  finally { loading.value = false }
}

async function fetchSensors() {
  try {
    const r = await getAllSensorsApi()
    sensors.value = r.data || []
  } catch { sensors.value = [] }
}

async function fetchRooms() {
  try {
    const r = await getRoomsApi({ page: 1, page_size: 100 })
    rooms.value = r.data.items || []
  } catch { rooms.value = [] }
}

async function loadTrendData() {
  if (!trendSensorId.value) { updateLineChart([]); return }
  try {
    const r = await getSensorDataApi(trendSensorId.value, 30)
    updateLineChart(r.data || [])
  } catch { updateLineChart([]) }
}

// Charts
function updateAllCharts() {
  updatePieChart()
  updateBarChart()
  if (trendSensorId.value) loadTrendData()
  else updateLineChart([])
}

function updatePieChart() {
  if (!pieChart) return
  const types = ["temperature","humidity","smoke","water","door_magnetic"]
  const names = ["温度","湿度","烟感","水浸","门磁"]
  const colors = ["#e74c3c","#3498db","#e67e22","#9b59b6","#2ecc71"]
  const data = types.map((t, i) => ({
    name: names[i],
    value: sensors.value.filter(s => s.sensor_type === t).length,
    itemStyle: { color: colors[i] }
  })).filter(d => d.value > 0)

  pieChart.setOption({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { bottom: 0, textStyle: { fontSize: 11 } },
    series: [{
      type: "pie", radius: ["35%", "60%"], center: ["50%", "45%"],
      avoidLabelOverlap: true,
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: "bold" } },
      data
    }]
  }, true)
}

function updateBarChart() {
  if (!barChart) return
  const roomNames = rooms.value.map(r => r.name)
  const roomCounts = rooms.value.map(r => sensors.value.filter(s => s.room_id === r.id).length)

  barChart.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 40, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: roomNames.length ? roomNames : ["暂无数据"], axisLabel: { fontSize: 11 } },
    yAxis: { type: "value", minInterval: 1 },
    series: [{
      type: "bar", data: roomCounts.length ? roomCounts : [0],
      itemStyle: {
        borderRadius: [4,4,0,0],
        color: new echarts.graphic.LinearGradient(0,0,0,1, [
          { offset: 0, color: "#409eff" },
          { offset: 1, color: "#79bbff" }
        ])
      },
      barMaxWidth: 40
    }]
  }, true)
}

function updateLineChart(data: any[]) {
  if (!lineChart) return
  const values = (data || []).reverse()
  const times = values.map((d: any) => {
    const t = new Date(d.recorded_at)
    return t.getHours().toString().padStart(2,"0")+":"+t.getMinutes().toString().padStart(2,"0")
  })
  const nums = values.map((d: any) => d.value)

  lineChart.setOption({
    tooltip: { trigger: "axis" },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: "category", data: times.length ? times : ["暂无数据"], axisLabel: { fontSize: 11 } },
    yAxis: { type: "value" },
    series: [{
      type: "line", data: nums.length ? nums : [0],
      smooth: true,
      showSymbol: false,
      lineStyle: { width: 2, color: "#409eff" },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0,0,0,1, [
          { offset: 0, color: "rgba(64,158,255,0.25)" },
          { offset: 1, color: "rgba(64,158,255,0.02)" }
        ])
      }
    }]
  }, true)
}

function initCharts() {
  if (pieChartRef.value) pieChart = echarts.init(pieChartRef.value)
  if (barChartRef.value) barChart = echarts.init(barChartRef.value)
  if (lineChartRef.value) lineChart = echarts.init(lineChartRef.value)
  updateAllCharts()
}

function handleResize() {
  pieChart?.resize()
  barChart?.resize()
  lineChart?.resize()
}

// Lifecycle
onMounted(async () => {
  await refreshAll()
  nextTick(() => initCharts())
})

onUnmounted(() => {
  pieChart?.dispose()
  barChart?.dispose()
  lineChart?.dispose()
  window.removeEventListener("resize", handleResize)
})

watch(() => trendSensorId.value, () => loadTrendData())
</script>

<style scoped>
.monitor-dashboard { }
.page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--app-text-muted); margin: 4px 0 0; }
.header-actions { flex-shrink: 0; }
.kpi-row { margin-bottom: 16px; }
.kpi-card { border-radius: 10px; }
.kpi-item { display: flex; align-items: center; gap: 14px; }
.kpi-icon-box { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.kpi-info { display: flex; flex-direction: column; }
.kpi-num { font-size: 24px; font-weight: 700; line-height: 1.2; }
.kpi-label { font-size: 12px; color: var(--app-text-muted); margin-top: 2px; }
.chart-row { margin-bottom: 16px; }
.chart-card { border-radius: 10px; }
.chart-title { font-size: 14px; font-weight: 600; }
:deep(.el-card__header) { padding: 10px 16px; border-bottom: 1px solid var(--app-border); }
.chart-container { width: 100%; }
.chart-container canvas { }
.line-chart-header { display: flex; align-items: center; justify-content: space-between; }
.table-card { border-radius: 10px; }
.table-header { display: flex; align-items: center; justify-content: space-between; }
</style>
