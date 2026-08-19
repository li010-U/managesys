<template>
  <div class="alc-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">告警生命周期</h3>
        <p class="page-desc">自动恢复 · 去重防抖 · 偶发故障识别 与 环境关联统计</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" :loading="sweepLoading" @click="runSweep">
          <el-icon><Refresh /></el-icon>&nbsp;触发自动恢复扫描
        </el-button>
      </div>
    </div>

    <!-- Summary Cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6"><el-card shadow="never" class="stat-card">
        <div class="stat-item"><div class="stat-icon-box" style="background:#e3f2fd"><el-icon :size="22" color="#1976d2"><DataLine /></el-icon></div>
          <div class="stat-info"><span class="stat-num">{{ summary.count }}</span><span class="stat-label">偶发故障总数</span></div></div>
      </el-card></el-col>
      <el-col :span="6"><el-card shadow="never" class="stat-card">
        <div class="stat-item"><div class="stat-icon-box" style="background:#e8f5e9"><el-icon :size="22" color="#27ae60"><Timer /></el-icon></div>
          <div class="stat-info"><span class="stat-num">{{ fmtDur(summary.avg_duration_seconds) }}</span><span class="stat-label">平均持续时长</span></div></div>
      </el-card></el-col>
      <el-col :span="6"><el-card shadow="never" class="stat-card">
        <div class="stat-item"><div class="stat-icon-box" style="background:#fef3e2"><el-icon :size="22" color="#e67e22"><AlarmClock /></el-icon></div>
          <div class="stat-info"><span class="stat-num">{{ fmtDur(summary.max_duration_seconds) }}</span><span class="stat-label">最长持续时长</span></div></div>
      </el-card></el-col>
      <el-col :span="6"><el-card shadow="never" class="stat-card">
        <div class="stat-item"><div class="stat-icon-box" style="background:#fce4ec"><el-icon :size="22" color="#e74c3c"><Clock /></el-icon></div>
          <div class="stat-info"><span class="stat-num">{{ fmtDur(summary.total_duration_seconds) }}</span><span class="stat-label">累计持续时长</span></div></div>
      </el-card></el-col>
    </el-row>

    <!-- 操作区：信号 + 环境摄入 -->
    <el-row :gutter="16" class="op-row">
      <el-col :span="12">
        <el-card shadow="never" class="panel">
          <template #header><span>设备状态信号（测试去重/防抖/偶发识别）</span></template>
          <el-form :inline="true" label-width="70px">
            <el-form-item label="设备ID"><el-input v-model="sig.target_id" placeholder="如 device-1" style="width:150px" /></el-form-item>
            <el-form-item label="状态">
              <el-radio-group v-model="sig.is_abnormal">
                <el-radio :value="true">异常</el-radio>
                <el-radio :value="false">恢复</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="标题"><el-input v-model="sig.title" placeholder="如 温度越阈" style="width:150px" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="sigLoading" @click="sendSignal">提交信号</el-button></el-form-item>
          </el-form>
          <el-alert v-if="sigResult" :title="sigResult" type="info" :closable="false" show-icon />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="never" class="panel">
          <template #header><span>环境/气象数据摄入</span></template>
          <el-form :inline="true" label-width="70px">
            <el-form-item label="温度°C"><el-input-number v-model="env.temperature" :controls="false" style="width:80px" /></el-form-item>
            <el-form-item label="湿度%"><el-input-number v-model="env.humidity" :controls="false" style="width:80px" /></el-form-item>
            <el-form-item label="风速"><el-input-number v-model="env.windspeed" :controls="false" style="width:80px" /></el-form-item>
            <el-form-item label="天气">
              <el-select v-model="env.weather" style="width:100px">
                <el-option v-for="w in weathers" :key="w" :label="w" :value="w" />
              </el-select>
            </el-form-item>
            <el-form-item label="位置"><el-input v-model="env.location_name" placeholder="如 主机房" style="width:110px" /></el-form-item>
            <el-form-item><el-button type="primary" :loading="envLoading" @click="recordEnv">登记环境</el-button></el-form-item>
          </el-form>
          <el-alert v-if="envResult" :title="envResult" type="success" :closable="false" show-icon />
        </el-card>
      </el-col>
    </el-row>

    <!-- 关联统计图表 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :span="12"><el-card shadow="never" class="panel"><template #header><span>逐小时偶发故障分布</span></template>
        <div ref="hourChartRef" class="chart"></div></el-card></el-col>
      <el-col :span="12"><el-card shadow="never" class="panel"><template #header><span>天气类型分布</span></template>
        <div ref="weatherChartRef" class="chart"></div></el-card></el-col>
    </el-row>

    <!-- 环境趋势折线图 -->
    <el-row class="chart-row">
      <el-col :span="24"><el-card shadow="never" class="panel"><template #header><span>环境趋势（温度 / 湿度 / 风速 近24小时）</span></template>
        <div ref="envTrendChartRef" class="chart"></div></el-card></el-col>
    </el-row>

    <el-row :gutter="16" class="chart-row">
      <el-col :span="8"><el-card shadow="never" class="panel"><template #header><span>温度区间分布</span></template>
        <div ref="tempChartRef" class="chart-sm"></div></el-card></el-col>
      <el-col :span="8"><el-card shadow="never" class="panel"><template #header><span>湿度区间分布</span></template>
        <div ref="humChartRef" class="chart-sm"></div></el-card></el-col>
      <el-col :span="8"><el-card shadow="never" class="panel"><template #header><span>风速区间分布</span></template>
        <div ref="windChartRef" class="chart-sm"></div></el-card></el-col>
    </el-row>

    <!-- 偶发故障事件 -->
    <el-card shadow="never" class="panel table-panel">
      <template #header><span>偶发故障事件（只记录、不推送，正常后自动解决）</span></template>
      <el-table :data="transientList" v-loading="transientLoading" height="360" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="target_id" label="对象" width="120" />
        <el-table-column prop="title" label="故障" min-width="140" />
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column prop="duration_seconds" label="持续(秒)" width="100" />
        <el-table-column label="环境" min-width="160">
          <template #default="{ row }">
            <span>{{ row.env_weather || '-' }} {{ row.env_temperature ?? '-' }}°C / {{ row.env_humidity ?? '-' }}% / {{ row.env_windspeed ?? '-' }}m/s</span>
          </template>
        </el-table-column>
        <el-table-column prop="location_name" label="位置" width="120" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import echarts from '../../lib/echarts'
