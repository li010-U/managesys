<template>
  <div class="rack3d-page">
    <div class="page-header">
      <div>
        <h3 class="page-title">机房 3D 视图</h3>
        <p class="page-desc">立体查看机柜布局与空间利用 · 左键旋转 / 右键平移 / 滚轮缩放</p>
      </div>
    </div>
    <el-card shadow="never" class="toolbar-card">
      <div class="toolbar-bar">
        <div class="toolbar-left">
          <el-select :model-value="roomId" placeholder="选择机房" style="width:220px" @change="switchRoom">
            <el-option v-for="r in roomList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
          <el-autocomplete
            v-model="searchText"
            :fetch-suggestions="onSearch"
            :trigger-on-focus="false"
            placeholder="搜索机柜/设备/资产号"
            clearable
            style="width:220px"
            @select="onSearchSelect"
          />
          <span class="room-badge" v-if="room?.name">{{ room.name }} · {{ room.code }}<template v-if="room?.floor"> · {{ room.floor }}</template></span>
          <el-tooltip v-if="sceneData?.temperature?.avg != null" content="机房环境温度(来自传感器)">
            <el-tag size="small" :type="tempType(sceneData.temperature.avg)" effect="dark"><el-icon :size="12" style="margin-right:3px"><ColdDrink /></el-icon>{{ sceneData.temperature.avg }}℃</el-tag>
          </el-tooltip>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadData">刷新</el-button>
          <el-select v-model="livePeriod" size="small" style="width:96px">
            <el-option v-for="ms in LIVE_OPTIONS" :key="ms" :label="(ms/1000)+'秒'" :value="ms" />
          </el-select>
          <el-button :type="liveToggling ? 'primary' : 'default'" @click="setLive(!liveToggling)">实时刷新</el-button>
          <el-button :icon="View" @click="sceneRef?.resetView()">复位视角</el-button>
          <el-button type="primary" :icon="Grid" @click="go2d">切换到 2D 视图</el-button>
        </div>
      </div>
    </el-card>
    <el-row :gutter="12">
      <el-col :span="18">
        <el-card shadow="never" class="scene-card">
          <Rack3DScene v-if="sceneData" ref="sceneRef" :data="sceneData" :history="historyData" @select-rack="onSelectRack" @selection-change="onSelectionChange" @box-select="onBoxSelect" @select-device="onSelectDevice" />
          <el-empty v-else-if="!loading" description="该机房暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="panel-card">
          <template #header><b>机柜 / 设备信息</b><el-button v-if="selectedDevice" text size="small" style="float:right;padding:0" @click="selectedDevice = null">返回机柜</el-button></template>
                    <div v-if="selectedDevice" class="rack-info dev-detail">
            <div class="ri-title">{{ selectedDevice.name }} <span class="ri-sub">{{ selectedDevice.asset_number }}</span></div>
            <el-tag size="small" :style="{color:'#fff',background:devStatusColor(selectedDevice.status)}">{{ statusName(selectedDevice.status) }}</el-tag>
            <el-descriptions :column="1" size="small" border style="margin-top:10px">
              <el-descriptions-item label="设备类型">{{ selectedDevice.device_type_name }}</el-descriptions-item>
              <el-descriptions-item label="类别"><span :style="{color:catColorText(selectedDevice.device_type_category)}">{{ selectedDevice.device_type_category || '—' }}</span></el-descriptions-item>
              <el-descriptions-item label="所在机柜">{{ selectedRack?.code || '—' }}</el-descriptions-item>
              <el-descriptions-item label="U 位">{{ selectedDevice.start_u }}{{ selectedDevice.end_u && selectedDevice.end_u !== selectedDevice.start_u ? '–' + selectedDevice.end_u : '' }}U</el-descriptions-item>
              <el-descriptions-item label="额定功率">{{ selectedDevice.power_rating || '—' }} kW</el-descriptions-item>
              <el-descriptions-item label="管理IP">{{ selectedDevice.management_ip || '—' }}</el-descriptions-item>
            </el-descriptions>
          </div>
