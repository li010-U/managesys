<template>
  <div class="rack3d-scene" :class="{ clean: cleanMode }" ref="wrapRef">
    <div ref="mountRef" class="rack3d-canvas"></div>
    <div class="rack3d-box" v-if="boxSelecting" ref="boxEl" :style="boxStyle"></div>
    <div v-if="!ready" class="rack3d-loading"><span>正在加载 3D 场景…</span></div>
    <div class="rack3d-hint" v-if="!cleanMode">左键旋转 · 右键平移 · 滚轮缩放 · 点击机柜选中 · Shift+点击多选 · B 进入框选</div>
    <button v-if="cleanMode" class="rack3d-exit" @click.stop="toggleClean">退出干净模式</button>
    <div class="rack3d-status" v-if="deviceCount">
      <span>{{ racks }} 个机柜 · {{ deviceCount }} 台设备 · {{ sensorCount }} 个传感器</span>
      <span v-if="props.data?.temperature?.avg != null" class="rb-temp">· 🌡 机房 {{ props.data.temperature.avg }}℃</span>
      <span class="rb-selected" v-if="selectedCount">· 已选 {{ selectedCount }}</span>
      <span class="rb-alert" v-if="playing">· ⏱ 回放中 {{ playTimeLabel }}</span>
    </div>
    <div class="rack3d-layerbar">
      <button class="lb-btn" :class="{active: layer==='util'}" @click.stop="setLayer('util')">利用率</button>
      <button class="lb-btn" :class="{active: layer==='power'}" @click.stop="setLayer('power')">功率负载</button>
      <button class="lb-btn" :class="{active: layer==='temp'}" @click.stop="setLayer('temp')">温度热力</button>
      <button class="lb-btn" :class="{active: showLabels}" @click.stop="toggleLabels">代号</button>
      <button class="lb-btn" @click.stop="nextAlert">告警聚焦</button>
      <button class="lb-btn" :class="{active: boxSelectMode}" @click.stop="toggleBoxSelect">框选</button>
      <button class="lb-btn" :class="{active: showRoomHeat}" @click.stop="toggleRoomHeat">房间热力</button>
      <button class="lb-btn" :class="{active: cleanMode}" @click.stop="toggleClean">干净</button>
    </div>
    <div class="rack3d-legend" v-if="legendItems.length">
      <div class="lg-title">图例 · {{ legendTitle }}</div>
      <div class="lg-row" v-for="li in legendItems" :key="li.label">
        <span class="lg-swatch" :style="{background: li.color}"></span>
        <span class="lg-text">{{ li.label }}</span>
      </div>
    </div>
    <div class="rack3d-playbar" v-if="historyLen > 1">
      <button class="lb-btn" @click.stop="togglePlay">{{ playing ? '暂停' : '回放' }}</button>
      <input type="range" class="play-range" :min="0" :max="historyLen-1" :value="playIndex" @input="onSeek" />
      <span class="play-idx">{{ playIndex + 1 }} / {{ historyLen }}</span>
    </div>
    <button class="rack3d-export" @click.stop="exportImage" title="导出当前视角为 PNG 图片">导出图片</button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DRenderer, CSS2DObject } from 'three/examples/jsm/renderers/CSS2DRenderer.js'

const props = defineProps<{ data: any; history?: any[]; config?: any }>()
const emit = defineEmits<{
  (e: 'select-rack', rack: any): void
  (e: 'selection-change', count: number): void
  (e: 'box-select', rackIds: number[]): void
}>()

const wrapRef = ref<HTMLDivElement | null>(null)
const mountRef = ref<HTMLDivElement | null>(null)
const boxEl = ref<HTMLDivElement | null>(null)
const ready = ref(false)

const racks = ref(0)
const deviceCount = ref(0)
const sensorCount = ref(0)
const selectedCount = ref(0)
const layer = ref('util')
const showLabels = ref(true)
const showRoomHeat = ref(false)
const cleanMode = ref(false)
const boxSelectMode = ref(false)
const boxSelecting = ref(false)
const boxStyle = ref({ left: '0px', top: '0px', width: '0px', height: '0px' })

const legendTitle = computed(() => layer.value === 'util' ? '利用率' : layer.value === 'power' ? '功率负载' : '温度热力')
const legendItems = computed<{ label: string; color: string }[]>(() => {
  if (layer.value === 'temp') {
    return [
      { label: '≥34℃ 高温', color: '#e53935' },
      { label: '31–34℃', color: '#ff7043' },
      { label: '28–31℃', color: '#ffca28' },
      { label: '25–28℃', color: '#66bb6a' },
      { label: '<25℃ 低温', color: '#26a69a' },
    ]
  }
  if (layer.value === 'power') {
    return [
      { label: '≥90% 过载', color: '#e53935' },
      { label: '70–90%', color: '#ff9800' },
      { label: '40–70%', color: '#66bb6a' },
      { label: '<40%', color: '#26a69a' },
    ]
  }
  return [
    { label: '≥80% 高利用', color: '#e74c3c' },
    { label: '50–80%', color: '#e67e22' },
    { label: '<50%', color: '#27ae60' },
  ]
})

// ---- 尺寸常量 ----
const RACK_W = 0.6
const RACK_D = 1.0
const U_H = 0.04445
const COL_SPACING = 1.3
const ROW_SPACING = 1.7

const catColors: Record<string, number> = {
  server: 0x2196F3, network: 0x4CAF50, storage: 0x9C27B0, security: 0xFF9800, power: 0xF44336,
}

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let labelRenderer: CSS2DRenderer
let controls: OrbitControls
let raycaster = new THREE.Raycaster()
let pointer = new THREE.Vector2()
let rafId = 0
let resizeObs: ResizeObserver | null = null
let floorHeat: THREE.Mesh | null = null
let heatBounds = { cx: 0, cz: 0, w: 20, d: 20 }
let needsRender = true

// 对象注册表
const rackObjs = new Map<number, {
  rack: any
  group: THREE.Group
  body: THREE.Mesh
  door?: THREE.Mesh
  aisle?: THREE.Mesh
  warn?: THREE.Mesh
  label?: CSS2DObject | null
  deviceGroup?: THREE.Group
}>()
const selectedSet = new Set<number>()

// 共享材质
const sharedMats: Record<string, THREE.MeshPhongMaterial> = {}
const sharedDoorMats: Record<string, THREE.MeshPhongMaterial> = {}

// 框选起点（屏幕坐标）
let boxStartX = 0
let boxStartY = 0

// 历史回放
const history = ref<any[]>(props.history || [])
const historyLen = ref((props.history || []).length)
const playIndex = ref(0)
const playing = ref(false)
const playTimeLabel = ref('')
let playTimer: number | null = null

