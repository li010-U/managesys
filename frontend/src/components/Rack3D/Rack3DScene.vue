<template>
  <div class="rack3d-scene" :class="{ clean: cleanMode }" ref="wrapRef">
    <div ref="mountRef" class="rack3d-canvas"></div>
    <div class="rack3d-box" v-if="boxSelecting" ref="boxEl" :style="boxStyle"></div>
    <div v-if="!ready" class="rack3d-loading"><span>正在加载 3D 场景…</span></div>
    <div class="rack3d-hint" v-if="!cleanMode">左键旋转 · 右键平移 · 滚轮缩放 · 点击选中 · Shift 多选 · B 框选 · G 鸟瞰 · O 环绕 · R 复位</div>
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
      <button class="lb-btn" @click.stop="birdView">鸟瞰</button>
      <button class="lb-btn" :class="{active: autoOrbit}" @click.stop="toggleOrbit">环绕</button>
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
import { computeExportLayout, wrapText as wrapExportText, rackLabel } from './exportRender'

const props = defineProps<{ data: any; history?: any[]; config?: any }>()
const emit = defineEmits<{
  (e: 'select-rack', rack: any): void
  (e: 'selection-change', count: number): void
  (e: 'box-select', rackIds: number[]): void
  (e: 'select-device', device: any): void
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
// 自动环绕漫游开关（演示/汇报增强）
let autoOrbit = false

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
const sharedMats: Record<string, THREE.MeshStandardMaterial> = {}
const sharedDoorMats: Record<string, THREE.MeshStandardMaterial> = {}

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
function sharedMat(opacity: number, key: string, color: number): THREE.MeshStandardMaterial {
  if (!sharedMats[key]) sharedMats[key] = new THREE.MeshStandardMaterial({ color, transparent: true, opacity, metalness: 0.08, roughness: 0.6 })
  return sharedMats[key]
}
function sharedDoorMat(opacity: number, key: string, color: number): THREE.MeshStandardMaterial {
  if (!sharedDoorMats[key]) sharedDoorMats[key] = new THREE.MeshStandardMaterial({ color, transparent: true, opacity, side: THREE.DoubleSide, metalness: 0.2, roughness: 0.35 })
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
  // 浅色科技风背景 + 线性雾：明亮通透，同时保留空间纵深
  scene.background = new THREE.Color(0xe9f0fb)
  scene.fog = new THREE.Fog(0xe9f0fb, 30, 130)

  camera = new THREE.PerspectiveCamera(55, w / h, 0.1, 1000)

  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  // ACES 电影化色调映射：让质感和光照更自然（避免灰扑扑的纯色方块感）
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.15
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
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

  // 灯光：低强度环境光 + 蓝紫环境光 + 主光源（带投影）+ 暖色轮廓光 + 冷色补光
  const ambient = new THREE.AmbientLight(0xffffff, 0.7)
  scene.add(ambient)
  const hemi = new THREE.HemisphereLight(0xdcebff, 0xb9cbe0, 0.7)
  scene.add(hemi)
  const dir = new THREE.DirectionalLight(0xffffff, 1.5)
  dir.position.set(12, 24, 14)
  dir.castShadow = true
  dir.shadow.mapSize.set(2048, 2048)
  dir.shadow.camera.near = 0.5
  dir.shadow.camera.far = 120
  dir.shadow.camera.left = -40
  dir.shadow.camera.right = 40
  dir.shadow.camera.top = 40
  dir.shadow.camera.bottom = -40
  scene.add(dir)
  const rim = new THREE.DirectionalLight(0x4f8fe3, 0.7)
  rim.position.set(-14, 8, -12)
  scene.add(rim)
  const fill = new THREE.PointLight(0xffffff, 0.35, 100)
  fill.position.set(0, 6, 0)
  scene.add(fill)

  el.addEventListener('click', onClick)
  el.addEventListener('pointerdown', onPointerDown)
  el.addEventListener('pointermove', onPointerMove)
  el.addEventListener('pointerup', onPointerUp)
  el.addEventListener('pointerleave', onPointerUp)
  window.addEventListener('keydown', onKey)

  let lastFrame = 0
  const renderLoop = (ts: number = 0) => {
    rafId = requestAnimationFrame(renderLoop)
    if (autoOrbit) {
      const radius = camera.position.distanceTo(controls.target)
      const angle = controls.getAzimuthalAngle() + 0.002
      const sph = new THREE.Spherical(radius, controls.getPolarAngle(), angle)
      camera.position.setFromSpherical(sph).add(controls.target)
      needsRender = true
    }
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
  // 雾效随场景尺寸自适应：远景柔和淡出
  if (scene.fog && scene.fog instanceof THREE.Fog) {
    scene.fog.near = size * 1.4
    scene.fog.far = size * 4
  }
  const floorGeo = new THREE.PlaneGeometry(floorW, floorD)
  // 浅色地坪：明亮通透，带微弱粗糙质感，承接机柜投影
  const floorMat = new THREE.MeshStandardMaterial({ color: 0xdfe8f6, metalness: 0.05, roughness: 0.9, side: THREE.DoubleSide })
  const floor = new THREE.Mesh(floorGeo, floorMat)
  floor.rotation.x = -Math.PI / 2
  floor.position.set(cx, 0, cz)
  floor.receiveShadow = true
  scene.add(floor)

  // 科技感网格：亮色细线、半透明，替代灰白大地网格
  const grid = new THREE.GridHelper(Math.max(floorW, floorD), Math.max(8, Math.round(Math.max(floorW, floorD) / 1.0)), 0x9db8dd, 0xc6d5ea)
  grid.position.set(cx, 0.012, cz)
  const gridMat = grid.material as THREE.LineBasicMaterial
  gridMat.transparent = true
  gridMat.opacity = 0.6
  scene.add(grid)

  // 米制刻度：沿 X 轴（下）与 Z 轴（左）
  const rulerLen = Math.max(floorW, floorD, 2)
  const rulerMat = new THREE.LineBasicMaterial({ color: 0x7a93b8 })
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
  const S3 = 1.75
  const bigW = Math.round(1600 * S3), bigH = Math.round(900 * S3)
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
  const img = new Image()
  img.src = url
  await img.decode().catch(() => new Promise((res) => { img.onload = res; img.onerror = res }))

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
  g.font = Math.round(13*S3) + 'px "Microsoft YaHei", sans-serif'
  let maxCodeW = 0
  visible.forEach((it: any) => {
    const wdt = g.measureText(it.code).width
    if (wdt > maxCodeW) maxCodeW = wdt
  })
  const legend = { x: Math.round(12*S3), y: Math.round(12*S3), w: Math.round(70*S3) + Math.ceil(maxCodeW), pad: Math.round(10*S3), rowH: Math.round(24*S3) }
  g.globalAlpha = 0.94
  g.fillStyle = '#ffffff'
  g.strokeStyle = '#c9d3dd'
  g.lineWidth = 1
  roundRect(g, legend.x, legend.y, legend.w, Math.round(44*S3) + visible.length * legend.rowH + Math.round(8*S3), Math.round(6*S3))
  g.fill(); g.stroke()
  g.globalAlpha = 1
  g.fillStyle = '#1f2937'
  g.font = 'bold ' + Math.round(16*S3) + 'px "Microsoft YaHei", sans-serif'
  g.textAlign = 'left'
  g.textBaseline = 'middle'
  g.fillText('机柜代号', legend.x + legend.pad, legend.y + Math.round(22*S3))
  g.font = Math.round(14*S3) + 'px "Microsoft YaHei", sans-serif'
  items.forEach((it, i) => {
    if (!it.show) return
    const ly = legend.y + Math.round(44*S3) + (i) * legend.rowH + Math.round(8*S3)
    g.fillStyle = badgeColor(i)
    roundRect(g, legend.x + legend.pad, ly - Math.round(10*S3), Math.round(22*S3), Math.round(20*S3), Math.round(3*S3))
    g.fill()
    g.fillStyle = '#ffffff'
    g.font = 'bold ' + Math.round(13*S3) + 'px sans-serif'
    g.textAlign = 'center'
    g.fillText(String(i + 1), legend.x + legend.pad + Math.round(11*S3), ly)
    g.fillStyle = '#374151'
    g.font = Math.round(14*S3) + 'px "Microsoft YaHei", sans-serif'
    g.textAlign = 'left'
    g.fillText(it.code, legend.x + legend.pad + Math.round(30*S3), ly)
  })
  items.forEach((it, i) => {
    if (!it.show) return
    const bx = Math.max(Math.round(30*S3), Math.min(it.sx - Math.round(10*S3), bigW - Math.round(44*S3)))
    const by = Math.max(Math.round(30*S3), Math.min(it.sy - Math.round(34*S3), bigH - Math.round(30*S3)))
    g.strokeStyle = 'rgba(31,41,55,0.5)'
    g.lineWidth = Math.max(1, Math.round(1*S3))
    g.beginPath(); g.moveTo(bx + Math.round(10*S3), by + Math.round(20*S3)); g.lineTo(it.sx, Math.min(it.sy, by + Math.round(34*S3))); g.stroke()
    g.fillStyle = badgeColor(i)
    roundRect(g, bx, by, Math.round(22*S3), Math.round(22*S3), Math.round(4*S3))
    g.fill()
    g.strokeStyle = '#ffffff'
    g.lineWidth = Math.round(1.5*S3)
    g.stroke()
    g.fillStyle = '#ffffff'
    g.font = 'bold ' + Math.round(14*S3) + 'px sans-serif'
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText(String(i + 1), bx + Math.round(11*S3), by + Math.round(12*S3))
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
    c.width = 1600; c.height = 400
    const g = c.getContext('2d')!
    g.fillStyle = '#fafafa'; g.fillRect(0, 0, 1600, 400)
    g.fillStyle = '#666'; g.font = 'bold 40px sans-serif'
    g.textAlign = 'center'
    g.fillText('该机房暂无机柜数据', 800, 200)
    return c
  }

  // 高清倍率：整体放大到 2x，保证放大后仍清晰
  const S = 2
  const cellH = 16 * S, cellW = 46 * S, uLabelW = 18 * S
  const nameW = 260 * S, nameGap = 14 * S
  const cardHeadH = 50 * S, cardFootH = 74 * S, padX = 14 * S
  const lineH = Math.round(15 * S)
  const bodyFont = '12px sans-serif'
  const headFont = 'bold 15px sans-serif'
  // 卡片宽 = U 网格 + 设备名明细列
  const gridW = uLabelW + cellW
  const cardW = padX + gridW + nameGap + nameW + padX
  const maxW = 1900 * S
  const perRow = Math.max(1, Math.floor(maxW / cardW))
  const rows = Math.ceil(racks.length / perRow)
  const maxU = Math.max(...racks.map((r: any) => r.total_units || 42))
  const gridH = maxU * cellH
  const cardH = cardHeadH + gridH + cardFootH

  const W = Math.min(maxW, perRow * cardW)
  const H = rows * cardH + 40 * S
  const c = document.createElement('canvas')
  c.width = W; c.height = H
  const g = c.getContext('2d')!

  const statusColor = (s: string) => {
    if (s === 'running' || s === 'online') return '#2f9e44'
    if (s === 'offline' || s === 'error' || s === 'fault') return '#e03131'
    return '#5c7cfa' // mounted / in_stock / other
  }
  const categoryColor = (cat: string) => {
    const map: Record<string, string> = { server: '#2196F3', network: '#4CAF50', storage: '#9C27B0', security: '#FF9800', power: '#F44336' }
    return map[cat] || '#607D8B'
  }
  const catName = (cat: string) => {
    const map: Record<string, string> = { server: '服务器', network: '网络', storage: '存储', security: '安全', power: '电源' }
    return map[cat] || cat || '设备'
  }
  // 在给定宽度内按字数断行（中文按字符，英文按词），返回行数组

  g.fillStyle = '#fbfdff'; g.fillRect(0, 0, W, H)

  racks.forEach((rack: any, ri: number) => {
    const row = Math.floor(ri / perRow)
    const col = ri % perRow
    const ox = col * cardW
    const oy = row * cardH + 30

    // 卡片背景
    g.fillStyle = '#ffffff'
    g.strokeStyle = '#d7dee6'
    g.lineWidth = 1.5
    roundRect(g, ox, oy, cardW - 4, cardH, 8)
    g.fill(); g.stroke()

    // 头部：完整机柜代号
    g.fillStyle = '#1f2937'
    g.font = headFont
    g.textAlign = 'left'
    g.textBaseline = 'middle'
    const code = rack.code || ('Rack' + rack.id)
    g.fillText(code, ox + padX, oy + 20 * S)
    if (rack.name && rack.name !== code) {
      g.font = 'bold ' + (12 * S) + 'px sans-serif'
      g.fillText(rack.name, ox + padX + g.measureText(code).width + 6 * S, oy + 20 * S)
      g.font = headFont
    }
    g.font = bodyFont
    g.fillStyle = '#6b7280'
    g.fillText((rack.utilization ?? 0) + '% 利用' + ' · ' + (rack.device_count ?? 0) + ' 台' + ' · ' + (rack.power_load ?? 0) + ' kW', ox + padX, oy + 38 * S)

    const totalU = rack.total_units || 42
    const devices = rack.devices || []
    const occupied: Record<number, any> = {}
    devices.forEach((d: any) => {
      const s = Math.min(Math.max(d.start_u || 1, 1), totalU)
      const e = Math.min(Math.max(d.end_u || d.start_u || 1, 1), totalU)
      for (let u = s; u <= e; u++) occupied[u] = d
    })

    const diagX = ox + padX + uLabelW
    const footY = oy + cardHeadH + gridH
    const gridX = ox + padX + uLabelW

    // U 编号 + 单元格
    for (let u = totalU; u >= 1; u--) {
      const rowY = oy + cardHeadH + (totalU - u) * cellH
      g.fillStyle = '#9aa4b0'
      g.font = bodyFont
      g.textAlign = 'right'
      g.textBaseline = 'middle'
      g.fillText(String(u), ox + padX + uLabelW - 4, rowY + cellH / 2)
      const d = occupied[u]
      g.fillStyle = d ? categoryColor(d.device_type_category) : '#eef1f4'
      g.strokeStyle = d ? '#c9d3dd' : '#e2e7ec'
      g.beginPath(); g.rect(gridX, rowY, cellW, cellH - 1); g.fill(); g.stroke()
    }

    // 右侧设备名明细列：每台设备完整名称 + U 段 + 类型/功率/状态，绝不截断
    // 布局策略：信息块顶部严格对齐该设备所占 U 位的上缘（与左侧网格视觉对齐）；
    // 当上方设备的文字高度超过其 U 带时，为避免覆盖，下方设备顺延到上方文字块的底部之下。
    // 这样既保留“设备与其 U 位对齐”的观感，又保证文字完整、绝不重叠截断。
    const colX = ox + padX + gridW + nameGap
    const colTopY = oy + cardHeadH
    const colBottomY = colTopY + gridH
    const sorted = devices.slice().sort((a: any, b: any) => (b.start_u || 0) - (a.start_u || 0))
    let prevBottom = colTopY
    sorted.forEach((d: any, di: number) => {
      const s = Math.min(Math.max(d.start_u || 1, 1), totalU)
      const e = Math.min(Math.max(d.end_u || d.start_u || 1, 1), totalU)
      const span = (e - s) + 1
      const topU = s
      const bandTop = colTopY + (totalU - topU) * cellH
      // 名称（完整，自动换行）
      g.font = 'bold ' + (13 * S) + 'px sans-serif'
      const nameLines = wrapExportText(d.name || d.device_type_name || '', nameW - 10, g, g.font)
      const typeLine = (d.device_type_name ? d.device_type_name + ' · ' : '') + catName(d.device_type_category)
      const extraLine = 'U' + s + '-' + e + ' · ' + (d.power_rating ?? '') + 'kW' + (d.status ? ' · ' + d.status : '')
      // 计算这组文本需要的高度（以文本为主，保证信息完整显示）
      g.font = bodyFont
      const typeW = g.measureText(typeLine).width
      const extraW = g.measureText(extraLine).width
      const subLines = Math.max(typeW, extraW) > (nameW - 10) ? 2 : 1
      const needH = nameLines.length * lineH + (2 + subLines) * lineH
      const bandH = span * cellH
      const useH = Math.max(bandH, needH, lineH)
      // 信息块顶部：优先对齐自己 U 带顶；若被上方文字覆盖则顺延到其底部之下
      const blockTop = Math.max(bandTop, prevBottom)
      // 分隔线背景（轻微淡色块标识占用）
      g.fillStyle = '#ffffff'
      g.fillRect(colX, blockTop, nameW, Math.min(useH, colBottomY - blockTop))
      if (di < sorted.length - 1) {
        g.strokeStyle = '#e2e7ec'; g.lineWidth = 1
        g.beginPath(); g.moveTo(colX, blockTop + Math.min(useH - 1, colBottomY - blockTop - 2)); g.lineTo(colX + nameW, blockTop + Math.min(useH - 1, colBottomY - blockTop - 2)); g.stroke()
      }
      if (blockTop < colBottomY) {
        // 设备名（完整）
        g.fillStyle = '#1f2937'
        g.font = 'bold ' + (13 * S) + 'px sans-serif'
        g.textAlign = 'left'; g.textBaseline = 'middle'
        nameLines.forEach((ln: string, li: number) => {
          g.fillText(ln, colX + 4, blockTop + 10 * S + li * lineH)
        })
        const textBaseY = blockTop + 10 * S + nameLines.length * lineH + 2
        // 类型
        g.fillStyle = '#5c7cfa'
        g.font = bodyFont
        g.fillText(typeLine, colX + 4, textBaseY)
        // 状态 / U 段 / 功率
        g.fillStyle = '#6b7280'
        g.font = bodyFont
        g.fillText(extraLine, colX + 4, textBaseY + lineH)
      }
      prevBottom = blockTop + useH
    })

    // 列分隔线（网格与明细列之间）
    g.strokeStyle = '#dfe5ec'; g.lineWidth = 1
    g.beginPath(); g.moveTo(colX - nameGap / 2, oy + cardHeadH); g.lineTo(colX - nameGap / 2, oy + cardHeadH + gridH); g.stroke()

    // 底部：统计 + 额定功率
    g.fillStyle = '#374151'
    g.font = bodyFont
    g.textAlign = 'left'
    const usedU = Object.keys(occupied).length
    g.fillText('占用 ' + usedU + '/' + totalU + 'U', ox + padX, footY + 18 * S)
    g.fillText('设备 ' + (rack.device_count ?? devices.length) + ' 台', ox + padX, footY + 34 * S)
    g.fillText('功率 ' + (rack.power_load ?? 0) + ' kW', ox + padX, footY + 50 * S)
    if (rack.rated_power) {
      g.fillStyle = '#b45309'
      g.fillText('额定 ' + rack.rated_power + ' kW' + ' · 负载 ' + (rack.power_load_pct ?? 0) + '%', ox + padX, footY + 66 * S)
    }
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

// 合成最终导出图
function composeExportImage(three: { img: HTMLImageElement; bigW: number; bigH: number }, two: HTMLCanvasElement) {
  const rm = props.data?.room
  const layout = computeExportLayout(three.bigW, three.bigH, two.width, two.height)
  const { titleH, W, threeH, H, twoTop } = layout
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
  g.drawImage(three.img, 0, titleH + 30, W, threeH)

  // 小节标题 + 2D U 位明细
  g.textAlign = 'left'
  g.font = 'bold 14px "Microsoft YaHei", sans-serif'
  g.fillStyle = '#374151'
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
  body.castShadow = true
  body.receiveShadow = true
  body.userData.rack = rack
  group.add(body)

  const edgeGeo = new THREE.EdgesGeometry(bodyGeo)
  const edge = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: 0x1f3350 }))
  edge.position.y = height / 2
  edge.userData.rack = rack
  group.add(edge)

  const door = new THREE.Mesh(new THREE.PlaneGeometry(width, height), sharedDoorMat(0.18, 'd' + color, color))
  door.position.set(0, height / 2, depth / 2 + 0.005)
  door.castShadow = true
  door.userData.rack = rack
  group.add(door)

  const aisleMat = new THREE.MeshBasicMaterial({ color: 0x4aa8ef, transparent: true, opacity: 0.1, side: THREE.DoubleSide })
  const aisle = new THREE.Mesh(new THREE.PlaneGeometry(width, depth * 0.6), aisleMat)
  aisle.position.set(0, 0.03, depth / 2 + depth * 0.3)
  aisle.receiveShadow = true
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
    labelDiv.textContent = rackLabel(rack.code, rack.name)
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

// 设备资产状态分层配色（以真实数据取值为准）
// 在线 online/running 用类别色高亮；mounted 正常；maintenance 橙；offline 灰；in_stock 半透规划灰；scrapped 红
function deviceStatusStyle(d: any): { color: number; opacity: number; emissive: number } {
  const base = catColors[d.device_type_category] || 0x4f7fb3
  const st = (d.status || 'mounted') as string
  const online = st === 'online' || st === 'running'
  if (online) return { color: base, opacity: 0.95, emissive: 0x000000 }
  if (st === 'mounted') return { color: base, opacity: 0.82, emissive: 0x000000 }
  if (st === 'maintenance') return { color: 0xf59f00, opacity: 0.9, emissive: 0x3a2100 }
  if (st === 'scrapped') return { color: 0xdc2626, opacity: 0.45, emissive: 0x000000 }
  if (st === 'offline') return { color: 0x8091ab, opacity: 0.72, emissive: 0x000000 }
  // in_stock / 未知 -> 半透灰，表示规划/未上架
  return { color: 0x8091ab, opacity: 0.35, emissive: 0x000000 }
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
    const ds = deviceStatusStyle(d)
    // 设备盒：标准材质 + 状态辉光 + 投影
    const boxGeo = new THREE.BoxGeometry(width * 0.82, uh, depth * 0.5)
    const box = new THREE.Mesh(
      boxGeo,
      new THREE.MeshStandardMaterial({ color: ds.color, transparent: true, opacity: ds.opacity, emissive: ds.emissive, emissiveIntensity: 0.5, metalness: 0.25, roughness: 0.45 })
    )
    box.position.set(0, centerY, depth * 0.05)
    box.castShadow = true
    box.receiveShadow = true
    box.userData.rack = rack
    box.userData.device = d
    devGroup.add(box)
    // 设备面板描边：强化“设备细节”观感
    const devEdge = new THREE.LineSegments(new THREE.EdgesGeometry(boxGeo), new THREE.LineBasicMaterial({ color: 0x0a1424, transparent: true, opacity: 0.7 }))
    devEdge.position.copy(box.position)
    devEdge.userData.rack = rack
    devEdge.userData.device = d
    devGroup.add(devEdge)
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
    const bodyMat = rec.body.material as THREE.MeshStandardMaterial
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

function deviceAtPointer(e: MouseEvent): any {
  const el = mountRef.value!
  const rect = el.getBoundingClientRect()
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const deviceMeshes: THREE.Object3D[] = []
  for (const rec of rackObjs.values()) {
    if (rec.deviceGroup && rec.deviceGroup.visible) {
      rec.deviceGroup.children.forEach((c) => deviceMeshes.push(c))
    }
  }
  if (!deviceMeshes.length) return null
  const hits = raycaster.intersectObjects(deviceMeshes, false)
  if (!hits.length) return null
  const dev = hits[0].object.userData.device
  const rack = hits[0].object.userData.rack
  if (dev) { if (rack) dev.rack_id = rack.id; return dev }
  return null
}

function onClick(e: MouseEvent) {
  if (boxSelectMode.value) return
  const device = deviceAtPointer(e)
  if (device && !e.shiftKey) {
    const rec = device.rack_id ? rackObjs.get(device.rack_id) : null
    if (rec) { selectedSet.clear(); selectedSet.add(device.rack_id); updateHighlight() }
    emit('select-device', device)
    return
  }
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
  else if (e.key === 'g' || e.key === 'G') birdView()
  else if (e.key === 'o' || e.key === 'O') toggleOrbit()
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

// 鸟瞰视角：从高处斜向俯视整个场景，适合演示/汇报
function birdView() {
  if (!camera || !controls) return
  const racksList = props.data?.racks || []
  const maxX = racksList.length ? (Math.max(...racksList.map((r: any) => r.pos_x_m ?? ((r.col_pos || 1) - 1) * COL_SPACING), 1)) : 1
  const size = Math.max(maxX, 6)
  const cx = maxX / 2, cz = (props.data?.racks?.length ? 0 : 0)
  camera.position.set(cx, size * 1.7, cz - size * 1.7)
  controls.target.set(cx, 1.0, cz)
  controls.update()
  needsRender = true
}

// 自动环绕漫游：缓慢绕目标旋转，用于大屏演示
function toggleOrbit() {
  autoOrbit = !autoOrbit
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

function focusRack(rackId: number) {
  if (!camera || !controls) return
  const rec = rackObjs.get(rackId)
  const rack = (props.data?.racks || []).find((r: any) => r.id === rackId)
  if (!rec) return
  controls.target.set(rec.group.position.x, 1.5, rec.group.position.z)
  camera.position.set(rec.group.position.x + 8, 8, rec.group.position.z + 8)
  selectedSet.clear(); selectedSet.add(rackId)
  updateHighlight()
  if (rack) emit('select-rack', rack)
  controls.update(); rebuildDeviceViews(); needsRender = true
}

function focusDevice(deviceId: number) {
  if (!camera || !controls) return
  for (const rec of rackObjs.values()) {
    const dev = (rec.rack.devices || []).find((d: any) => d.id === deviceId)
    if (!dev) continue
    controls.target.set(rec.group.position.x, 1.5, rec.group.position.z)
    camera.position.set(rec.group.position.x + 5, 5, rec.group.position.z + 5)
    selectedSet.clear(); selectedSet.add(rec.rack.id)
    updateHighlight(); rebuildDeviceViews(); controls.update(); needsRender = true
    return true
  }
  return false
}

defineExpose({
  resetView, topView, nextAlert, setLayer, toggleLabels, toggleBoxSelect, toggleRoomHeat, toggleClean, exportImage,
  roomHeatOn: () => showRoomHeat.value,
  setBoxSelect: (m: boolean) => { boxSelectMode.value = m },
  clearSelection: () => { selectedSet.clear(); updateHighlight() },
  focusRack,
  focusDevice,
  selectIds: (ids: number[]) => {
    selectedSet.clear(); ids.forEach(id => selectedSet.add(id)); updateHighlight(); rebuildDeviceViews()
  },
})
</script>

<style scoped>
.rack3d-scene { position: relative; width: 100%; height: 100%; min-height: 60vh; overflow: hidden; border-radius: 12px; background: #e9f0fb; }
.rack3d-canvas { width: 100%; height: 100%; min-height: 60vh; touch-action: none; }
.rack3d-box { position: absolute; border: 1px dashed #38bdf8; background: rgba(56,189,248,0.1); z-index: 6; pointer-events: none; }
.rack3d-loading { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(233,240,251,0.85); color: #5a7ba8; z-index: 5; }
.rack3d-hint { position: absolute; left: 50%; bottom: 12px; transform: translateX(-50%); background: rgba(255,255,255,0.7); border: 1px solid rgba(90,130,200,0.35); color: #4a658a; padding: 4px 12px; border-radius: 14px; font-size: 12px; pointer-events: none; z-index: 4; backdrop-filter: blur(6px); box-shadow: 0 2px 8px rgba(30,60,110,0.12); }
.rb-temp { color: #ffb74d; font-weight: 600; }
.rb-selected { color: #ffd54f; font-weight: 600; }
.rb-alert { color: #ff6e6e; font-weight: 600; }
.rack3d-status { position: absolute; top: 12px; left: 12px; background: rgba(255,255,255,0.72); border: 1px solid rgba(90,130,200,0.3); padding: 6px 12px; border-radius: 8px; font-size: 12px; color: #33475f; z-index: 4; backdrop-filter: blur(8px); box-shadow: 0 2px 12px rgba(30,60,110,0.12); }
.rack3d-layerbar { position: absolute; top: 12px; right: 12px; background: rgba(255,255,255,0.72); border: 1px solid rgba(90,130,200,0.3); border-radius: 8px; padding: 4px; display: flex; gap: 4px; flex-wrap: wrap; max-width: 60%; justify-content: flex-end; z-index: 4; backdrop-filter: blur(8px); box-shadow: 0 2px 12px rgba(30,60,110,0.12); }
.rack3d-legend { position: absolute; top: 12px; right: 12px; transform: translateY(56px); background: rgba(255,255,255,0.8); border: 1px solid rgba(90,130,200,0.3); border-radius: 8px; padding: 8px 10px; z-index: 4; min-width: 120px; backdrop-filter: blur(8px); box-shadow: 0 2px 12px rgba(30,60,110,0.12); }
.lg-title { font-size: 11px; font-weight: 700; color: #3b6fb0; margin-bottom: 6px; }
.lg-row { display: flex; align-items: center; gap: 6px; margin: 2px 0; }
.lg-swatch { width: 14px; height: 14px; border-radius: 3px; border: 1px solid rgba(255,255,255,0.15); flex-shrink: 0; }
.lg-text { font-size: 11px; color: #4a658a; white-space: nowrap; }
.rack3d-playbar { position: absolute; bottom: 44px; left: 50%; transform: translateX(-50%); background: rgba(255,255,255,0.72); border: 1px solid rgba(90,130,200,0.3); padding: 4px 10px; border-radius: 8px; display: flex; align-items: center; gap: 8px; z-index: 4; backdrop-filter: blur(8px); box-shadow: 0 2px 12px rgba(30,60,110,0.12); }
.play-range { width: 160px; }
.play-idx { font-size: 11px; color: #4a658a; }
.lb-btn { border: 1px solid rgba(110,155,225,0.5); background: rgba(240,246,255,0.6); color: #3d5a80; font-size: 12px; padding: 4px 10px; border-radius: 6px; cursor: pointer; transition: all .15s ease; }
.lb-btn:hover { border-color: #2b6fd0; color: #2456a0; }
.lb-btn.active { background: linear-gradient(135deg,#2b6fd0,#38bdf8); border-color: #3ea8f5; color: #fff; }
:deep(.rack3d-label) { color: #33475f; background: rgba(255,255,255,0.85); font-size: 11px; padding: 1px 6px; border-radius: 4px; border: 1px solid rgba(90,130,200,0.4); white-space: pre-line; max-width: 220px; pointer-events: none; backdrop-filter: blur(4px); box-shadow: 0 1px 4px rgba(30,60,110,0.1); }
.rack3d-export { position: absolute; bottom: 12px; right: 12px; border: 1px solid #2b6fd0; background: rgba(43,111,208,0.1); color: #2456a0; font-size: 12px; padding: 6px 12px; border-radius: 8px; cursor: pointer; z-index: 7; backdrop-filter: blur(6px); box-shadow: 0 2px 10px rgba(30,60,110,0.18); }
.rack3d-export:hover { background: linear-gradient(135deg,#2b6fd0,#38bdf8); color: #fff; }
.rack3d-exit { position: absolute; top: 12px; right: 12px; border: 1px solid rgba(90,130,200,0.4); background: rgba(255,255,255,0.7); color: #33475f; font-size: 12px; padding: 6px 12px; border-radius: 8px; cursor: pointer; z-index: 7; backdrop-filter: blur(6px); }
.rack3d-exit:hover { background: rgba(255,255,255,0.95); }
.rack3d-scene.clean .rack3d-status,
.rack3d-scene.clean .rack3d-layerbar,
.rack3d-scene.clean .rack3d-legend,
.rack3d-scene.clean .rack3d-playbar,
.rack3d-scene.clean .rack3d-hint { display: none; }
</style>