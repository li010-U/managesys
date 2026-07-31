<template>
  <div class="env-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">环境监测</h3>
        <p class="page-desc">实时监控机房温湿度、烟感、水浸、门磁等环境参数</p>
      </div>
    </div>

    <!-- Summary Cards -->
    <el-row :gutter="16" class="stats-row">
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background:#e3f2fd">
              <el-icon :size="22" color="#1976d2"><ColdDrink /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ sensors.length }}</span>
              <span class="stat-label">传感器总数</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background:#e8f5e9">
              <el-icon :size="22" color="#27ae60"><Check /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ onlineCount }}</span>
              <span class="stat-label">在线</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background:#fef3e2">
              <el-icon :size="22" color="#e67e22"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ alertCount }}</span>
              <span class="stat-label">告警中</span>
            </div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="stat-card">
          <div class="stat-item">
            <div class="stat-icon-box" style="background:#fce4ec">
              <el-icon :size="22" color="#e74c3c"><Connection /></el-icon>
            </div>
            <div class="stat-info">
              <span class="stat-num">{{ offlineCount }}</span>
              <span class="stat-label">离线</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Toolbar -->
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar-bar">
        <div class="toolbar-left">
          <span class="label-text">机房：</span>
          <el-select v-model="filterRoom" clearable placeholder="全部机房" style="width:180px" @change="fetchData">
            <el-option v-for="r in roomList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </div>
        <div class="toolbar-left" style="margin-left:12px">
          <span class="label-text">类型：</span>
          <el-select v-model="filterType" clearable placeholder="全部类型" style="width:140px" @change="fetchData">
            <el-option label="温度" value="temperature" />
            <el-option label="湿度" value="humidity" />
            <el-option label="烟感" value="smoke" />
            <el-option label="水浸" value="water" />
            <el-option label="门磁" value="door_magnetic" />
          </el-select>
        </div>
        <div style="flex:1"></div>
        <el-button type="primary" :icon="Plus" @click="openDialog()">新增传感器</el-button>
        <el-button :icon="Refresh" @click="fetchData">刷新</el-button>
      </div>
    </el-card>

    <!-- Sensor Cards Grid -->
    <el-card shadow="never" class="sensor-grid-card">
      <div v-if="loading" class="loading-overlay"><el-icon class="is-loading" :size="32"><Loading /></el-icon></div>
      <div v-if="filteredSensors.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无传感器数据" :image-size="80" />
      </div>

      <div v-else class="sensor-grid">
        <div v-for="s in filteredSensors" :key="s.id" class="sensor-card" :class="sensorCardClass(s)">
          <!-- Card header -->
          <div class="sc-header">
            <div class="sc-type-icon" :style="{ background: sensorTypeColor(s.sensor_type) + '15' }">
              <el-icon :size="18" :color="sensorTypeColor(s.sensor_type)">
                <component :is="sensorTypeIcon(s.sensor_type)" />
              </el-icon>
            </div>
            <div class="sc-info">
              <div class="sc-name">{{ s.name }}</div>
              <div class="sc-location">{{ s.code }} · {{ s.install_position || s.room_name }}</div>
            </div>
            <div class="sc-status">
              <el-tag :type="s.status === 'online' ? 'success' : 'info'" size="small" effect="plain">
                {{ s.status === 'online' ? '在线' : '离线' }}
              </el-tag>
            </div>
          </div>
          <!-- Card body -->
          <div class="sc-body">
            <div class="sc-value">
              <template v-if="s.current_value">
                <span class="sc-value-num" :style="{ color: sensorValueColor(s) }">{{ formatValue(s.current_value.value, s.sensor_type) }}</span>
                <span class="sc-value-unit">{{ getUnit(s.sensor_type) }}</span>
              </template>
              <span v-else class="sc-value-na">--</span>
            </div>
            <div class="sc-meta">
              <span>更新: {{ formatTime(s.last_update_time) }}</span>
              <span v-if="s.threshold_min !== null || s.threshold_max !== null">
                阈值: {{ s.threshold_min ?? '-' }} ~ {{ s.threshold_max ?? '-' }}
              </span>
            </div>
            <!-- Mini value bar for temperature/humidity -->
            <div v-if="sensorTypeGauge(s.sensor_type) && s.current_value" class="sc-bar">
              <div class="sc-bar-track">
                <div class="sc-bar-fill" :style="{ width: gaugePercent(s) + '%', background: sensorValueColor(s) }"></div>
              </div>
            </div>
          </div>
          <!-- Card actions -->
          <div class="sc-actions">
            <el-button text size="small" :icon="Edit" @click="openDialog(s)">编辑</el-button>
            <el-button text size="small" :icon="DataLine" @click="showHistory(s)">历史</el-button>
            <el-button text size="small" type="primary" :icon="Upload" @click="simulateData(s)">模拟数据</el-button>
            <el-button text type="danger" size="small" :icon="Delete" @click="deleteItem(s)">删除</el-button>
          </div>
        </div>
      </div>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑传感器' : '新增传感器'" width="600px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="传感器名称" prop="name"><el-input v-model="form.name" placeholder="如：A01列头柜温度" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="编号" prop="code"><el-input v-model="form.code" placeholder="如：T-A01-01" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="所属机房" prop="room_id"><el-select v-model="form.room_id" filterable style="width:100%"><el-option v-for="r in roomList" :key="r.id" :label="r.name" :value="r.id" /></el-select></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="传感器类型" prop="sensor_type"><el-select v-model="form.sensor_type" style="width:100%"><el-option label="温度" value="temperature" /><el-option label="湿度" value="humidity" /><el-option label="烟感" value="smoke" /><el-option label="水浸" value="water" /><el-option label="门磁" value="door_magnetic" /></el-select></el-form-item></el-col>
        </el-row>
        <el-form-item label="安装位置"><el-input v-model="form.install_position" placeholder="如：A01列柜顶" /></el-form-item>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item label="阈值下限"><el-input-number v-model="form.threshold_min" :min="-100" :step="0.5" :precision="1" clearable style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item label="阈值上限"><el-input-number v-model="form.threshold_max" :min="-100" :step="0.5" :precision="1" clearable style="width:100%" /></el-form-item></el-col>
        </el-row>
        <el-form-item label="告警级别"><el-select v-model="form.alert_level" style="width:100%"><el-option label="一般" value="general" /><el-option label="严重" value="serious" /><el-option label="紧急" value="emergency" /></el-select></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- History Dialog -->
    <el-dialog v-model="historyDialog.visible" title="传感器历史数据" width="600px">
      <div v-if="historyData.length === 0" style="text-align:center;padding:40px">暂无历史数据</div>
      <div v-else class="history-list">
        <div v-for="d in historyData" :key="d.id" class="history-item">
          <span class="hi-value">{{ d.value }}</span>
          <span class="hi-time">{{ formatTime(d.recorded_at) }}</span>
        </div>
      </div>
      <template #footer><el-button @click="historyDialog.visible = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import type { FormInstance } from "element-plus"
