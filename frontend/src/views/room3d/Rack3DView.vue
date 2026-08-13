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
          <span class="room-badge" v-if="room?.name">{{ room.name }} · {{ room.code }}<template v-if="room?.floor"> · {{ room.floor }}</template></span>
          <el-tooltip v-if="sceneData?.temperature?.avg != null" content="机房环境温度(来自传感器)">
            <el-tag size="small" :type="tempType(sceneData.temperature.avg)" effect="dark"><el-icon :size="12" style="margin-right:3px"><ColdDrink /></el-icon>{{ sceneData.temperature.avg }}℃</el-tag>
          </el-tooltip>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="loadData">刷新</el-button>
          <el-button :icon="View" @click="sceneRef?.resetView()">复位视角</el-button>
          <el-button type="primary" :icon="Grid" @click="go2d">切换到 2D 视图</el-button>
        </div>
      </div>
    </el-card>
    <el-row :gutter="12">
      <el-col :span="18">
        <el-card shadow="never" class="scene-card">
          <Rack3DScene v-if="sceneData" ref="sceneRef" :data="sceneData" :history="historyData" @select-rack="onSelectRack" @selection-change="onSelectionChange" @box-select="onBoxSelect" />
          <el-empty v-else-if="!loading" description="该机房暂无数据" :image-size="80" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="never" class="panel-card">
          <template #header><b>机柜信息</b></template>
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
              <div v-for="d in selectedRack.devices" :key="d.id" class="dev-row">
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
import { ref, computed, onMounted } from 'vue'
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

const catColors: Record<string, string> = {
  server: '#2196F3', network: '#4CAF50', storage: '#9C27B0', security: '#FF9800', power: '#F44336',
}
function catColorText(c: string): string { return catColors[c] || '#607D8B' }
function utilType(u: number): string { return u >= 80 ? 'danger' : u >= 50 ? 'warning' : 'success' }
function tempType(t: number): string { return t >= 32 ? 'danger' : t >= 27 ? 'warning' : 'success' }
function powerColor(p: number): string { return p >= 90 ? '#e74c3c' : p >= 70 ? '#e67e22' : '#27ae60' }

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

async function switchRoom(id: number) {
  if (id === roomId.value) return
  roomId.value = id
  try {
    await router.replace({ query: { ...route.query, room_id: id } })
  } catch { /* 仅更新 URL query，忽略导航结果 */ }
  await loadData()
}
function onSelectRack(rack: any) { selectedRack.value = rack }
function onSelectionChange(count: number) { if (count === 0) selectedRack.value = null }
function onBoxSelect(ids: number[]) {
  if (ids.length) {
    selectedRack.value = {
      multi: true, ids,
      racks: ids.map((id: number) => (sceneData.value?.racks || []).find((r: any) => r.id === id)).filter(Boolean),
    }
  } else {
    selectedRack.value = null
  }
}
function go2d() { router.push({ name: 'Racks', query: { room_id: roomId.value } }) }
function go2dDetail() {
  if (selectedRack.value && !selectedRack.value.multi) router.push({ name: 'Racks', query: { room_id: roomId.value, rack: selectedRack.value.id } })
}

onMounted(async () => {
  await loadRooms()
  await loadData()
})
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