<div v-if="selectedRack && !selectedRack.multi" class="rack-info">
            <div class="ri-title">{{ selectedRack.code }} <span class="ri-sub">{{ selectedRack.name }}</span></div>
            <el-tag size="small" :type="utilType(selectedRack.utilization)">利用率 {{ selectedRack.utilization }}%</el-tag>
            <el-tag size="small" type="danger" v-if="selectedRack.alerts > 0">{{ selectedRack.alerts }} 条告警</el-tag>
            <el-descriptions :column="1" size="small" border style="margin-top:10px">
              <el-descriptions-item label="U 位">{{ selectedRack.total_units - selectedRack.available_units }} / {{ selectedRack.total_units }}U</el-descriptions-item>
              <el-descriptions-item label="设备数">{{ selectedRack.device_count }}</el-descriptions-item>
              <el-descriptions-item label="额定功率">{{ selectedRack.rated_power || '—' }} kW</el-descriptions-item>
              <el-descriptions-item label="功率负载">{{ selectedRack.power_load || 0 }} kW <span v-if="selectedRack.power_load_pct" :style="{color:powerColor(selectedRack.power_load_pct)}">({{ selectedRack.power_load_pct }}%)</span></el-descriptions-item>
              <el-descriptions-item label="环境温度">{{ sceneData?.temperature?.avg ?? '—' }}℃</el-descriptions-item>
            </el-descriptions>
            <el-divider content-position="left">设备(U位)</el-divider>
            <div v-if="selectedRack.devices?.length" class="dev-list">
              <div v-for="d in selectedRack.devices" :key="d.id" class="dev-row" style="cursor:pointer" @click="onSelectDevice(d)">
                <span class="dev-u">{{ d.start_u }}U</span>
                <span class="dev-name">{{ d.name }}</span>
                <span class="dev-cat" :style="{color:catColorText(d.device_type_category)}">{{ d.device_type_name }}</span>
              </div>
            </div>
            <el-empty v-else description="机柜内无设备" :image-size="50" />
            <el-button type="primary" style="width:100%;margin-top:12px" @click="go2dDetail">进入 2D 详情</el-button>
          </div>
          <div v-else-if="selectedRack && selectedRack.multi" class="rack-info">
            <div class="ri-title">已选 {{ selectedRack.ids.length }} 个机柜</div>
            <div class="dev-list" style="margin-top:8px">
              <div v-for="r in selectedRack.racks" :key="r.id" class="dev-row">
                <span class="dev-u" :style="{color: powerColor(r.power_load_pct)}">{{ r.code }}</span>
                <span class="dev-name">{{ r.name }}</span>
                <span class="dev-cat" style="color:#374151">利用率 {{ r.utilization }}% · 负载 {{ r.power_load_pct }}%</span>
              </div>
            </div>
            <div class="dev-row" style="margin-top:8px">
              <span class="dev-u">合计</span>
              <span class="dev-name">设备 {{ totalDevices }} 台</span>
              <span class="dev-cat" style="color:#374151">功率 {{ totalPower }} kW</span>
            </div>
          </div>
          <el-empty v-else description="点击左侧机柜查看详情" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Rack3DView' })
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, View, Grid, ColdDrink } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getRoomsApi, getRoomRack3dApi, getRoomApi } from '../../api/facility'
import { getSensorDataApi } from '../../api/sensor'
import Rack3DScene from '../../components/Rack3D/Rack3DScene.vue'

const route = useRoute()
const router = useRouter()

const roomId = ref<number>(Number(route.query.room_id || route.params.room_id) || 0)
const roomList = ref<any[]>([])
const room = ref<any>(null)
const sceneData = ref<any>(null)
const loading = ref(false)
const selectedRack = ref<any>(null)
const sceneRef = ref<any>(null)
const historyData = ref<any[]>([])
const livePeriod = ref(15000)
const LIVE_OPTIONS = [3000, 5000, 10000, 15000]
let liveTimer: number | null = null
const liveToggling = ref(false)
const selectedDevice = ref<any>(null)
const searchText = ref('')

const catColors: Record<string, string> = {
  server: '#2196F3', network: '#4CAF50', storage: '#9C27B0', security: '#FF9800', power: '#F44336',
}
function catColorText(c: string): string { return catColors[c] || '#607D8B' }
function utilType(u: number): string { return u >= 80 ? 'danger' : u >= 50 ? 'warning' : 'success' }
function tempType(t: number): string { return t >= 32 ? 'danger' : t >= 27 ? 'warning' : 'success' }
function powerColor(p: number): string { return p >= 90 ? '#e74c3c' : p >= 70 ? '#e67e22' : '#27ae60' }
function statusName(s: string): string { const m: Record<string,string> = { online:'在线', running:'运行中', mounted:'已上架', in_stock:'在库', offline:'离线', maintenance:'维护', scrapped:'报废' }; return m[s] || (s || '未知') }
function devStatusColor(s: string): string { const online = s === 'online' || s === 'running'; if (online) return '#2f9e44'; if (s === 'offline' || s === 'scrapped') return '#868e96'; if (s === 'in_stock') return '#f59f00'; if (s === 'maintenance') return '#f76707'; return '#5c7cfa' }