import { Plus, Edit, Delete, Refresh, DataLine, Upload, Warning } from "@element-plus/icons-vue"
import { getSensorsApi, createSensorApi, updateSensorApi, deleteSensorApi, getSensorDataApi, recordSensorDataApi } from "../../api/sensor"
import { getRoomsApi } from "../../api/facility"
import type { SensorInfo } from "../../api/sensor"
import type { RoomInfo } from "../../api/facility"
import { ColdDrink, Check, Connection } from "@element-plus/icons-vue"
import { Loading } from "@element-plus/icons-vue"
import type { Component } from "vue"

const loading = ref(false)
const submitting = ref(false)
const sensors = ref<SensorInfo[]>([])
const roomList = ref<RoomInfo[]>([])
const filterRoom = ref<number | null>(null)
const filterType = ref<string>("")
const formRef = ref<FormInstance>()
const dialog = ref({ visible: false, isEdit: false, id: 0 })
const form = ref<any>({ name: "", code: "", room_id: undefined, sensor_type: "temperature", install_position: "", threshold_min: null, threshold_max: null, alert_level: "general" })
const rules = {
  name: [{ required: true, message: "请输入传感器名称", trigger: "blur" }],
  code: [{ required: true, message: "请输入传感器编号", trigger: "blur" }],
  room_id: [{ required: true, message: "请选择所属机房", trigger: "change" }],
  sensor_type: [{ required: true, message: "请选择传感器类型", trigger: "change" }],
}
const historyDialog = ref({ visible: false })
const historyData = ref<any[]>([])

