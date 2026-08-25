<template>
  <div
    class="pet-assistant"
    :class="{ collapsed: collapsed, 'drag-active': dragging, docked: docked }"
    :style="{ left: pos.x + 'px', top: pos.y + 'px' }"
    @mousedown="startDrag"
  >
    <!-- 角色主体 -->
    <div
      class="pet-body"
      :class="'mood-' + (advisor?.status || 'healthy')"
      @click="onBodyClick"
      @mousemove="onBodyMove"
      @mouseleave="onBodyLeave"
      :title="advisor?.mood || ''"
      :style="bodyStyle"
    >
            <KabutackChar
        class="pet-char"
        :class="{ sleeping: !panelOpen && !hasReminder, squash: squash, jumping: hasReminder && !panelOpen }"
        :mood="advisor?.status"
        :eye-x="eyeX"
        :eye-y="eyeY"
        :sleeping="!panelOpen && !hasReminder"
        :squash="squash"
        :jumping="hasReminder && !panelOpen"
        :danger-count="dangerCount"
        :quiet="panelOpen"
      />
      <transition name="pop">
        <div v-if="newReminders > 0" class="pet-badge">{{ newReminders }}</div>
      </transition>
    </div>

    <transition name="bubble">
      <div
        v-if="currentBubble"
        class="reminder-bubble"
        :class="'level-' + currentBubble.level"
      >
        <div class="bubble-head">
          <span class="bubble-title">
            {{ currentBubble.title }}
            <span class="bubble-badge" v-if="(currentBubble as any).generated">已生成工单</span>
          </span>
          <el-icon class="bubble-close" @click.stop="dismissBubble"><Close /></el-icon>
        </div>
        <div class="bubble-content">{{ currentBubble.content }}</div>
        <div class="bubble-actions" v-if="currentBubble.actions && currentBubble.actions.length">
          <span
            v-for="a in currentBubble.actions"
            :key="a.type"
            class="bubble-action"
            @click.stop="runAction(currentBubble, a)"
          >{{ a.label || "操作" }}</span>
        </div>
        <div class="bubble-view" v-if="canAccess(currentBubble)" @click.stop="goTo(currentBubble)">
          <span>查看</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
    </transition>

    <transition name="panel">
      <div v-if="panelOpen" class="pet-panel" @click.stop @mousedown.stop>
        <div class="panel-header">
          <span class="panel-title">AI 数据中心助手</span>
          <div class="panel-actions">
            <el-switch v-model="liveEnabled" size="small" active-text="实时" inline-prompt />
            <el-icon class="panel-close" @click="togglePanel"><Close /></el-icon>
          </div>
        </div>

        <div class="panel-greeting" v-if="advisor">
          <span class="mood-dot" :class="'dot-' + advisor.status"></span>
          <span class="greeting-text">{{ greeting }}</span>
        </div>

        <div class="stat-grid" v-if="snapshot">
          <div class="stat-card">
            <div class="stat-value">{{ snapshot.device_count }}</div>
            <div class="stat-label">设备总数</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ snapshot.room_count }}</div>
            <div class="stat-label">机房数</div>
          </div>
          <div class="stat-card" :class="{ warn: snapshot.alert_stats.new > 0 }">
            <div class="stat-value">{{ snapshot.alert_stats.new }}</div>
            <div class="stat-label">待处理告警</div>
          </div>
          <div class="stat-card" :class="{ warn: snapshot.sensor.abnormal > 0 }">
            <div class="stat-value">{{ snapshot.sensor.abnormal }}</div>
            <div class="stat-label">环境异常</div>
          </div>
          <div class="stat-card">
            <div class="stat-value">{{ snapshot.rack.avg_usage.toFixed(1) }}%</div>
            <div class="stat-label">机柜利用率</div>
          </div>
          <div class="stat-card" :class="{ warn: snapshot.sensor.offline > 0 }">
            <div class="stat-value">{{ snapshot.sensor.offline }}</div>
            <div class="stat-label">传感器离线</div>
          </div>
        </div>

        <div class="loading-bar" v-else>
          <span class="loader"></span>
        </div>

        <div class="reminder-list" v-if="reminders.length">
          <div class="section-head" @click="reminderOpen = !reminderOpen">
            <span class="list-title">主动提醒</span>
            <span class="section-toggle"><el-icon><ArrowDown v-if="reminderOpen" /><ArrowRight v-else /></el-icon></span>
          </div>
          <div v-show="reminderOpen">
          <div
            v-for="(r, idx) in displayedReminders"
            :key="r.title + idx"
            class="reminder-item"
            :class="'level-' + r.level"
            @click="goTo(r)"
          >
            <span class="item-icon" :class="'icon-' + r.type"></span>
            <div class="item-main">
              <div class="item-title">
                <span>{{ r.title }}</span>
                <span class="item-badge" v-if="r.generated">已生成工单</span>
              </div>
              <div class="item-content">{{ r.content }}</div>
              <div class="item-actions" v-if="r.actions && r.actions.length">
                <span
                  v-for="a in r.actions"
                  :key="a.type"
                  class="item-action"
                  :class="{ 'action-created': r.generated }"
                  @click.stop="runAction(r, a)"
                >{{ a.label || "操作" }}</span>
              </div>
            </div>
            <span class="item-view" v-if="canAccess(r)" @click.stop="goTo(r)">
              <span>查看</span>
              <el-icon class="item-view-arrow"><ArrowRight /></el-icon>
            </span>
          </div>
          </div>
        </div>

        <div class="generated-section" v-if="createdOrders.length">
          <div class="gen-head" @click="generatedOpen = !generatedOpen">
            <span class="gen-title">
              <el-icon class="gen-chevron"><ArrowDown v-if="generatedOpen" /><ArrowRight v-else /></el-icon>
              <span class="list-title">已生成工单历史</span>
            </span>
            <el-button link type="danger" size="small" @click.stop="clearCreatedOrders">清除历史</el-button>
          </div>
          <div v-show="generatedOpen">
          <el-input
            v-model="genSearch"
            size="small"
            placeholder="按单号/标题搜索"
            clearable
            class="gen-search"
          />
          <div v-for="g in generatedGroups" :key="g.status" class="gen-group">
            <div class="gen-status">{{ g.status }}（{{ g.items.length }}）</div>
            <div
              v-for="(r, idx) in g.items"
              :key="'gen' + r.orderNo + idx"
              class="reminder-item gen-item"
              @click.stop="goTo(r)"
            >
              <span class="gen-order">#{{ r.orderNo }}</span>
              <span class="item-action action-created" @click.stop="runAction(r, r.actions![0])">查看工单</span>
              <span class="gen-remove" title="删除这条记录" @click.stop="removeCreatedOrder(r.orderNo)">
                <el-icon><Close /></el-icon>
              </span>
            </div>
          </div>
            <div v-if="!generatedGroups.length" class="gen-empty">无匹配的记录</div>
          </div>
        </div>

        <div class="recent-section" v-if="recentOrders.length">
          <div class="gen-head" @click="recentOpen = !recentOpen">
            <span class="gen-title">
              <el-icon class="gen-chevron"><ArrowDown v-if="recentOpen" /><ArrowRight v-else /></el-icon>
              <span class="list-title">最近浏览工单</span>
            </span>
            <el-button link type="danger" size="small" @click.stop="clearRecent">清空</el-button>
          </div>
          <div v-show="recentOpen">
            <div
              v-for="(wo, idx) in recentOrders"
              :key="'recent' + wo.id + idx"
              class="reminder-item recent-item"
              @click="goDetail(wo)"
            >
              <el-icon class="recent-icon"><Clock /></el-icon>
              <div class="item-main">
                <div class="item-title"><span>#{{ wo.order_no }}</span></div>
                <div class="item-content">{{ wo.title }}</div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel-footer" @click="openChat">
          <el-icon><ChatDotRound /></el-icon>
          <span>和我聊聊数据中心</span>
          <el-icon class="foot-arrow"><ArrowRight /></el-icon>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from "vue"