function utilColor(util: number): number { return util >= 80 ? 0xe74c3c : util >= 50 ? 0xe67e22 : 0x27ae60 }
function powerColor(pct: number): number {
  if (pct == null) return 0x90a4ae
  return pct >= 90 ? 0xe53935 : pct >= 70 ? 0xff9800 : pct >= 40 ? 0x66bb6a : 0x26a69a
}
function heatColor(t?: number): number {
  if (t == null) return 0x90a4ae
  if (t >= 34) return 0xe53935
  if (t >= 31) return 0xff7043
  if (t >= 28) return 0xffca28
  if (t >= 25) return 0x66bb6a
  return 0x26a69a
}
function sharedMat(opacity: number, key: string, color: number): THREE.MeshPhongMaterial {
  if (!sharedMats[key]) sharedMats[key] = new THREE.MeshPhongMaterial({ color, transparent: true, opacity })
  return sharedMats[key]
}
function sharedDoorMat(opacity: number, key: string, color: number): THREE.MeshPhongMaterial {
  if (!sharedDoorMats[key]) sharedDoorMats[key] = new THREE.MeshPhongMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide })
  return sharedDoorMats[key]
}

function layerColor(rack: any): number {
  if (layer.value === 'power') return powerColor(rack.power_load_pct)
  if (layer.value === 'temp') return heatColor(rack.temperature)
  return utilColor(rack.utilization || 0)
}

function buildPositions(rackList: any[]) {
  let idx = 0
  const placements = rackList.map((r: any) => {
    let x: number, z: number
    const hasWorld = typeof r.pos_x_m === 'number' || typeof r.pos_z_m === 'number'
    const hasRowCol = typeof r.row_pos === 'number' && typeof r.col_pos === 'number'
    if (hasWorld) { x = r.pos_x_m ?? 0; z = r.pos_z_m ?? 0 }
    else if (hasRowCol) { x = (r.col_pos - 1) * COL_SPACING; z = (r.row_pos - 1) * ROW_SPACING }
    else {
      idx++
      const side = Math.ceil(Math.sqrt(rackList.length))
      x = (idx - 1) % side * COL_SPACING
      z = Math.floor((idx - 1) / side) * ROW_SPACING
    }
    return { rack: r, x, z, width: r.width_m ?? RACK_W, depth: r.depth_m ?? RACK_D, yaw: r.facing_deg ?? 0 }
  })
  const xs = placements.map(p => p.x)
  const zs = placements.map(p => p.z)
  const minX = xs.length ? Math.min(...xs) : 0
  const maxX = xs.length ? Math.max(...xs) : 1
  const minZ = zs.length ? Math.min(...zs) : 0
  const maxZ = zs.length ? Math.max(...zs) : 1
  return { placements, minX, maxX, minZ, maxZ }
}

function init() {
  const el = mountRef.value!
  const w = el.clientWidth || 800
  const h = el.clientHeight || 600

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf5f7fa)

  camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 1000)

  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.domElement.style.touchAction = 'none'
  el.appendChild(renderer.domElement)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.setSize(w, h)
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  el.appendChild(labelRenderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.1
  controls.target.set(0, 1.5, 0)

  const ambient = new THREE.AmbientLight(0xffffff, 0.65)
  scene.add(ambient)
  const hemi = new THREE.HemisphereLight(0xffffff, 0x8899aa, 0.35)
  scene.add(hemi)
  const dir = new THREE.DirectionalLight(0xffffff, 0.85)
  dir.position.set(10, 20, 10)
  scene.add(dir)
  const dir2 = new THREE.DirectionalLight(0xffffff, 0.3)
  dir2.position.set(-10, 10, -10)
  scene.add(dir2)

  el.addEventListener('click', onClick)
  el.addEventListener('pointerdown', onPointerDown)
  el.addEventListener('pointermove', onPointerMove)
  el.addEventListener('pointerup', onPointerUp)
  el.addEventListener('pointerleave', onPointerUp)
  window.addEventListener('keydown', onKey)

  let lastFrame = 0
  const renderLoop = (ts: number = 0) => {
    rafId = requestAnimationFrame(renderLoop)
    controls.update()
    updateLod()
    updateWarnFlash(ts)
    if (needsRender) {
      renderer.render(scene, camera)
      labelRenderer.render(scene, camera)
      needsRender = false
      lastFrame = ts
    } else if (ts - lastFrame > 66) {
      renderer.render(scene, camera)
      labelRenderer.render(scene, camera)
      lastFrame = ts
    }
  }
  controls.addEventListener('start', () => { needsRender = true })
  controls.addEventListener('change', () => { needsRender = true })
  controls.addEventListener('end', () => { needsRender = true })

  resizeObs = new ResizeObserver(() => resize())
  if (wrapRef.value) resizeObs.observe(wrapRef.value)

  renderLoop()
  ready.value = true
}

function resize() {
  if (!mountRef.value || !renderer) return
  const w = mountRef.value.clientWidth || 800
  const h = mountRef.value.clientHeight || 600
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
  labelRenderer.setSize(w, h)
  needsRender = true
}

function buildFloor(placements: any) {
  const { minX, maxX, minZ, maxZ } = placements
  const cx = (minX + maxX) / 2
  const cz = (minZ + maxZ) / 2
  const size = Math.max(maxX - minX, maxZ - minZ, 6)
  camera.position.set(cx + size * 0.3, Math.max(size * 0.9, 8), cz + size * 1.5)
  controls.target.set(cx, 1.5, cz)

  const pad = 2.0
  const floorW = Math.max(maxX - minX, 2) + pad * 2
  const floorD = Math.max(maxZ - minZ, 2) + pad * 2
  const floorGeo = new THREE.PlaneGeometry(floorW, floorD)
  const floorMat = new THREE.MeshStandardMaterial({ color: 0xdfe6ee, side: THREE.DoubleSide })
  const floor = new THREE.Mesh(floorGeo, floorMat)
  floor.rotation.x = -Math.PI / 2
  floor.position.set(cx, 0, cz)
  scene.add(floor)

  const grid = new THREE.GridHelper(Math.max(floorW, floorD), Math.max(8, Math.round(Math.max(floorW, floorD) / 1.0)), 0x94a3b8, 0xcdd5e0)
  grid.position.set(cx, 0.01, cz)
  scene.add(grid)

  // 米制刻度：沿 X 轴（下）与 Z 轴（左）
  const rulerLen = Math.max(floorW, floorD, 2)
  const rulerMat = new THREE.LineBasicMaterial({ color: 0x78909c })
  const ruler = new THREE.Group()
  const pts = [new THREE.Vector3(cx - rulerLen / 2, 0.012, minZ - pad * 0.4), new THREE.Vector3(cx + rulerLen / 2, 0.012, minZ - pad * 0.4)]
  ruler.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), rulerMat))
  const zpts = [new THREE.Vector3(minX - pad * 0.4, 0.012, cz - rulerLen / 2), new THREE.Vector3(minX - pad * 0.4, 0.012, cz + rulerLen / 2)]
  ruler.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(zpts), rulerMat))
  for (let v = Math.ceil(cx - rulerLen / 2); v <= Math.floor(cx + rulerLen / 2); v += 1) {
    ruler.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(v, 0.012, minZ - pad * 0.4 - 0.12),
      new THREE.Vector3(v, 0.012, minZ - pad * 0.4 + 0.12),
    ]), rulerMat))
  }
  for (let v = Math.ceil(cz - rulerLen / 2); v <= Math.floor(cz + rulerLen / 2); v += 1) {
    ruler.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(minX - pad * 0.4 - 0.12, 0.012, v),
      new THREE.Vector3(minX - pad * 0.4 + 0.12, 0.012, v),
    ]), rulerMat))
  }
  ruler.userData.isRuler = true
  scene.add(ruler)
  heatBounds = { cx, cz, w: floorW, d: floorD }
}