// Computed
const onlineCount = computed(() => sensors.value.filter(s => s.status === "online").length)
const offlineCount = computed(() => sensors.value.filter(s => s.status === "offline").length)
const alertCount = computed(() => sensors.value.filter(s => {
  if (!s.current_value) return false
  const v = s.current_value.value
  return (s.threshold_min !== null && v < s.threshold_min) || (s.threshold_max !== null && v > s.threshold_max)
}).length)

const filteredSensors = computed(() => {
  let list = sensors.value
  if (filterType.value) {
    list = list.filter(s => s.sensor_type === filterType.value)
  }
  return list
})

function sensorTypeColor(type: string): string {
  return ({ temperature: "#e74c3c", humidity: "#3498db", smoke: "#e67e22", water: "#9b59b6", door_magnetic: "#2ecc71" } as any)[type] || "#909399"
}
function sensorTypeIcon(type: string): Component {
  const icons: Record<string, Component> = { temperature: ColdDrink, humidity: ColdDrink, smoke: Warning, water: Connection, door_magnetic: Connection }
  return icons[type] || Warning
}
function sensorTypeGauge(type: string): boolean {
  return ["temperature", "humidity"].includes(type)
}
function getUnit(type: string): string {
  return ({ temperature: "°C", humidity: "%RH", smoke: "", water: "", door_magnetic: "" } as any)[type] || ""
}
function sensorValueColor(s: SensorInfo): string {
  if (!s.current_value || s.current_value.value === null) return "#909399"
  const v = s.current_value.value
  if (s.threshold_min !== null && v < s.threshold_min) return "#3498db"
  if (s.threshold_max !== null && v > s.threshold_max) return "#e74c3c"
  return "#27ae60"
}
function sensorCardClass(s: SensorInfo): string {
  if (s.status !== "online") return "sc-offline"
  if (!s.current_value) return ""
  const v = s.current_value.value
  if ((s.threshold_min !== null && v < s.threshold_min) || (s.threshold_max !== null && v > s.threshold_max)) return "sc-alert"
  return ""
}
function gaugePercent(s: SensorInfo): number {
  if (!s.current_value) return 0
  const v = s.current_value.value
  if (s.threshold_min !== null && s.threshold_max !== null) {
    const range = s.threshold_max - s.threshold_min
    if (range === 0) return 50
    return Math.min(100, Math.max(0, (v - s.threshold_min) / range * 100))
  }
  return Math.min(100, v / 50 * 100)
}
function formatValue(v: number, type: string): string {
  if (v === null || v === undefined) return "--"
  if (type === "temperature" || type === "humidity") return v.toFixed(1)
  return String(v)
}
function formatTime(t: string | null): string {
  if (!t) return "--"
  try {
    const d = new Date(t)
    return (d.getMonth() + 1) + "/" + d.getDate() + " " + d.getHours().toString().padStart(2, "0") + ":" + d.getMinutes().toString().padStart(2, "0")
  } catch { return "--" }
}

onMounted(async () => { await fetchRooms(); await fetchData() })