import { useRouter } from "vue-router"
import { Close, ChatDotRound, ArrowRight, ArrowDown, Clock } from "@element-plus/icons-vue"
import KabutackChar from "./KabutackChar.vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { getAssistantSnapshotApi, type AssistantPayload, type Reminder } from "../../api/assistant"
import { executeToolApi } from "../../api/chat"
import { useAuthStore } from "../../stores/auth"

const emit = defineEmits<{ (e: "open-chat"): void }>()

const router = useRouter()
const authStore = useAuthStore()

// 目标页面所要求的权限（无权限要求的页面不需要配置）
const TARGET_PERMISSIONS: Record<string, string> = {
  "/monitor/alerts": "monitor:view_alerts",
  "/workorder/list": "work:view",
}

function canAccess(r: Reminder): boolean {
  if (!r.target) return true
  const perm = TARGET_PERMISSIONS[r.target]
  if (!perm) return true
  return authStore.hasPermission(perm)
}

const panelOpen = ref(false)
const collapsed = ref(true)
const dragging = ref(false)
const liveEnabled = ref(true)
const data = ref<AssistantPayload | null>(null)
// 允许把桌宠拖到最左（贴近屏幕左边缘），仅保留极小边距避免完全拖出屏外
const PET_SAFE_MIN_X = 4
// 停靠左边缘阈值：桌宠左边缘小于该值即视为“停靠”，自动折叠隐藏以避免遮挡
const AUTO_COLLAPSE_THRESHOLD = 90
const pos = ref({ x: PET_SAFE_MIN_X, y: 24 })
const dragOffset = ref({ x: 0, y: 0 })
// 停靠状态：拖到左边缘附近时折叠隐藏（缩小为小圆点，避免遮挡左侧导航/内容）
const docked = computed(() => pos.value.x < AUTO_COLLAPSE_THRESHOLD)
const currentBubble = ref<Reminder | null>(null)
const seenTitles = ref<Set<string>>(new Set())
const showAll = ref(false)
// 面板分区折叠状态（本地记忆，刷新后保持用户偏好）
const COLLAPSE_KEY = "pet_panel_collapse"
function loadCollapse(): Record<string, boolean> {
  try {
    const saved = JSON.parse(localStorage.getItem(COLLAPSE_KEY) || "{}")
    return saved && typeof saved === "object" ? saved : {}
  } catch {
    return {}
  }
}
const collapsePrefs = loadCollapse()
const reminderOpen = ref(collapsePrefs.reminder ?? true)
const generatedOpen = ref(collapsePrefs.generated ?? true)
const recentOpen = ref(collapsePrefs.recent ?? false)