function clearRoomHeat() {
  if (floorHeat) { scene.remove(floorHeat); floorHeat = null }
}

function roomHeatStep(temp?: number): string {
  if (temp == null) return 'rgba(158,158,169,0.25)'
  if (temp >= 34) return 'rgba(229,57,53,0.75)'
  if (temp >= 31) return 'rgba(255,112,67,0.62)'
  if (temp >= 28) return 'rgba(255,202,40,0.5)'
  if (temp >= 25) return 'rgba(102,187,106,0.5)'
  return 'rgba(38,166,154,0.45)'
}

function buildRoomHeat() {
  clearRoomHeat()
  const S = 128
  const canvas = document.createElement('canvas')
  canvas.width = S; canvas.height = S
  const ctx = canvas.getContext('2d')!
  ctx.clearRect(0, 0, S, S)
  // 底图：机房平均色
  const avg = props.data?.temperature?.avg
  ctx.fillStyle = roomHeatStep(avg)
  ctx.fillRect(0, 0, S, S)
  // 每台机柜按其温度画一个径向热点
  rackObjs.forEach((rec) => {
    const t = rec.rack.temperature
    if (t == null) return
    const px = (rec.group.position.x - (heatBounds.cx - heatBounds.w / 2)) / heatBounds.w * S
    const py = (rec.group.position.z - (heatBounds.cz - heatBounds.d / 2)) / heatBounds.d * S
    const x = Math.min(S, Math.max(0, px))
    const y = Math.min(S, Math.max(0, py))
    const col = roomHeatStep(t)
    const r = Math.max(8, Math.min(S, S * 0.14))
    const g = ctx.createRadialGradient(x, y, 0, x, y, r)
    g.addColorStop(0, col)
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = g
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill()
    // 等温线：以机柜为中心绘制两级虚线等温环（随温度阈值上色）
    ctx.setLineDash([3, 3])
    ctx.strokeStyle = t >= 34 ? 'rgba(183,28,28,0.55)' : t >= 31 ? 'rgba(230,74,25,0.5)' : t >= 28 ? 'rgba(245,124,0,0.45)' : 'rgba(27,94,32,0.5)'
    ctx.lineWidth = 1
    for (const k of [0.6, 0.95]) {
      ctx.beginPath(); ctx.arc(x, y, r * k, 0, Math.PI * 2); ctx.stroke()
    }
    ctx.setLineDash([])
    // 高亮文本：机柜温度
    ctx.fillStyle = t >= 31 ? '#c62828' : '#374151'
    ctx.font = '7px sans-serif'
    ctx.textAlign = 'center'
    ctx.fillText(String(Math.round(t * 10) / 10), x, y + 2)
  })
  const tex = new THREE.CanvasTexture(canvas)
  const plane = new THREE.Mesh(
    new THREE.PlaneGeometry(heatBounds.w, heatBounds.d),
    new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.75, depthWrite: false })
  )
  plane.rotation.x = -Math.PI / 2
  plane.position.set(heatBounds.cx, 0.02, heatBounds.cz)
  plane.renderOrder = 1
  floorHeat = plane
  scene.add(plane)
}

function toggleRoomHeat() {
  showRoomHeat.value = !showRoomHeat.value
  if (showRoomHeat.value) buildRoomHeat()
  else clearRoomHeat()
  needsRender = true
}
function toggleClean() {
  cleanMode.value = !cleanMode.value
  needsRender = true
}
async function exportImage() {
  if (!renderer) return
  try {
    // 1) 俯视 3D 快照：相机置于机房正上方，框选全部机柜
    const threeSnap = await topDownSnapshot()
    // 2) 2D U 位明细图
    const twoDSnap = build2DUCanvas(props.data?.racks || [])
    // 3) 合成一张图片：标题 + 俯视 3D + 2D U 位明细
    const composite = composeExportImage(threeSnap, twoDSnap)

    const a = document.createElement('a')
    const ts = new Date().toISOString().replace(/[:.]/g, '-')
    const rm = props.data?.room
    const name = (rm?.code || 'room') + '-机房3D与U位导出-' + ts + '.png'
    a.href = composite.toDataURL('image/png')
    a.download = name
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  } catch (e) {
    console.error('导出图片失败', e)
  }
  needsRender = true
}