import {
  postAlertSignalApi, runAlertSweepApi, recordEnvApi,
  getTransientEventsApi, getCorrelationApi, getEnvTrendApi,
} from '../../api/alertLifecycle'

const weathers = ['晴', '多云', '阴', '雨', '雪', '风']

const summary = reactive({ count: 0, avg_duration_seconds: 0, max_duration_seconds: 0, min_duration_seconds: 0, total_duration_seconds: 0 })
const transientList = ref<any[]>([])
const transientLoading = ref(false)

const sig = reactive({ target_id: 'device-1', is_abnormal: true, title: '设备异常' })
const sigLoading = ref(false)
const sweepLoading = ref(false)
const sigResult = ref('')

const env = reactive({ temperature: 25, humidity: 60, windspeed: 3, weather: '多云', location_name: '主机房' })
const envLoading = ref(false)
const envResult = ref('')

const hourChartRef = ref<HTMLDivElement>()
const weatherChartRef = ref<HTMLDivElement>()
const tempChartRef = ref<HTMLDivElement>()
const humChartRef = ref<HTMLDivElement>()
const windChartRef = ref<HTMLDivElement>()
const envTrendChartRef = ref<HTMLDivElement>()

let charts: echarts.ECharts[] = []

function fmtDur(sec: number | undefined) {
  if (!sec) return '0s'
  if (sec < 60) return `${sec}s`
  if (sec < 3600) return `${Math.round(sec / 60)}m`
  return `${(sec / 3600).toFixed(1)}h`
}
function fmtTime(t?: string) {
  return t ? t.replace('T', ' ').slice(0, 19) : '-'
}
function disposeCharts() {
  charts.forEach((c) => { if (c) c.dispose() })
  charts = []
}
function initChart(el: HTMLDivElement | undefined) {
  if (!el) return null
  const c = echarts.init(el)
  charts.push(c)
  return c
}

async function sendSignal() {
  sigLoading.value = true
  try {
    const r = await postAlertSignalApi({
      target_type: 'device', target_id: sig.target_id, is_abnormal: sig.is_abnormal,
      title: sig.title, level: 'general',
    })
    const d = r.data
    sigResult.value = `action=${d.action}${d.transient ? '（偶发，仅记录不推送）' : ''}`
    await refresh()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '信号提交失败')
  } finally {
    sigLoading.value = false
  }
}