watch([reminderOpen, generatedOpen, recentOpen], ([r, g, rc]) => {
  try {
    localStorage.setItem(COLLAPSE_KEY, JSON.stringify({ reminder: r, generated: g, recent: rc }))
  } catch { /* ignore */ }
})

// 清空最近浏览工单
function clearRecent() {
  try { localStorage.removeItem("pet_recent_work_orders") } catch { /* ignore */ }
  recentOrders.value = []
  ElMessage.success("已清空最近浏览")
}

// 形象互动：瞳孔跟随 / 表情 / 点击反馈
const eyeX = ref(0)
const eyeY = ref(0)
const squash = ref(false)
const gaze = ref(false)
let gazeTimer: ReturnType<typeof setInterval> | null = null
let squashTimer: ReturnType<typeof setTimeout> | null = null

const bodyStyle = computed(() => ({
  "--eye-x": eyeX.value + "px",
  "--eye-y": eyeY.value + "px",
}))

let sse: EventSource | null = null
let streamAbort: AbortController | null = null
let visibilityHandler: (() => void) | null = null
let bubbleTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const snapshot = computed(() => data.value?.snapshot ?? null)
const advisor = computed(() => data.value?.advisor ?? null)
const reminders = computed<Reminder[]>(() => data.value?.reminders ?? [])
// AI 助手生成工单后，前端按会话记录，把“生成工单”改为“已生成工单 / 查看”
interface CreatedOrder {
  reminderTitle: string
  orderId: number
  orderNo: string
  priority?: string
  createdAt: number
}

// 工单状态 -> 中文标签（与工单列表一致）
const WORK_ORDER_STATUS: Record<string, string> = {
  pending: "待分配",
  assigned: "已指派",
  processing: "处理中",
  pending_verify: "待验收",
  completed: "已完成",
  closed: "已关闭",
}

const CREATED_ORDERS_KEY = "pet_assistant_created_orders"

// 跨会话恢复“已生成工单”记录
function restoreCreatedOrders(): CreatedOrder[] {
  try {
    const saved = localStorage.getItem(CREATED_ORDERS_KEY)
    if (!saved) return []
    const arr = JSON.parse(saved)
    if (!Array.isArray(arr)) return []
    return arr
      .filter((o: any) => o && typeof o.reminderTitle === "string" && o.orderNo)
      .map((o: any) => ({
        reminderTitle: o.reminderTitle,
        orderId: Number(o.orderId) || 0,
        orderNo: String(o.orderNo),
        priority: o.priority || "normal",
        createdAt: Number(o.createdAt) || Date.now(),
      }))
  } catch {
    return []
  }
}

const createdOrders = ref<CreatedOrder[]>(restoreCreatedOrders())

// 持久化“已生成工单”记录
watch(createdOrders, (val) => {
  try {
    localStorage.setItem(CREATED_ORDERS_KEY, JSON.stringify(val))
  } catch { /* ignore */ }
}, { deep: true })

// 在原始提醒上叠加“已生成工单”状态：替换动作为查看，并追加一条已生成工单记录
const viewReminders = computed<(Reminder & { generated?: boolean; orderId?: number; orderNo?: string; liveStatus?: string })[]>(() => {
  const list: (Reminder & { generated?: boolean; orderId?: number; orderNo?: string; liveStatus?: string })[] = []
  // 按快照里的开放工单，给已生成工单补上实时处理状态
  const openItems: any[] = (snapshot.value as any)?.work_orders?.items || []
  const liveOf = (o: CreatedOrder) => {
    const live = openItems.find((w) => w.id === o.orderId)
    return live ? (WORK_ORDER_STATUS[live.status] || live.status) : ""
  }
  for (const r of reminders.value) {
    const made = createdOrders.value.find((o) => o.reminderTitle === r.title)
    if (!r.actions?.some((a) => a.type === "create_work_order")) {
      list.push(r)
      continue
    }
    if (made) {
      list.push({
        ...r,
        generated: true,
        orderId: made.orderId,
        orderNo: made.orderNo,
        liveStatus: liveOf(made),
        actions: [{ type: "view_work_order", label: "查看工单", priority: made.priority }],
      })
    } else {
      list.push(r)
    }
  }
  for (const o of createdOrders.value) {
    if (!list.some((r) => (r as any).orderNo === o.orderNo)) {
      const liveStatus = liveOf(o)
      list.push({
        type: "work_order",
        level: "info",
        title: `已生成工单 #${o.orderNo}${liveStatus ? `（${liveStatus}）` : ""}`,
        content: o.reminderTitle + "，已由 AI 助手生成工单，可前往查看。",
        target: "/workorder/detail/" + o.orderId,
        generated: true,
        orderId: o.orderId,
        orderNo: o.orderNo,
        liveStatus,
        actions: [{ type: "view_work_order", label: "查看工单" }],
      })
    }
  }
  return list
})