// 俯视 3D 快照：不改动实时相机，用克隆相机从正上方取景全部机柜
async function topDownSnapshot() {
  const bigW = 1600, bigH = 900
  const racks: any[] = props.data?.racks || []
  const pos = buildPositions(racks)
  let spanX = 8, spanZ = 8
  let cx = 0, cz = 0
  if (racks.length) {
    const hw = racks.map((r, i) => (pos.placements[i]?.width || 0.6) / 2)
    const hd = racks.map((r, i) => (pos.placements[i]?.depth || 0.6) / 2)
    const bminX = pos.minX - Math.max(...hw)
    const bmaxX = pos.maxX + Math.max(...hw)
    const bminZ = pos.minZ - Math.max(...hd)
    const bmaxZ = pos.maxZ + Math.max(...hd)
    spanX = Math.max(bmaxX - bminX, 6)
    spanZ = Math.max(bmaxZ - bminZ, 6)
    cx = (bminX + bmaxX) / 2
    cz = (bminZ + bmaxZ) / 2
  }

  const margin = 2.5
  const fov = THREE.MathUtils.degToRad(camera.fov)
  const aspect = bigW / bigH
  const hFov = 2 * Math.atan(Math.tan(fov / 2) * aspect)
  const distX = (spanX / 2 + margin) / Math.tan(hFov / 2)
  const distZ = (spanZ / 2 + margin) / Math.tan(fov / 2)
  const dist = Math.max(distX, distZ, 6)

  const cam = camera.clone()
  cam.fov = camera.fov
  cam.aspect = aspect
  cam.up.set(0, 0, -1)
  cam.position.set(cx, dist, cz)
  cam.lookAt(cx, 0, cz)
  cam.updateProjectionMatrix()

  const tmp = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  tmp.setSize(bigW, bigH, false)
  tmp.setPixelRatio(1)
  tmp.render(scene, cam)
  const url = tmp.domElement.toDataURL('image/png')
  tmp.dispose()
  // 等待图片解码完成，否则 drawImage 会画出空白
  const img = new Image()
  img.src = url
  await img.decode().catch(() => new Promise((res) => { img.onload = res; img.onerror = res }))

  // 在 3D 俯视图上标注机柜代号：机柜上只放紧凑编号徽标，右侧附“编号→完整代号”图例，
  // 避免长代号标签互相重叠、也保证完整代号一定可读
  const out = document.createElement('canvas')
  out.width = bigW; out.height = bigH
  const g = out.getContext('2d')!
  g.drawImage(img, 0, 0, bigW, bigH)
  const v = new THREE.Vector3()
  const pits = pos.placements || []
  const items: any[] = pits.map((pl: any, i: number) => {
    const rack = racks[i] as any
    const height = (rack?.total_units || 42) * U_H
    v.set(pl.x, height, pl.z).project(cam)
    const sx = (v.x * 0.5 + 0.5) * bigW
    const sy = (-v.y * 0.5 + 0.5) * bigH
    const show = v.z <= 1 && sx >= -60 && sx <= bigW + 60 && sy >= -30 && sy <= bigH + 60
    return { sx, sy, code: rack ? (rack.code || ('Rack' + rack.id)) : '', show }
  })
  const visible = items.filter(i => i.show)
  // 右侧图例面板：编号 -> 完整代号
  const legend = { x: 12, y: 12, w: 230, pad: 10, rowH: 20 }
  g.globalAlpha = 0.94
  g.fillStyle = '#ffffff'
  g.strokeStyle = '#c9d3dd'
  g.lineWidth = 1
  roundRect(g, legend.x, legend.y, legend.w, 36 + visible.length * legend.rowH + 6, 6)
  g.fill(); g.stroke()
  g.globalAlpha = 1
  g.fillStyle = '#1f2937'
  g.font = 'bold 13px "Microsoft YaHei", sans-serif'
  g.textAlign = 'left'
  g.textBaseline = 'middle'
  g.fillText('机柜代号', legend.x + legend.pad, legend.y + 18)
  g.font = '12px "Microsoft YaHei", sans-serif'
  items.forEach((it, i) => {
    if (!it.show) return
    const ly = legend.y + 36 + (i) * legend.rowH + 8
    // 对应编号徽标（颜色与机柜标记一致）
    g.fillStyle = badgeColor(i)
    roundRect(g, legend.x + legend.pad, ly - 8, 18, 16, 3)
    g.fill()
    g.fillStyle = '#ffffff'
    g.font = 'bold 11px sans-serif'
    g.textAlign = 'center'
    g.fillText(String(i + 1), legend.x + legend.pad + 9, ly)
    g.fillStyle = '#374151'
    g.font = '12px "Microsoft YaHei", sans-serif'
    g.textAlign = 'left'
    g.fillText(shortText(it.code, 18), legend.x + legend.pad + 26, ly)
  })
  // 每个机柜顶部的编号徽标 + 指向机身
  items.forEach((it, i) => {
    if (!it.show) return
    const bx = Math.max(30, Math.min(it.sx - 10, bigW - 44))
    const by = Math.max(30, Math.min(it.sy - 34, bigH - 30))
    g.strokeStyle = 'rgba(31,41,55,0.5)'
    g.lineWidth = 1
    g.beginPath(); g.moveTo(bx + 10, by + 20); g.lineTo(it.sx, Math.min(it.sy, by + 34)); g.stroke()
    g.fillStyle = badgeColor(i)
    roundRect(g, bx, by, 20, 20, 4)
    g.fill()
    g.strokeStyle = '#ffffff'
    g.lineWidth = 1.5
    g.stroke()
    g.fillStyle = '#ffffff'
    g.font = 'bold 12px sans-serif'
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText(String(i + 1), bx + 10, by + 11)
  })
  const outUrl = out.toDataURL('image/png')
  const outImg = new Image()
  outImg.src = outUrl
  await outImg.decode().catch(() => new Promise((res) => { outImg.onload = res; outImg.onerror = res }))
  return { img: outImg, bigW, bigH }
}

// 2D U 位明细：每台机柜一张“卡片”，从上到下绘制 U=total..1 的占用状态
function build2DUCanvas(racks: any[]) {
  if (!racks.length) {
    const c = document.createElement('canvas')
    c.width = 800; c.height = 200
    const g = c.getContext('2d')!
    g.fillStyle = '#fafafa'; g.fillRect(0, 0, 800, 200)
    g.fillStyle = '#666'; g.font = 'bold 20px sans-serif'
    g.textAlign = 'center'
    g.fillText('该机房暂无机柜数据', 400, 100)
    return c
  }
  const cellH = 12, cellW = 34, uLabelW = 16, cardHeadH = 42, cardFootH = 54, padX = 10
  const cardW = uLabelW + cellW + padX * 2 + 50
  const maxW = 1200
  const perRow = Math.max(1, Math.floor(maxW / cardW))
  const rows = Math.ceil(racks.length / perRow)
  const maxU = Math.max(...racks.map((r: any) => r.total_units || 42))
  const cardH = cardHeadH + maxU * cellH + cardFootH

  const W = Math.min(maxW, perRow * cardW)
  const H = rows * cardH + 60
  const c = document.createElement('canvas')
  c.width = W; c.height = H
  const g = c.getContext('2d')!

  const statusColor = (s: string) => {
    if (s === 'running') return '#2f9e44'
    if (s === 'offline' || s === 'error' || s === 'fault') return '#e03131'
    return '#5c7cfa' // mounted / in_stock / other
  }
  const categoryColor = (cat: string) => {
    const map: Record<string, string> = { server: '#2196F3', network: '#4CAF50', storage: '#9C27B0', security: '#FF9800', power: '#F44336' }
    return map[cat] || '#607D8B'
  }

  g.fillStyle = '#fbfdff'; g.fillRect(0, 0, W, H)

  racks.forEach((rack: any, ri: number) => {
    const row = Math.floor(ri / perRow)
    const col = ri % perRow
    const ox = col * cardW
    const oy = row * cardH + 30

    // 卡片背景
    g.fillStyle = '#ffffff'
    g.strokeStyle = '#d7dee6'
    g.lineWidth = 1
    roundRect(g, ox, oy, cardW - 4, cardH, 6)
    g.fill(); g.stroke()

    // 头部：机柜代号
    g.fillStyle = '#1f2937'
    g.font = 'bold 13px sans-serif'
    g.textAlign = 'left'
    g.fillText(rack.code || ('Rack' + rack.id), ox + 8, oy + 18)
    g.font = '11px sans-serif'
    g.fillStyle = '#6b7280'
    g.fillText((rack.utilization ?? 0) + '% 利用', ox + 8, oy + 32)

    const totalU = rack.total_units || 42
    const devices = rack.devices || []
    const occupied: Record<number, any> = {}
    devices.forEach((d: any) => {
      const s = Math.min(d.start_u, totalU)
      const e = Math.min(d.end_u || d.start_u, totalU)
      for (let u = s; u <= e; u++) occupied[u] = d
    })

    const diagX = ox + uLabelW + 4
    const footY = oy + cardHeadH + totalU * cellH

    // U 编号 + 单元格
    for (let u = totalU; u >= 1; u--) {
      const rowY = oy + cardHeadH + (totalU - u) * cellH
      g.fillStyle = '#9aa4b0'
      g.font = '9px sans-serif'
      g.textAlign = 'right'
      g.fillText(String(u), ox + uLabelW - 3, rowY + cellH - 3)
      const d = occupied[u]
      g.fillStyle = d ? categoryColor(d.device_type_category) : '#eef1f4'
      g.strokeStyle = d ? '#c9d3dd' : '#e2e7ec'
      g.beginPath(); g.rect(diagX, rowY, cellW, cellH - 1); g.fill(); g.stroke()
    }

    // 设备名称标注（占位大于等于2U才显示，避免拥挤）
    devices.forEach((d: any) => {
      const s = Math.min(d.start_u, totalU)
      const e = Math.min(d.end_u || d.start_u, totalU)
      const topU = s; const span = (e - s) + 1
      if (span < 2) return
      const rowY = oy + cardHeadH + (totalU - topU) * cellH
      if (span * cellH < 16) return
      g.fillStyle = '#ffffff'
      g.font = 'bold 9px sans-serif'
      g.textAlign = 'left'
      g.fillText(shortText(d.name, 5), diagX + 3, rowY + Math.min(span * cellH, 14) - 3)
    })

    // 底部：统计
    g.fillStyle = '#374151'
    g.font = '11px sans-serif'
    g.textAlign = 'left'
    const usedU = Object.keys(occupied).length
    g.fillText('占用 ' + usedU + '/' + totalU + 'U', ox + 8, footY + 16)
    g.fillText('设备 ' + (rack.device_count ?? devices.length) + ' 台', ox + 8, footY + 30)
    g.fillText('功率 ' + (rack.power_load ?? 0) + ' kW', ox + 8, footY + 44)
  })

  return c
}