const totalDevices = computed(() => (selectedRack.value?.racks || []).reduce((a: number, r: any) => a + (r.device_count || 0), 0))
const totalPower = computed(() => (selectedRack.value?.racks || []).reduce((a: number, r: any) => a + (r.power_load || 0), 0).toFixed(1))

async function loadRooms() {
  try {
    const r = await getRoomsApi({ page: 1, page_size: 100 })
    roomList.value = r.data.items
    if (!roomId.value && roomList.value.length) roomId.value = roomList.value[0].id
  } catch { roomList.value = [] }
}

async function loadData() {
  if (!roomId.value) return
  loading.value = true
  sceneData.value = null
  selectedRack.value = null
  historyData.value = []
  try {
    const [rr, d] = await Promise.all([getRoomApi(roomId.value), getRoomRack3dApi(roomId.value)])
    room.value = rr.data
    sceneData.value = d.data
    await loadHistory()
  } catch {
    sceneData.value = null
    ElMessage.error('加载 3D 数据失败')
  } finally { loading.value = false }
}

async function loadHistory() {
  historyData.value = []
  const temps = (sceneData.value?.sensors || []).filter((s: any) => s.sensor_type === 'temperature')
  if (!temps.length) return
  try {
    const sample = temps.slice(0, 3)
    const series = await Promise.all(sample.map((s: any) => getSensorDataApi(s.id, 20).then((r: any) => r.data || []).catch(() => [])))
    if (!series.some((arr: any[]) => arr.length)) return
    const length = Math.max(...series.map((arr: any[]) => arr.length))
    const points: { time: string; temps: Record<number, number> }[] = []
    for (let i = 0; i < length; i++) {
      let sum = 0, cnt = 0, time = ''
      for (const arr of series) {
        const rec = arr[arr.length - 1 - i]
        if (!rec) continue
        const v = rec.value
        if (typeof v === 'number') { sum += v; cnt++; time = rec.created_at || rec.ts || '' }
      }
      if (!cnt) continue
      const avg = Math.round(sum / cnt * 10) / 10
      const temps: Record<number, number> = {}
      for (const r of (sceneData.value?.racks || [])) {
        const base = typeof r.temperature === 'number' ? r.temperature : avg
        temps[r.id] = Math.round((base + (avg - (sceneData.value?.temperature?.avg ?? avg))) * 10) / 10
      }
      points.push({ time, temps })
    }
    points.reverse()
    historyData.value = points
  } catch { historyData.value = [] }
}

async function pollData() {
  if (!roomId.value || !sceneData.value) return
  try {
    const d = await getRoomRack3dApi(roomId.value)
    if (d?.data) {
      // 增量刷新：保留选中，仅更新数值/状态（场景组件对 racks 做差异化更新）
      const prev = sceneData.value
      const next = d.data
      next.racks = (next.racks || []).map((r: any) => {
        const old = (prev?.racks || []).find((o: any) => o.id === r.id)
        return { ...(old || {}), ...r }
      })
      sceneData.value = next
      // 若已选中某机柜/设备，同步其最新数据
      syncSelectionAfterPoll(next)
    }
  } catch { /* 实时刷新失败静默，下次再试 */ }
}

function syncSelectionAfterPoll(next: any) {
  const sel = selectedRack.value
  if (!sel || sel.multi) return
  const fresh = (next?.racks || []).find((r: any) => r.id === sel.id)
  if (fresh) { selectedRack.value = fresh; if (selectedDevice.value) selectedDevice.value = fresh.devices?.find((d: any) => d.id === selectedDevice.value?.id) || null }
}

function setLive(on: boolean) {
  liveToggling.value = on
  if (!on) { if (liveTimer) { clearInterval(liveTimer); liveTimer = null } return }
  if (on && !liveTimer) { liveTimer = window.setInterval(pollData, livePeriod.value) }
}