const displayedReminders = computed(() => {
  const normal = viewReminders.value.filter((r) => !r.generated)
  return showAll.value ? normal : normal.slice(0, 5)
})
// 只统计“已生成工单”相关记录（含被改写的提醒与追加的历史）
const generatedReminders = computed(() => viewReminders.value.filter((r) => r.generated))

// 已生成工单历史的按单号/内容过滤关键字
const genSearch = ref("")

// 按实时处理状态分组，便于查看
const generatedGroups = computed<{ status: string; items: any[] }[]>(() => {
  const order = ["处理中", "待分配", "已指派", "待验收", "已完成", "已关闭"]
  const groups: { status: string; items: any[] }[] = []
  const byStatus: Record<string, any[]> = {}
  const kw = genSearch.value.trim().toLowerCase()
  for (const r of generatedReminders.value) {
    if (kw && !((r as any).orderNo || r.title).toString().toLowerCase().includes(kw)) continue
    const key = (r as any).liveStatus || "其他"
    ;(byStatus[key] ||= []).push(r)
  }
  const keys = Object.keys(byStatus).sort((a, b) => {
    const ia = order.indexOf(a), ib = order.indexOf(b)
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
  })
  for (const k of keys) groups.push({ status: k, items: byStatus[k] })
  return groups
})

// 清除已生成工单历史（含本地存储）
function clearCreatedOrders() {
  createdOrders.value = []
  ElMessage.success("已清除已生成工单历史")
}

// 单条删除某条已生成工单历史
function removeCreatedOrder(orderNo: string) {
  createdOrders.value = createdOrders.value.filter((o) => o.orderNo !== orderNo)
  ElMessage.success("已删除")
}

// 最近浏览工单（来自工单详情页记录）
const RECENT_KEY = "pet_recent_work_orders"
const recentOrders = ref<any[]>([])
function loadRecent() {
  try {
    const arr = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]")
    recentOrders.value = Array.isArray(arr) ? arr.slice(0, 5) : []
  } catch {
    recentOrders.value = []
  }
}


const dangerCount = computed(
  () => (snapshot.value?.alert_stats.new ?? 0) + (snapshot.value?.sensor.abnormal ?? 0)
)
const newReminders = computed(() => viewReminders.value.filter((r) => !seenTitles.value.has(r.title)).length)
const hasReminder = computed(() => viewReminders.value.length > 0)

const greeting = computed(() => {
  const a = advisor.value
  if (!a) return "正在连接设备数据中心，请稍候…"
  return "我很好（" + a.mood + "）。" + a.summary
})

function restorePosition() {
  try {
    const saved = localStorage.getItem("pet_assistant_pos")
    if (saved) {
      const p = JSON.parse(saved)
      if (typeof p.x === "number" && typeof p.y === "number") {
        pos.value = {
          x: Math.max(PET_SAFE_MIN_X, Math.min(p.x, window.innerWidth - 90)),
          y: Math.max(0, Math.min(p.y, window.innerHeight - 120)),
        }
      }
    } else {
      // 像素坐标越界时，回退到安全位置
      pos.value.x = PET_SAFE_MIN_X
    }
  } catch { /* ignore */ }
}

function persistPosition() {
  localStorage.setItem("pet_assistant_pos", JSON.stringify(pos.value))
}

function startDrag(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (target.closest(".pet-panel") || target.closest(".reminder-bubble")) return
  dragging.value = true
  dragOffset.value = { x: e.clientX - pos.value.x, y: e.clientY - pos.value.y }
  window.addEventListener("mousemove", onDrag)
  window.addEventListener("mouseup", endDrag)
}

function onDrag(e: MouseEvent) {
  if (!dragging.value) return
  pos.value = {
    x: Math.max(PET_SAFE_MIN_X, Math.min(window.innerWidth - 90, e.clientX - dragOffset.value.x)),
    y: Math.max(0, Math.min(window.innerHeight - 120, e.clientY - dragOffset.value.y)),
  }
}