function roundRect(g: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  g.beginPath()
  g.moveTo(x + r, y)
  g.arcTo(x + w, y, x + w, y + h, r)
  g.arcTo(x + w, y + h, x, y + h, r)
  g.arcTo(x, y + h, x, y, r)
  g.arcTo(x, y, x + w, y, r)
  g.closePath()
}
function badgeColor(i: number) {
  const palette = ['#e74c3c', '#e67e22', '#f1c40f', '#27ae60', '#16a085', '#2980b9', '#8e44ad', '#d35400', '#16a085', '#2c3e50', '#c0392b', '#d4ac0d']
  return palette[i % palette.length]
}
function shortText(s: string, n: number) {
  if (!s) return ''
  return s.length > n ? s.slice(0, n) + '…' : s
}

// 合成最终导出图
function composeExportImage(three: { img: HTMLImageElement; bigW: number; bigH: number }, two: HTMLCanvasElement) {
  const rm = props.data?.room
  const titleH = 56
  const gap = 16
  const W = Math.max(three.bigW, two.width)
  const H = titleH + three.bigH + gap + two.height + 30
  const c = document.createElement('canvas')
  c.width = W; c.height = H
  const g = c.getContext('2d')!

  g.fillStyle = '#ffffff'; g.fillRect(0, 0, W, H)

  // 标题
  g.fillStyle = '#1f2937'
  g.font = 'bold 22px "Microsoft YaHei", sans-serif'
  g.textAlign = 'left'
  const title = (rm?.name || '') + (rm?.code ? ' · ' + rm.code : '') + (rm?.floor ? ' · ' + rm.floor : '')
  g.fillText(title || '机房 3D 视图导出', 20, 36)
  g.font = '12px "Microsoft YaHei", sans-serif'
  g.fillStyle = '#6b7280'
  const ts = new Date().toLocaleString('zh-CN')
  g.textAlign = 'right'
  g.fillText('渲染时间：' + ts + ' · 当前图层：' + layerLabel(), W - 20, 36)

  // 小节标题 + 3D 俯视图
  g.textAlign = 'left'; g.fillStyle = '#374151'; g.font = 'bold 14px "Microsoft YaHei", sans-serif'
  g.fillText('① 俯视 3D 布局（全部机柜）', 20, titleH + 22)
  const threeScale = W / three.bigW
  g.drawImage(three.img, 0, titleH + 30, W, three.bigH * threeScale)

  // 小节标题 + 2D U 位明细
  g.textAlign = 'left'
  g.font = 'bold 14px "Microsoft YaHei", sans-serif'
  g.fillStyle = '#374151'
  const twoTop = titleH + 30 + three.bigH * threeScale + gap
  g.fillText('② 2D U 位明细（每台机柜自下而上 U=1..' + (props.data?.racks?.length ? Math.max(...(props.data.racks as any).map((r: any) => r.total_units || 42)) : '') + '）', 20, twoTop + 22)
  g.drawImage(two, 0, twoTop + 30, two.width, two.height)

  return c
}