async function fetchRooms() {
  try { const r = await getRoomsApi({ page: 1, page_size: 100 }); roomList.value = r.data.items } catch {}
}
async function fetchData() {
  loading.value = true
  try {
    const r = await getSensorsApi({ page: 1, page_size: 100, room_id: filterRoom.value || undefined })
    sensors.value = r.data.items
  } catch { sensors.value = [] }
  finally { loading.value = false }
}
function openDialog(item?: SensorInfo) {
  dialog.value = { visible: true, isEdit: !!item, id: item?.id || 0 }
  form.value = item
    ? { name: item.name, code: item.code, room_id: item.room_id, sensor_type: item.sensor_type, install_position: item.install_position || "", threshold_min: item.threshold_min, threshold_max: item.threshold_max, alert_level: item.alert_level }
    : { name: "", code: "", room_id: undefined, sensor_type: "temperature", install_position: "", threshold_min: null, threshold_max: null, alert_level: "general" }
  setTimeout(() => formRef.value?.clearValidate(), 0)
}
async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  submitting.value = true
  try {
    const data = { ...form.value }
    if (dialog.value.isEdit) { await updateSensorApi(dialog.value.id, data); ElMessage.success("已更新") }
    else { await createSensorApi(data); ElMessage.success("已创建") }
    dialog.value.visible = false
    await fetchData()
  } catch {} finally { submitting.value = false }
}
async function deleteItem(item: SensorInfo) {
  try {
    await ElMessageBox.confirm(`确定删除传感器 "${item.name}" ？`, "确认", { type: "warning" })
    await deleteSensorApi(item.id)
    ElMessage.success("已删除")
    await fetchData()
  } catch {}
}
async function showHistory(item: SensorInfo) {
  try {
    const r = await getSensorDataApi(item.id, 20)
    historyData.value = r.data || []
    historyDialog.value.visible = true
  } catch { historyData.value = []; historyDialog.value.visible = true }
}
async function simulateData(item: SensorInfo) {
  try {
    let value: number
    switch (item.sensor_type) {
      case "temperature": value = 20 + Math.random() * 10; break
      case "humidity": value = 40 + Math.random() * 30; break
      case "smoke": value = Math.random() * 100; break
      case "water": value = Math.round(Math.random()); break
      case "door_magnetic": value = Math.round(Math.random()); break
      default: value = Math.random() * 100
    }
    await recordSensorDataApi(item.id, Math.round(value * 10) / 10)
    ElMessage.success("已模拟一条数据")
    await fetchData()
  } catch {}
}
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 18px; font-weight: 600; margin: 0; }
.page-desc { font-size: 13px; color: var(--app-text-muted); margin: 4px 0 0; }
.stats-row { margin-bottom: 16px; }
.stat-card { border-radius: 10px; }
.stat-item { display: flex; align-items: center; gap: 14px; }
.stat-icon-box { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 22px; font-weight: 700; line-height: 1.2; }
.stat-label { font-size: 12px; color: var(--app-text-muted); margin-top: 2px; }
.toolbar-card { margin-bottom: 16px; border-radius: 10px; }
.toolbar-bar { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.toolbar-left { display: flex; align-items: center; gap: 6px; }
.label-text { font-size: 13px; color: var(--app-text-secondary); white-space: nowrap; }
.sensor-grid-card { border-radius: 10px; position: relative; min-height: 200px; }
.loading-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.6); z-index: 10; }
.empty-state { padding: 40px; display: flex; justify-content: center; }
.sensor-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.sensor-card { border: 1px solid var(--app-border); border-radius: 12px; padding: 16px; transition: all 0.2s; background: var(--app-bg); }
.sensor-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); transform: translateY(-1px); }
.sensor-card.sc-alert { border-color: #e74c3c; background: rgba(231,76,60,0.02); }
.sensor-card.sc-offline { opacity: 0.7; }
html.dark .sensor-card { background: var(--app-bg-secondary); }
.sc-header { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.sc-type-icon { width: 36px; height: 36px; border-radius: 8px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.sc-info { flex: 1; min-width: 0; }
.sc-name { font-size: 14px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sc-location { font-size: 11px; color: var(--app-text-muted); margin-top: 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sc-status { flex-shrink: 0; }
.sc-body { margin-bottom: 10px; }
.sc-value { display: flex; align-items: baseline; gap: 4px; margin-bottom: 6px; }
.sc-value-num { font-size: 28px; font-weight: 700; font-family: "SFMono-Regular", Consolas, monospace; }
.sc-value-unit { font-size: 14px; color: var(--app-text-muted); }
.sc-value-na { font-size: 24px; color: var(--app-text-muted); }
.sc-meta { display: flex; gap: 16px; font-size: 11px; color: var(--app-text-muted); margin-bottom: 8px; }
.sc-bar-track { height: 4px; background: var(--app-border); border-radius: 2px; overflow: hidden; }
.sc-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
.sc-actions { display: flex; gap: 4px; border-top: 1px solid var(--app-border); padding-top: 10px; }
.history-list { max-height: 400px; overflow-y: auto; }
.history-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--app-border); font-size: 13px; }
.hi-value { font-weight: 600; font-family: "SFMono-Regular", Consolas, monospace; }
.hi-time { color: var(--app-text-muted); }
</style>