function endDrag() {
  if (!dragging.value) return
  dragging.value = false
  persistPosition()
  // 停靠到左边缘时自动折叠隐藏，避免面板/气泡遮挡左侧导航
  if (docked.value) {
    panelOpen.value = false
    collapsed.value = true
    currentBubble.value = null
  }
  window.removeEventListener("mousemove", onDrag)
  window.removeEventListener("mouseup", endDrag)
}

function onBodyClick() {
  // 停靠状态点击：先向右侧移出靠左停靠区，让面板能正常展开，再继续原有行为
  if (docked.value) {
    pos.value.x = AUTO_COLLAPSE_THRESHOLD + 20
    persistPosition()
  }
  // 点击挤压反馈（squash & stretch）
  if (squash.value) return
  squash.value = true
  if (squashTimer) clearTimeout(squashTimer)
  squashTimer = setTimeout(() => { squash.value = false; squashTimer = null }, 260)
  togglePanel()
}

function onBodyMove(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const cx = rect.left + rect.width / 2
  const cy = rect.top + rect.height / 2
  // 瞳孔朝向鼠标（限制在 ±2.5px 内，保持自然不贴边）
  eyeX.value = clamp((e.clientX - cx) / 16, -2.5, 2.5)
  eyeY.value = clamp((e.clientY - cy) / 16, -2.5, 2.5)
}

function onBodyLeave() {
  eyeX.value = 0
  eyeY.value = 0
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v))
}

function randomGaze() {
  if (!gaze) return
  const x = Math.round((Math.random() * 2 - 1) * 2)
  const y = Math.round((Math.random() * 2 - 1) * 1.5)
  eyeX.value = x
  eyeY.value = y
  setTimeout(() => {
    eyeX.value = 0
    eyeY.value = 0
  }, 900)
}

function togglePanel() {
  panelOpen.value = !panelOpen.value
  collapsed.value = !panelOpen.value
  ensureData()
}

function openPanel() {
  panelOpen.value = true
  collapsed.value = false
}

function dismissBubble() {
  currentBubble.value = null
}

function openChat() {
  emit("open-chat")
}

function goDetail(wo: any) {
  if (!wo?.id) return
  panelOpen.value = false
  collapsed.value = true
  currentBubble.value = null
  router.push(`/workorder/detail/${wo.id}`)
}

function jumpTo(r: Reminder) {
  panelOpen.value = false
  collapsed.value = true
  currentBubble.value = null
  const loc = r.locate
  if (loc?.kind === "sensor" && loc.room_id) {
    router.push({ path: "/environment", query: { room_id: loc.room_id, sensor_id: loc.sensor_id } })
    return
  }
  if (loc?.kind === "rack") {
    if (loc.rack_id) {
      router.push({ path: "/room/racks", query: { room_id: loc.room_id, rack: loc.rack_id } })
    } else {
      router.push("/room/racks")
    }
    return
  }
  if (loc?.kind === "work_order") {
    if (loc.order_id) router.push(`/workorder/detail/${loc.order_id}`)
    else router.push("/workorder/list")
    return
  }
  if (loc?.kind === "alert") { router.push("/monitor/alerts"); return }
  if (r.target) { router.push(r.target); return }
  currentBubble.value = r
}

async function goTo(r: Reminder) {
  if (!canAccess(r)) {
    ElMessage.warning("你没有权限访问该页面")
    return
  }
  try {
    await ElMessageBox.confirm(r.content, r.title, {
      confirmButtonText: "跳转到相关位置",
      cancelButtonText: "仅查看全文",
      type: r.level === "danger" ? "error" : r.level === "warning" ? "warning" : "info",
      distinguishCancelAndClose: true,
    })
    jumpTo(r)
  } catch (reason) {
    // cancel / close : 全文已在弹窗展示，不跳转
    if (reason !== "cancel" && reason !== "close") return
  }
}

async function runAction(r: Reminder, action: { type: string; label?: string; priority?: string }) {
  // 已生成工单 -> 跳转查看工单列表
  if (action.type === "view_work_order") {
    panelOpen.value = false
    collapsed.value = true
    currentBubble.value = null
    const orderId = (r as { orderId?: number }).orderId
    // 有独立详情页：直接 URL 直达工单详情；兜底回工单列表
    if (orderId) {
      router.push(`/workorder/detail/${orderId}`)
    } else {
      router.push("/workorder/list")
    }
    return
  }
  if (action.type !== "create_work_order") return
  try {
    await ElMessageBox.confirm(
      `将根据“${r.title}”创建一条工单，是否继续？`,
      "创建工单",
      { confirmButtonText: "确认创建", cancelButtonText: "取消", type: "warning" }
    )
  } catch {
    return
  }
  try {
    const res = await executeToolApi("create_work_order", {
      title: r.title,
      description: r.content,
      priority: action.priority || "normal",
    })
    const result = (res?.data?.result as { order_id?: number; order_no?: string }) || {}
    // 记录这次生成的工单，提醒由“生成工单”变为“已生成工单 / 查看”
    createdOrders.value.push({
      reminderTitle: r.title,
      orderId: result.order_id ?? 0,
      orderNo: result.order_no ?? "",
      priority: action.priority || "normal",
      createdAt: Date.now(),
    })
    // 最多保留近期 20 条已生成工单，避免本地记录无限增长
    if (createdOrders.value.length > 20) {
      createdOrders.value = createdOrders.value.slice(-20)
    }
    if (result.order_no) {
      ElMessage.success(`工单已生成：${result.order_no}，可点击“查看工单”前往。`)
    } else {
      ElMessage.success("工单已生成")
    }
    // 重新拉取快照，刷新提醒状态
    applyData(null)
    return res
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "创建工单失败")
  }
}