function layerLabel() {
  const map: Record<string, string> = { util: '利用率', power: '功率负载', temp: '温度热力' }
  return map[layer.value] || '利用率'
}
function buildRackMesh(pl: any, applyLabel = true) {
  const rack = pl.rack
  const width = pl.width || RACK_W
  const depth = pl.depth || RACK_D
  const height = (rack.total_units || 42) * U_H

  const group = new THREE.Group()
  group.position.set(pl.x, 0, pl.z)
  group.rotation.y = THREE.MathUtils.degToRad(pl.yaw)

  const color = layerColor(rack)
  const bodyGeo = new THREE.BoxGeometry(width, height, depth)
  const body = new THREE.Mesh(bodyGeo, sharedMat(0.92, 'b' + color, color))
  body.position.y = height / 2
  body.userData.rack = rack
  group.add(body)

  const edgeGeo = new THREE.EdgesGeometry(bodyGeo)
  const edge = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: 0x37474f }))
  edge.position.y = height / 2
  edge.userData.rack = rack
  group.add(edge)

  const door = new THREE.Mesh(new THREE.PlaneGeometry(width, height), sharedDoorMat(0.18, 'd' + color, color))
  door.position.set(0, height / 2, depth / 2 + 0.005)
  door.userData.rack = rack
  group.add(door)

  const aisleMat = new THREE.MeshBasicMaterial({ color: 0x81c784, transparent: true, opacity: 0.22, side: THREE.DoubleSide })
  const aisle = new THREE.Mesh(new THREE.PlaneGeometry(width, depth * 0.6), aisleMat)
  aisle.position.set(0, 0.03, depth / 2 + depth * 0.3)
  aisle.userData.rack = rack
  group.add(aisle)

  let warn: THREE.Mesh | undefined
  if ((rack.alerts || 0) > 0) {
    warn = new THREE.Mesh(new THREE.ConeGeometry(0.25, 0.5, 16), new THREE.MeshPhongMaterial({ color: 0xe74c3c, emissive: 0x7f0000, transparent: true }))
    warn.position.set(0, height + 0.4, 0)
    warn.userData.rack = rack
    warn.userData.isAlert = true
    group.add(warn)
  }

  let label: CSS2DObject | null = null
  if (applyLabel) {
    const labelDiv = document.createElement('div')
    labelDiv.className = 'rack3d-label'
    labelDiv.textContent = rack.code || ''
    const tempNote = rack.temperature != null ? ('\n机柜温度 ' + rack.temperature + '℃') : ''
    labelDiv.title = rack.code + ' ' + rack.name +
      '\n利用率 ' + (rack.utilization || 0) + '%' +
      '\n功率负载 ' + (rack.power_load || 0) + 'kW' + (rack.power_load_pct ? (' (' + rack.power_load_pct + '%)') : '') +
      '\n额定功率 ' + (rack.rated_power || '—') + 'kW' +
      '\n告警 ' + (rack.alerts || 0) + tempNote
    labelDiv.dataset.rackId = String(rack.id)
    label = new CSS2DObject(labelDiv)
    label.position.set(0, height + 0.6, 0)
    label.userData.rack = rack
    group.add(label)
  }

  scene.add(group)
  rackObjs.set(rack.id, { rack, group, body, door, aisle, warn, label })
}

function clearRuleObjects() {
  const toRemove: THREE.Object3D[] = []
  scene.traverse(o => { if ((o as any).userData?.isRuler) toRemove.push(o) })
  toRemove.forEach(o => scene.remove(o))
}

// ---- 增量更新：只重建变化部分 ----
function applyDiff(newRacks: any[]) {
  const nextIds = new Set(newRacks.map((r: any) => r.id))
  const oldIds = Array.from(rackObjs.keys())
  // 删除消失的机柜
  for (const id of oldIds) {
    if (!nextIds.has(id)) {
      const rec = rackObjs.get(id)
      if (rec) scene.remove(rec.group)
      rackObjs.delete(id)
    }
  }
  // 更新已有（颜色）
  for (const r of newRacks) {
    const rec = rackObjs.get(r.id)
    if (rec) applyColor(r)
  }
  // 新增 + 布局变化则全量重建（位置变更走重建更安全）
  const placements = buildPositions(newRacks)
  const needAdd = newRacks.some(r => !rackObjs.has(r.id))
  const labelOn = showLabels.value && newRacks.length <= 40
  if (needAdd) {
    rackObjs.forEach(rec => scene.remove(rec.group))
    rackObjs.clear()
    for (const pl of placements.placements) buildRackMesh(pl, labelOn)
    rebuildDeviceViews()
    if (showRoomHeat.value) buildRoomHeat()
  } else {
    // 仅当已有且位置变化才重建（简化：有变化全量重建，这里只处理添加场景）
    for (const pl of placements.placements) {
      if (!rackObjs.has(pl.rack.id)) {
        buildRackMesh(pl, labelOn)
      }
    }
  }
  updateCounts(newRacks)
}

function rebuildDeviceViews() {
  rackObjs.forEach((rec) => {
    const hasDevices = (rec.rack?.devices?.length || 0) > 0
    const sel = selectedSet.has(rec.rack.id)
    const near = isNear(rec.group)
    if (rec.deviceGroup) { rec.group.remove(rec.deviceGroup); rec.deviceGroup = undefined }
    if (sel && near && hasDevices) buildDeviceGroup(rec)
  })
}

function buildDeviceGroup(rec: any) {
  const rack = rec.rack
  const width = rec.body.geometry.parameters.width as number
  const depth = rec.body.geometry.parameters.depth as number
  const height = (rack.total_units || 42) * U_H
  const devGroup = new THREE.Group()
  for (const d of rack.devices) {
    const us = (d.end_u ?? d.start_u) - (d.start_u ?? 0) + 1
    const uh = us * U_H
    const yBottom = (d.start_u ?? 1) - 1
    const centerY = yBottom * U_H + uh / 2
    const color = catColors[d.device_type_category] || 0x607D8B
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(width * 0.82, uh, depth * 0.5),
      new THREE.MeshPhongMaterial({ color, transparent: true, opacity: 0.92 })
    )
    box.position.set(0, centerY, depth * 0.05)
    box.userData.rack = rack
    box.userData.device = d
    devGroup.add(box)
  }
  rec.deviceGroup = devGroup
  rec.group.add(devGroup)
}

// ---- LOD：按距离裁剪细节 ----
function isNear(group: THREE.Group): boolean {
  if (!camera) return false
  const d = camera.position.distanceTo(group.position)
  return d < 22
}
function updateLod() {
  rackObjs.forEach((rec) => {
    const near = isNear(rec.group)
    const sel = selectedSet.has(rec.rack.id)
    if (rec.door) rec.door.visible = near
    if (rec.aisle) rec.aisle.visible = near
    if (rec.label) rec.label.visible = showLabels.value && (near || sel)
    if (rec.deviceGroup) rec.deviceGroup.visible = sel && near
  })
}

// ---- 告警闪烁 ----
function updateWarnFlash(ts: number) {
  const phase = (ts / 500) % 1
  const k = 0.6 + 0.4 * Math.sin(phase * Math.PI * 2)
  rackObjs.forEach((rec) => {
    if (rec.warn) {
      rec.warn.scale.set(1 + 0.2 * k, 1 + 0.2 * k, 1 + 0.2 * k)
      const m = rec.warn.material as THREE.MeshPhongMaterial
      m.opacity = 0.55 + 0.45 * k
    }
  })
}

function applyColor(rack: any) {
  const rec = rackObjs.get(rack.id)
  if (!rec) return
  const color = layerColor(rack)
  rec.body.material = sharedMat(0.92, 'b' + color, color)
  if (rec.door) rec.door.material = sharedDoorMat(0.18, 'd' + color, color)
}

function updateHighlight() {
  rackObjs.forEach((rec, id) => {
    const isSel = selectedSet.has(id)
    const bodyMat = rec.body.material as THREE.MeshPhongMaterial
    if (isSel) bodyMat.emissive.setHex(0x263238)
    else bodyMat.emissive.setHex(0x000000)
    bodyMat.needsUpdate = true
    const edge = rec.group.children.find((o: any) => o.isLineSegments) as THREE.LineSegments | undefined
    if (edge) (edge.material as THREE.LineBasicMaterial).color.set(isSel ? 0xff9800 : 0x37474f)
  })
  selectedCount.value = selectedSet.size
  emit('selection-change', selectedSet.size)
}