function onSelectRack(rack: any) { selectedRack.value = rack; selectedDevice.value = null }
function onSelectionChange(count: number) { if (count === 0) selectedRack.value = null }
function onBoxSelect(ids: number[]) {
  selectedDevice.value = null
  if (ids.length) {
    selectedRack.value = {
      multi: true, ids,
      racks: ids.map((id: number) => (sceneData.value?.racks || []).find((r: any) => r.id === id)).filter(Boolean),
    }
  } else {
    selectedRack.value = null
  }
}
function onSelectDevice(dev: any) {
  if (!dev) { selectedDevice.value = null; return }
  selectedDevice.value = dev
  const rid = dev.rack_id ?? selectedRack.value?.id
  const r = rid ? (sceneData.value?.racks || []).find((x: any) => x.id === rid) : null
  if (r) selectedRack.value = r
}
interface SearchHit { value: string; kind: 'rack' | 'device'; id: number; rackId?: number }
const searchLoading = ref(false)
function onSearch(queryString: string, cb: (r: any[]) => void) {
  if (!queryString) { cb([]); return }
  const q = queryString.trim().toLowerCase()
  const hits: SearchHit[] = []
  for (const r of (sceneData.value?.racks || [])) {
    const rLabel = (r.code || '') + ' ' + (r.name || '')
    const rKey = (rLabel + ' ' + r.id).toLowerCase()
    if (rKey.includes(q)) { hits.push({ value: rLabel.trim(), kind: 'rack', id: r.id }); continue }
    for (const d of (r.devices || [])) {
      const dLabel = (d.name || '') + ' · ' + (d.asset_number || (d.id + ''))
      if ((dLabel + ' ' + d.id).toLowerCase().includes(q)) {
        hits.push({ value: dLabel.trim(), kind: 'device', id: d.id, rackId: r.id })
      }
    }
  }
  cb(hits.slice(0, 12))
}
function onSearchSelect(item: any) {
  const hit = item as unknown as SearchHit
  if (!hit) return
  if (hit.kind === 'rack') sceneRef.value?.focusRack(hit.id)
  else if (hit.kind === 'device') sceneRef.value?.focusDevice(hit.id)
}
async function switchRoom(id: number) {
  if (id === roomId.value) return
  roomId.value = id
  try {
    await router.replace({ query: { ...route.query, room_id: id } })
  } catch { /* 仅更新 URL query，忽略导航结果 */ }
  await loadData()
}
function go2d() { router.push({ name: 'Racks', query: { room_id: roomId.value } }) }
function go2dDetail() {
  if (selectedRack.value && !selectedRack.value.multi) router.push({ name: 'Racks', query: { room_id: roomId.value, rack: selectedRack.value.id } })
}

watch(() => livePeriod.value, () => { if (liveToggling.value) setLive(true) })

onMounted(async () => {
  await loadRooms()
  await loadData()
  setLive(true)
})

onBeforeUnmount(() => { setLive(false) })
</script>

<style scoped>
.page-header { margin-bottom: 16px; }
.page-title { font-size: 20px; font-weight: 700; margin: 0; background: linear-gradient(135deg, #8e24aa, #4a148c); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
.page-desc { font-size: 13px; color: var(--app-text-muted); margin: 4px 0 0; }
.toolbar-card { margin-bottom: 12px; border-radius: 12px; }
.toolbar-bar { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.toolbar-left, .toolbar-right { display: flex; align-items: center; gap: 8px; }
.room-badge { font-size: 14px; font-weight: 600; color: var(--app-primary); }
.scene-card { border-radius: 12px; overflow: hidden; }
.panel-card { border-radius: 12px; }
.rack-info .ri-title { font-size: 16px; font-weight: 700; margin-bottom: 8px; }
.rack-info .ri-sub { font-size: 12px; color: var(--app-text-muted); font-weight: 400; margin-left: 6px; }
.dev-list { max-height: 260px; overflow-y: auto; }
.dev-row { display: flex; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px dashed var(--app-border,#e5e7eb); font-size: 12px; }
.dev-u { width: 34px; color: #7b1fa2; font-weight: 600; flex-shrink: 0; }
.dev-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dev-cat { color: #607D8B; flex-shrink: 0; font-size: 11px; }
</style>