function rotateBubble() {
  const unseen = viewReminders.value.filter((r) => !seenTitles.value.has(r.title))
  const pool = unseen.length ? unseen : viewReminders.value
  if (!pool.length) return
  const next = pool[Math.floor(Date.now() / 8000) % pool.length]
  currentBubble.value = next
  pool.forEach((r) => seenTitles.value.add(r.title))
}

function resetSeen() {
  seenTitles.value = new Set()
}

function ensureData() {
  if (!data.value) applyData(null)
}

function applyData(payload: AssistantPayload | null) {
  if (!payload) {
    getAssistantSnapshotApi()
      .then((res) => {
        data.value = res.data
        maybeBubble()
      })
      .catch(() => { /* 静默失败 */ })
    return
  }
  data.value = payload
  maybeBubble()
}

function maybeBubble() {
  if (!currentBubble.value && viewReminders.value.length && !panelOpen.value) {
    rotateBubble()
  }
}

function startStreaming() {
  // 无有效 token 时不建立 SSE 长连接，避免 token 失效后无限重连刷 401，
  // 既拖累页面渲染，也让数据请求被挤占。
  const token = localStorage.getItem("access_token")
  if (!token) return
  const base = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "")
  const url = base + "/assistant/stream"
  // 原生 EventSource 不支持自定义 header，改用 fetch + ReadableStream 兼容鉴权
  connectSSE(url, token)
}

function connectSSE(url: string, token: string | null) {
  const headers: Record<string, string> = { Accept: "text/event-stream" }
  if (token) headers.Authorization = "Bearer " + token

  streamAbort = new AbortController()
  const signal = streamAbort.signal

  fetch(url, { headers, signal })
    .then((resp) => {
      if (!resp.ok) throw new Error("stream failed " + resp.status)
      const reader = resp.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ""
      const pump = () => {
        reader.read().then(({ done, value }) => {
          if (done) { resetFailCount(); startFallbackPolling(); scheduleReconnect(); return }
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() || ""
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const chunk = line.slice(6)
              if (chunk === "[DONE]") { resetFailCount(); startFallbackPolling(); scheduleReconnect(); return }
              try {
                const payload = JSON.parse(chunk) as AssistantPayload
                data.value = payload
                resetFailCount()
                startFallbackPolling()
                maybeBubble()
              } catch { /* ignore */ }
            }
          }
          pump()
        }).catch((err) => {
          if (streamAbort?.signal.aborted) return
          scheduleReconnect()
        })
      }
      pump()
    })
    .catch(() => {
      if (streamAbort?.signal.aborted) return
      scheduleReconnect()
    })
}

let streamActive = false
let failCount = 0
let reconnectTimer: ReturnType<typeof setTimeout> | null = null
let fallbackPollTimer: ReturnType<typeof setInterval> | null = null

// 断线退避 + 随机抖动，避免所有桌宠同时重连造成雪崩
function scheduleReconnect() {
  if (!liveEnabled.value) return
  if (reconnectTimer) return
  const base = Math.min(30000, 4000 * Math.pow(2, failCount))
  const jitter = Math.round(base * (0.7 + Math.random() * 0.6))
  failCount += 1
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null
    startStreaming()
  }, jitter)
}

function resetFailCount() {
  failCount = 0
}

function startFallbackPolling() {
  if (fallbackPollTimer) return
  // 每 30s 静默刷新一次快照，保证数据不至于过旧
  fallbackPollTimer = setInterval(() => applyData(null), 30000)
}

function stopStreaming() {
  if (streamAbort) { streamAbort.abort(); streamAbort = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
  if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null }
  if (fallbackPollTimer) { clearInterval(fallbackPollTimer); fallbackPollTimer = null }
}

watch(liveEnabled, (val) => {
  if (val) { startStreaming() } else { stopStreaming() }
})

watch(panelOpen, (val) => {
  if (val) { resetSeen(); loadRecent() }
  if (val) currentBubble.value = null
})