function updateCounts(list: any[]) {
  racks.value = list.length
  deviceCount.value = list.reduce((a: number, r: any) => a + (r.devices?.length || 0), 0)
  sensorCount.value = (props.data?.sensors || []).length
}

function buildScene() {
  const data = props.data
  if (!data) return
  rackObjs.forEach(r => scene.remove(r.group))
  rackObjs.clear()
  clearRuleObjects()
  const { placements, minX, maxX, minZ, maxZ } = buildPositions(data.racks || [])
  buildFloor({ minX, maxX, minZ, maxZ })
  updateCounts(data.racks || [])
  const labelOn = showLabels.value && (data.racks?.length || 0) <= 40
  for (const pl of placements) buildRackMesh(pl, labelOn)
  rebuildDeviceViews()
  if (showRoomHeat.value) buildRoomHeat()
}

function rackAtPointer(e: MouseEvent): any {
  const el = mountRef.value!
  const rect = el.getBoundingClientRect()
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const meshes = Array.from(rackObjs.values()).map(r => r.body)
  const hits = raycaster.intersectObjects(meshes, false)
  return hits.length ? hits[0].object.userData.rack : null
}

function onClick(e: MouseEvent) {
  if (boxSelectMode.value) return
  const rack = rackAtPointer(e)
  if (rack) {
    if (e.shiftKey) {
      if (selectedSet.has(rack.id)) selectedSet.delete(rack.id); else selectedSet.add(rack.id)
    } else {
      selectedSet.clear()
      selectedSet.add(rack.id)
    }
    updateHighlight()
    emit('select-rack', rack)
    const rec = rackObjs.get(rack.id)
    if (rec) {
      controls.target.set(rec.group.position.x, 1.5, rec.group.position.z)
      controls.update()
      rebuildDeviceViews()
    }
  } else if (!e.shiftKey) {
    selectedSet.clear()
    updateHighlight()
    emit('select-rack', null as any)
    rebuildDeviceViews()
  }
}

function onPointerDown(e: PointerEvent) {
  if (!boxSelectMode.value || e.button !== 0) return
  boxSelecting.value = true
  const rect = mountRef.value!.getBoundingClientRect()
  boxStartX = e.clientX - rect.left
  boxStartY = e.clientY - rect.top
  boxStyle.value = { left: boxStartX + 'px', top: boxStartY + 'px', width: '0px', height: '0px' }
}
function onPointerMove(e: PointerEvent) {
  if (boxSelecting.value) {
    const rect = mountRef.value!.getBoundingClientRect()
    const cx = e.clientX - rect.left
    const cy = e.clientY - rect.top
    const left = Math.min(cx, boxStartX)
    const top = Math.min(cy, boxStartY)
    boxStyle.value = { left: left + 'px', top: top + 'px', width: Math.abs(cx - boxStartX) + 'px', height: Math.abs(cy - boxStartY) + 'px' }
    return
  }
  // hover：仅更新射线起点，供 LOD 使用
  const el = mountRef.value!
  const rect = el.getBoundingClientRect()
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
}
function onPointerUp(e: PointerEvent) {
  if (!boxSelecting.value) return
  boxSelecting.value = false
  const el = mountRef.value!
  const rect = el.getBoundingClientRect()
  const rx = e.clientX - rect.left
  const ry = e.clientY - rect.top
  const x0 = Math.min(boxStartX, rx)
  const x1 = Math.max(boxStartX, rx)
  const y0 = Math.min(boxStartY, ry)
  const y1 = Math.max(boxStartY, ry)
  if (x1 - x0 < 6 || y1 - y0 < 6) { boxStyle.value = { left: '0px', top: '0px', width: '0px', height: '0px' }; return }
  const ids: number[] = []
  const v = new THREE.Vector3()
  rackObjs.forEach((rec, id) => {
    const pos = v.copy(rec.group.position).project(camera)
    const px = (pos.x + 1) / 2 * rect.width
    const py = (-pos.y + 1) / 2 * rect.height
    if (px >= x0 && px <= x1 && py >= y0 && py <= y1) {
      ids.push(id)
      if (!e.shiftKey) selectedSet.add(id)
      else if (selectedSet.has(id)) selectedSet.delete(id)
    }
  })
  boxStyle.value = { left: '0px', top: '0px', width: '0px', height: '0px' }
  if (ids.length) {
    updateHighlight()
    emit('box-select', ids)
    const first = rackObjs.get(ids[0])
    if (first) {
      controls.target.set(first.group.position.x, 1.5, first.group.position.z)
      controls.update()
    }
  }
}

function onKey(e: KeyboardEvent) {
  if (!ready.value) return
  if (e.key === 'r' || e.key === 'R') resetView()
  else if (e.key === 't' || e.key === 'T') topView()
  else if (e.key === 'b' || e.key === 'B') toggleBoxSelect()
  else if (e.key === 'c' || e.key === 'C') toggleClean()
  else if (e.key === ' ') { e.preventDefault(); togglePlay() }
  else if (e.key === 'Escape') {
    boxSelectMode.value = false
    selectedSet.clear()
    updateHighlight()
    emit('select-rack', null as any)
  }
}

function resetView() {
  if (!camera || !controls) return
  const racksList = props.data?.racks || []
  const maxX = racksList.length ? (Math.max(...racksList.map((r: any) => r.pos_x_m ?? ((r.col_pos || 1) - 1) * COL_SPACING), 1)) : 1
  const size = Math.max(maxX, 6)
  const cx = maxX / 2
  camera.position.set(cx + size * 0.3, Math.max(size * 0.9, 8), size * 1.5)
  controls.target.set(cx, 1.5, 0)
  controls.update()
  needsRender = true
}
function topView() {
  if (!camera || !controls) return
  const cx = controls.target.x, cz = controls.target.z
  camera.position.set(cx, 60, cz)
  controls.update()
  needsRender = true
}

function nextAlert() {
  const alerts = (props.data?.racks || []).filter((r: any) => (r.alerts || 0) > 0)
  if (!alerts.length) return
  const rec = rackObjs.get(alerts[0].id)
  if (rec) {
    controls.target.set(rec.group.position.x, 1.5, rec.group.position.z)
    camera.position.set(rec.group.position.x + 8, 8, rec.group.position.z + 8)
    selectedSet.clear(); selectedSet.add(alerts[0].id)
    updateHighlight(); emit('select-rack', alerts[0]); controls.update(); rebuildDeviceViews()
  }
}