async function runSweep() {
  try {
    const r = await runAlertSweepApi()
    ElMessage.success(`自动恢复 ${r.data.resolved_count} 条告警`)
    await refresh()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '扫描失败')
  }
}

async function recordEnv() {
  envLoading.value = true
  try {
    await recordEnvApi({ ...env })
    envResult.value = '环境数据已登记'
    await refresh()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '登记失败')
  } finally {
    envLoading.value = false
  }
}

function renderCharts(data: any) {
  const hour = data?.by_hour || []
  const weather = data?.by_weather || []
  const buckets = data?.by_env_bucket || {}

  const hourChart = initChart(hourChartRef.value)
  if (hourChart) hourChart.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 16, top: 24, bottom: 28 },
    xAxis: { type: 'category', data: hour.map((h: any) => `${h.hour}:00`) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [{ type: 'bar', data: hour.map((h: any) => h.count), itemStyle: { color: '#4e79a7' }, barMaxWidth: 22 }],
  })

  const weatherChart = initChart(weatherChartRef.value)
  if (weatherChart) weatherChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie', radius: ['40%', '68%'], center: ['50%', '46%'],
      label: { formatter: '{b}: {c}' },
      data: weather.map((w: any) => ({ name: w.weather, value: w.count })),
    }],
  })

  const mkBar = (el: any, list: any[], color: string) => {
    const c = initChart(el)
    if (c) c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 70, right: 16, top: 16, bottom: 30 },
      xAxis: { type: 'value', minInterval: 1 },
      yAxis: { type: 'category', data: (list || []).map((b: any) => b.bucket), inverse: true },
      series: [{ type: 'bar', data: (list || []).map((b: any) => b.count), itemStyle: { color } }],
    })
  }
  mkBar(tempChartRef.value, buckets.temperature, '#f28e2b')
  mkBar(humChartRef.value, buckets.humidity, '#59a14f')
  mkBar(windChartRef.value, buckets.windspeed, '#76b7b2')
}

function renderEnvTrend(list: any[]) {
  const c = initChart(envTrendChartRef.value)
  if (!c) return
  const times = list.map((r: any) => (r.recorded_at || '').replace('T', ' ').slice(5, 16))
  c.setOption({
    tooltip: { trigger: 'axis' },
    legend: { top: 0 },
    grid: { left: 48, right: 48, top: 30, bottom: 28 },
    xAxis: { type: 'category', data: times, boundaryGap: false },
    yAxis: [
      { type: 'value', name: '°C / %', position: 'left' },
      { type: 'value', name: 'm/s', position: 'right' },
    ],
    series: [
      { name: '温度(°C)', type: 'line', data: list.map((r: any) => r.temperature), smooth: true, showSymbol: false },
      { name: '湿度(%)', type: 'line', data: list.map((r: any) => r.humidity), smooth: true, showSymbol: false },
      { name: '风速(m/s)', type: 'line', yAxisIndex: 1, data: list.map((r: any) => r.windspeed), smooth: true, showSymbol: false },
    ],
  })
}

async function refresh() {
  try {
    const corr = await getCorrelationApi(7)
    Object.assign(summary, corr.data.summary)
    const list = await getTransientEventsApi(100)
    transientList.value = list.data
    const trend = await getEnvTrendApi({ hours: 24, limit: 200 })
    disposeCharts()
    renderCharts(corr)
    renderEnvTrend(trend.data || [])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '数据加载失败')
  }
}

onMounted(() => { refresh() })
onBeforeUnmount(() => { disposeCharts() })
</script>

<style scoped>
.alc-page { padding: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.page-title { margin: 0; font-size: 20px; }
.page-desc { margin: 4px 0 0; color: #909399; font-size: 13px; }
.stats-row { margin-bottom: 16px; }
.stat-card { border-radius: 8px; }
.stat-item { display: flex; align-items: center; gap: 12px; }
.stat-icon-box { width: 46px; height: 46px; border-radius: 8px; display: flex; align-items: center; justify-content: center; }
.stat-num { font-size: 22px; font-weight: 700; display: block; }
.stat-label { font-size: 12px; color: #909399; }
.op-row, .chart-row { margin-bottom: 16px; }
.panel { border-radius: 8px; }
.chart { width: 100%; height: 280px; }
.chart-sm { width: 100%; height: 220px; }
.table-panel { margin-bottom: 8px; }
</style>