onMounted(() => {
  restorePosition()
  applyData(null)
  startStreaming()
  // 空闲时随机张望，让桌宠更有生气
  gaze.value = true
  gazeTimer = setInterval(() => {
    if (!panelOpen.value && Math.random() < 0.6) randomGaze()
  }, 5000)
  bubbleTimer = setInterval(() => {
    if (!panelOpen.value) rotateBubble()
  }, 9000)
  visibilityHandler = () => {
    if (document.hidden) {
      stopStreaming()
    } else if (liveEnabled.value) {
      startStreaming()
    }
  }
  document.addEventListener("visibilitychange", visibilityHandler)
})

onBeforeUnmount(() => {
  if (visibilityHandler) document.removeEventListener("visibilitychange", visibilityHandler)
  stopStreaming()
  if (bubbleTimer) clearTimeout(bubbleTimer)
  if (gazeTimer) clearInterval(gazeTimer)
  if (squashTimer) clearTimeout(squashTimer)
})
</script>

<style scoped>
.pet-assistant { position: fixed; z-index: 3000; user-select: none; }
.pet-body { position: absolute; left: 0; top: 0; width: 150px; height: 162px; cursor: pointer; transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.pet-body:hover { transform: translateY(-4px) scale(1.06); }
/* 停靠左边缘：收缩为小圆点，让出左侧导航/内容区 */
.pet-assistant.docked .pet-body { transform: translateY(0) scale(0.28); transform-origin: center left; opacity: 0.95; }
.pet-assistant.docked .pet-body:hover { transform: translateY(0) scale(0.34); }
.pet-assistant.docked .pet-badge { font-size: 9px; min-width: 14px; height: 14px; line-height: 14px; top: 0; right: 0; }
.pet-assistant.docked .reminder-bubble,
.pet-assistant.docked .pet-panel { display: none; }
.pet-char {
  display: block; width: 134px; height: 146px; margin: 0;
  overflow: visible;
}

/* ===== 身体与配色 ===== */

/* ===== 天线 ===== */

/* ===== 眼睛与瞳孔 ===== */



/* ===== 眉毛（SVG 线条绕中心旋转） ===== */

/* ===== 嘴形（按状态显示/隐藏） ===== */



/* ===== 健康：放松上扬眉毛 + 微笑 ===== */

/* ===== 一般：内端下压眉毛 + 平嘴 ===== */


/* ===== 告警：竖眉瞪眼张嘴（眼/身转红） ===== */


/* 默认隐藏所有嘴形，健康态显微笑已在上方覆盖 */

.pet-badge { position: absolute; top: -2px; right: -2px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: #ef4444; color: #fff; font-size: 11px; line-height: 20px; text-align: center; box-shadow: 0 2px 8px rgba(239,68,68,0.5); }
.reminder-bubble { position: absolute; left: 112px; top: 0; min-width: 230px; max-width: 300px; background: #fff; border-radius: 14px; box-shadow: 0 12px 32px rgba(15,23,42,0.18); padding: 12px 14px; cursor: pointer; border-left: 4px solid #3b82f6; }
.reminder-bubble.level-warning { border-left-color: #f59e0b; }
.reminder-bubble.level-danger { border-left-color: #ef4444; }
.bubble-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.bubble-title { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; font-size: 13px; color: #1e293b; }
.bubble-close { color: #94a3b8; cursor: pointer; font-size: 14px; }
.bubble-content { font-size: 12px; color: #475569; line-height: 1.5; }
.bubble-view { display: inline-flex; align-items: center; gap: 4px; margin-top: 10px; padding: 4px 12px; border-radius: 999px; background: #eff6ff; color: #2563eb; font-size: 12px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
.bubble-view:hover { background: #dbeafe; }
.bubble-view .el-icon { font-size: 13px; }
.pet-panel { position: absolute; left: 112px; top: 60px; width: 320px; max-height: 62vh; overflow-y: auto; background: #fff; border-radius: 16px; box-shadow: 0 20px 50px rgba(15,23,42,0.22); padding: 14px; cursor: default; }
.panel-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.panel-title { font-weight: 700; font-size: 14px; color: #1e293b; }
.panel-actions { display: flex; align-items: center; gap: 10px; }
.panel-close { color: #94a3b8; cursor: pointer; font-size: 16px; }
.panel-greeting { display: flex; align-items: center; gap: 6px; background: #f1f5f9; border-radius: 10px; padding: 8px 10px; font-size: 12px; color: #334155; margin-bottom: 10px; }
.mood-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.dot-healthy { background: #22c55e; } .dot-attention { background: #f59e0b; } .dot-alert { background: #ef4444; }
.greeting-text { line-height: 1.5; }
.stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-bottom: 12px; }
.stat-card { background: #f8fafc; border-radius: 10px; padding: 10px 8px; text-align: center; border: 1px solid #e2e8f0; }
.stat-card.warn { border-color: #fca5a5; background: #fef2f2; }
.stat-value { font-size: 20px; font-weight: 700; color: #1e293b; }
.stat-card.warn .stat-value { color: #dc2626; }
.stat-label { font-size: 11px; color: #64748b; margin-top: 2px; }
.loader { width: 28px; height: 28px; border: 3px solid #e2e8f0; border-top-color: #3b82f6; border-radius: 50%; display: block; margin: 20px auto; animation: spin 0.8s linear infinite; }
.reminder-list { margin-top: 4px; }
.list-title { font-size: 12px; color: #94a3b8; margin-bottom: 6px; font-weight: 600; }
.reminder-item { display: flex; gap: 8px; padding: 8px; border-radius: 8px; margin-bottom: 6px; background: #f8fafc; cursor: pointer; transition: background 0.2s; }
.reminder-item:hover { background: #f1f5f9; }
.reminder-item.level-warning { border-left: 3px solid #f59e0b; }
.reminder-item.level-danger { border-left: 3px solid #ef4444; }
.item-icon { width: 8px; height: 8px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.icon-alert { background: #ef4444; } .icon-env { background: #3b82f6; } .icon-capacity { background: #f59e0b; } .icon-work { background: #8b5cf6; }
.item-main { flex: 1; min-width: 0; }
.item-title { display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600; color: #334155; }
.item-badge, .bubble-badge { flex-shrink: 0; padding: 1px 6px; border-radius: 6px; background: #6366f1; color: #fff; font-size: 10px; font-weight: 600; line-height: 1.5; }
.item-content { font-size: 11px; color: #64748b; margin-top: 2px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.item-view { display: inline-flex; align-items: center; gap: 2px; margin-left: 6px; padding: 3px 8px; border-radius: 6px; background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 600; cursor: pointer; flex-shrink: 0; }
.item-view:hover { background: #dbeafe; }
.item-view .el-icon { font-size: 12px; }
.item-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.item-action { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 6px; background: #ecfdf5; color: #059669; font-size: 11px; font-weight: 600; cursor: pointer; border: 1px solid #a7f3d0; }
.item-action:hover { background: #d1fae5; }
.item-action.action-created { background: #eef2ff; color: #4f46e5; border-color: #c7d2fe; }
.item-action.action-created:hover { background: #e0e7ff; }
.generated-section { margin-top: 10px; border-top: 1px dashed #e2e8f0; padding-top: 8px; }
.gen-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; cursor: pointer; user-select: none; }
.section-head { display: flex; align-items: center; justify-content: space-between; cursor: pointer; user-select: none; }
.section-toggle { color: #94a3b8; font-size: 13px; }
.gen-title { display: flex; align-items: center; gap: 4px; }
.gen-chevron { color: #94a3b8; font-size: 12px; transition: transform 0.2s; }
.gen-group { margin-bottom: 8px; }
.gen-status { font-size: 11px; color: #6366f1; font-weight: 600; margin: 6px 0 4px; }
.gen-search { margin-bottom: 8px; }
.gen-remove { flex-shrink: 0; color: #cbd5e1; cursor: pointer; font-size: 13px; }
.gen-remove:hover { color: #ef4444; }
.recent-section { margin-top: 10px; border-top: 1px dashed #e2e8f0; padding-top: 8px; }
.recent-item { cursor: pointer; }
.recent-icon { color: #94a3b8; margin-top: 4px; font-size: 14px; }
.gen-empty { color: #94a3b8; font-size: 12px; padding: 8px 0; text-align: center; }
.gen-item { cursor: pointer; padding: 6px 8px; }
.gen-order { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; color: #334155; }
.bubble-actions { display: flex; gap: 6px; margin-top: 8px; }
.bubble-action { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; background: #ecfdf5; color: #059669; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid #a7f3d0; }
.bubble-action:hover { background: #d1fae5; }
.icon-trend { background: #8b5cf6; }
.panel-footer { display: flex; align-items: center; gap: 6px; color: #3b82f6; font-size: 12px; font-weight: 600; padding: 10px; border-top: 1px solid #e2e8f0; margin-top: 8px; cursor: pointer; }
.foot-arrow { margin-left: auto; }



@keyframes blink { 0%,92%,100% { transform: scaleY(1); } 95% { transform: scaleY(0.05); } }
@keyframes blink-warning { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
@keyframes spin { to { transform: rotate(360deg); } }
.bubble-enter-active, .bubble-leave-active { transition: all 0.3s ease; }
.bubble-enter-from, .bubble-leave-to { opacity: 0; transform: translateY(8px); }
.panel-enter-active, .panel-leave-active { transition: all 0.25s ease; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateY(10px) scale(0.96); }
.pop-enter-active, .pop-leave-active { transition: all 0.2s ease; }
.pop-enter-from, .pop-leave-to { opacity: 0; transform: scale(0.5); }
</style>