function setLayer(l: string) {
  layer.value = l
  rackObjs.forEach((_r, id) => {
    const rack = (props.data?.racks || []).find((r: any) => r.id === id)
    if (rack) applyColor(rack)
  })
  needsRender = true
}
function toggleLabels() {
  showLabels.value = !showLabels.value
  rackObjs.forEach((rec) => { if (rec.label) rec.label.visible = showLabels.value })
  needsRender = true
}
function toggleBoxSelect() {
  boxSelectMode.value = !boxSelectMode.value
  if (boxSelectMode.value) controls.enabled = false
  else { controls.enabled = true; boxSelecting.value = false; boxStyle.value = { left: '0px', top: '0px', width: '0px', height: '0px' } }
}

// ---- 历史回放 ----
function startPlay() {
  if (historyLen.value <= 1) return
  playing.value = true
  playTimer = window.setInterval(() => {
    playIndex.value = (playIndex.value + 1) % historyLen.value
    applyHistoryFrame(playIndex.value)
  }, 400)
  applyHistoryFrame(playIndex.value)
}
function stopPlay() {
  playing.value = false
  if (playTimer) { clearInterval(playTimer); playTimer = null }
}
function togglePlay() {
  if (playing.value) stopPlay(); else startPlay()
}
function onSeek(e: Event) {
  const idx = Number((e.target as HTMLInputElement).value)
  playIndex.value = idx
  applyHistoryFrame(idx)
}
function applyHistoryFrame(idx: number) {
  const frame = history.value[idx]
  if (!frame) return
  playTimeLabel.value = frame.time || ''
  const heatById: Record<number, number> = frame.temps || {}
  rackObjs.forEach((rec, id) => {
    if (heatById[id] != null) {
      rec.rack.temperature = heatById[id]
    }
    applyColor(rec.rack)
  })
  if (showRoomHeat.value) buildRoomHeat()
  needsRender = true
}
function applyHistoryProp() {
  history.value = props.history || []
  historyLen.value = history.value.length
  if (historyLen.value <= 1) stopPlay()
}

function dispose() {
  stopPlay()
  cancelAnimationFrame(rafId)
  if (resizeObs) resizeObs.disconnect()
  clearRoomHeat()
  if (renderer) renderer.dispose()
  if (mountRef.value) mountRef.value.innerHTML = ''
}

onMounted(() => { init(); buildScene() })
onBeforeUnmount(() => dispose())
watch(() => props.data, (val) => { if (val) applyDiff(val.racks || []) })
watch(() => props.history, applyHistoryProp)
watch(boxSelectMode, (m) => { if (!m) { controls.enabled = true; boxSelecting.value = false } })

defineExpose({
  resetView, topView, nextAlert, setLayer, toggleLabels, toggleBoxSelect, toggleRoomHeat, toggleClean, exportImage,
  roomHeatOn: () => showRoomHeat.value,
  setBoxSelect: (m: boolean) => { boxSelectMode.value = m },
  clearSelection: () => { selectedSet.clear(); updateHighlight() },
  selectIds: (ids: number[]) => {
    selectedSet.clear(); ids.forEach(id => selectedSet.add(id)); updateHighlight(); rebuildDeviceViews()
  },
})
</script>

<style scoped>
.rack3d-scene { position: relative; width: 100%; height: 100%; min-height: 60vh; overflow: hidden; border-radius: 12px; }
.rack3d-canvas { width: 100%; height: 100%; min-height: 60vh; touch-action: none; }
.rack3d-box { position: absolute; border: 1px dashed #e67e22; background: rgba(230,126,34,0.08); z-index: 6; pointer-events: none; }
.rack3d-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.7); color: #606266; z-index: 5; }
.rack3d-hint { position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%); background: rgba(0,0,0,0.6); color: #fff; padding: 4px 10px; border-radius: 14px; font-size: 12px; pointer-events: none; z-index: 4; }
.rb-temp { color: #e67e22; font-weight: 600; }
.rb-selected { color: #ff9800; font-weight: 600; }
.rb-alert { color: #e53935; font-weight: 600; }
.rack3d-status { position: absolute; top: 12px; left: 12px; background: #fff; border: 1px solid var(--app-border,#e5e7eb); padding: 6px 12px; border-radius: 8px; font-size: 12px; color: #374151; z-index: 4; }
.rack3d-layerbar { position: absolute; top: 12px; right: 12px; background: #fff; border: 1px solid var(--app-border,#e5e7eb); border-radius: 8px; padding: 4px; display: flex; gap: 4px; flex-wrap: wrap; max-width: 60%; justify-content: flex-end; z-index: 4; }
.rack3d-legend { position: absolute; top: 12px; right: 12px; transform: translateY(56px); background: rgba(255,255,255,0.92); border: 1px solid var(--app-border,#e5e7eb); border-radius: 8px; padding: 8px 10px; z-index: 4; min-width: 120px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.lg-title { font-size: 11px; font-weight: 700; color: #374151; margin-bottom: 6px; }
.lg-row { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
.lg-swatch { width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(0,0,0,0.12); flex-shrink: 0; }
.lg-text { font-size: 11px; color: #4b5563; white-space: nowrap; }
.rack3d-playbar { position: absolute; bottom: 44px; left: 50%; transform: translateX(-50%); background: #fff; border: 1px solid var(--app-border,#e5e7eb); padding: 4px 10px; border-radius: 8px; display: flex; align-items: center; gap: 8px; z-index: 4; }
.play-range { width: 160px; }
.play-idx { font-size: 11px; color: #374151; }
.lb-btn { border: 1px solid var(--app-border,#e5e7eb); background: #fff; color: #374151; font-size: 12px; padding: 4px 10px; border-radius: 6px; cursor: pointer; }
.lb-btn:hover { border-color: var(--app-primary); color: var(--app-primary); }
.lb-btn.active { background: var(--app-primary); border-color: var(--app-primary); color: #fff; }
:deep(.rack3d-label) { color: #374151; background: rgba(255,255,255,0.85); font-size: 11px; padding: 1px 5px; border-radius: 4px; border: 1px solid #d1d5db; white-space: nowrap; pointer-events: none; }
.rack3d-export { position: absolute; bottom: 12px; right: 12px; border: 1px solid var(--app-primary,#409eff); background: #fff; color: var(--app-primary,#409eff); font-size: 12px; padding: 6px 12px; border-radius: 8px; cursor: pointer; z-index: 7; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.rack3d-export:hover { background: var(--app-primary,#409eff); color: #fff; }
.rack3d-exit { position: absolute; top: 12px; right: 12px; border: 1px solid rgba(255,255,255,0.6); background: rgba(0,0,0,0.55); color: #fff; font-size: 12px; padding: 6px 12px; border-radius: 8px; cursor: pointer; z-index: 7; }
.rack3d-exit:hover { background: rgba(0,0,0,0.7); }
.rack3d-scene.clean .rack3d-status,
.rack3d-scene.clean .rack3d-layerbar,
.rack3d-scene.clean .rack3d-legend,
.rack3d-scene.clean .rack3d-playbar,
.rack3d-scene.clean .rack3d-hint { display: none; }
</style>