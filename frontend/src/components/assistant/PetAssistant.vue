<template>
  <div
    class="pet-assistant"
    :class="{ collapsed: collapsed, 'drag-active': dragging }"
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
      <svg
        class="pet-char"
        :class="{ sleeping: !panelOpen && !hasReminder, squash: squash, jumping: hasReminder && !panelOpen }"
        viewBox="0 0 72 76"
        xmlns="http://www.w3.org/2000/svg"
      >
        <!-- 天线（顶部） -->
        <line class="antenna" x1="36" y1="17" x2="36" y2="7" stroke="#64748b" stroke-width="2.4" stroke-linecap="round"/>
        <circle class="antenna-ball" cx="36" cy="5.5" r="4" :class="{ 'blink-warning': dangerCount > 0 }"/>
        <!-- 侧耳（头盔侧板） -->
        <ellipse class="ear" cx="13" cy="31" rx="4.2" ry="9"/>
        <ellipse class="ear" cx="59" cy="31" rx="4.2" ry="9"/>
        <!-- 头盔主体（铁甲小宝红） -->
        <path class="svg-body" d="M17 47 C17 16 55 16 55 47 Q55 69 36 69 Q17 69 17 47 Z"/>
        <!-- 头顶高光 -->
        <ellipse class="svg-body-high" cx="30" cy="18" rx="12" ry="4"/>
        <!-- 脸板（奶油色） -->
        <rect class="face" x="21" y="20" width="30" height="24" rx="9" fill="#fff7e6"/>
        <!-- 腮红 -->
        <circle class="cheek" cx="23" cy="35" r="2.8"/>
        <circle class="cheek" cx="49" cy="35" r="2.8"/>
        <!-- 眼睛 -->
        <g class="eye left-eye">
          <ellipse class="eyeball" cx="30" cy="29.5" rx="4" ry="5"/>
          <circle class="pupil" cx="30" cy="29.5" r="2.2"/>
        </g>
        <g class="eye right-eye">
          <ellipse class="eyeball" cx="42" cy="29.5" rx="4" ry="5"/>
          <circle class="pupil" cx="42" cy="29.5" r="2.2"/>
        </g>
        <!-- 眉毛 -->
        <line class="brow left-brow" x1="24" y1="23" x2="35" y2="21"/>
        <line class="brow right-brow" x1="48" y1="21" x2="37" y2="23"/>
        <!-- 嘴 -->
        <path class="mouth mouth-smile" d="M32 37 Q36 41 40 37" fill="none" stroke="#7f1d1d" stroke-width="2.2" stroke-linecap="round"/>
        <path class="mouth mouth-flat" d="M33 38 L39 38" fill="none" stroke="#7f1d1d" stroke-width="2.2" stroke-linecap="round"/>
        <path class="mouth mouth-open" d="M33 36 Q36 42 39 36" fill="#7f1d1d" stroke="#7f1d1d" stroke-width="2.2" stroke-linecap="round"/>
        <!-- 胸甲（奶油色徽记） -->
        <circle class="belly" cx="36" cy="56" r="8.5" fill="#fff7e6"/>
        <!-- 手臂 -->
        <ellipse class="arm" cx="15.5" cy="52" rx="4.4" ry="8" fill="#dc2626"/>
        <ellipse class="arm" cx="56.5" cy="52" rx="4.4" ry="8" fill="#dc2626"/>
        <!-- 脚 -->
        <ellipse class="foot" cx="28" cy="73" rx="7.5" ry="3.6" fill="#b91c1c"/>
        <ellipse class="foot" cx="44" cy="73" rx="7.5" ry="3.6" fill="#b91c1c"/>
</svg>
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
          <span class="bubble-title">{{ currentBubble.title }}</span>
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
          <div class="list-title">主动提醒</div>
          <div
            v-for="(r, idx) in displayedReminders"
            :key="r.title + idx"
            class="reminder-item"
            :class="'level-' + r.level"
            @click="goTo(r)"
          >
            <span class="item-icon" :class="'icon-' + r.type"></span>
            <div class="item-main">
              <div class="item-title">{{ r.title }}</div>
              <div class="item-content">{{ r.content }}</div>
              <div class="item-actions" v-if="r.actions && r.actions.length">
                <span
                  v-for="a in r.actions"
                  :key="a.type"
                  class="item-action"
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
import { Close, ChatDotRound, ArrowRight } from "@element-plus/icons-vue"
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
const pos = ref({ x: 24, y: 24 })
const dragOffset = ref({ x: 0, y: 0 })
const currentBubble = ref<Reminder | null>(null)
const seenTitles = ref<Set<string>>(new Set())
const showAll = ref(false)

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
const displayedReminders = computed(() =>
  showAll.value ? reminders.value : reminders.value.slice(0, 5)
)
const dangerCount = computed(
  () => (snapshot.value?.alert_stats.new ?? 0) + (snapshot.value?.sensor.abnormal ?? 0)
)
const newReminders = computed(() => reminders.value.filter((r) => !seenTitles.value.has(r.title)).length)
const hasReminder = computed(() => reminders.value.length > 0)

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
      if (typeof p.x === "number" && typeof p.y === "number") pos.value = p
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
    x: Math.max(0, Math.min(window.innerWidth - 90, e.clientX - dragOffset.value.x)),
    y: Math.max(0, Math.min(window.innerHeight - 120, e.clientY - dragOffset.value.y)),
  }
}

function endDrag() {
  if (!dragging.value) return
  dragging.value = false
  persistPosition()
  window.removeEventListener("mousemove", onDrag)
  window.removeEventListener("mouseup", endDrag)
}

function onBodyClick() {
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

function goTo(r: Reminder) {
  if (!canAccess(r)) {
    ElMessage.warning("你没有权限访问该页面")
    return
  }
  panelOpen.value = false
  collapsed.value = true
  currentBubble.value = null
  if (r.target) {
    router.push(r.target)
  } else {
    currentBubble.value = r
  }
}

async function runAction(r: Reminder, action: { type: string; label?: string; priority?: string }) {
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
    ElMessage.success("工单已创建")
    // 重新拉取快照，刷新提醒状态
    applyData(null)
    return res
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || "创建工单失败")
  }
}

function rotateBubble() {
  const unseen = reminders.value.filter((r) => !seenTitles.value.has(r.title))
  const pool = unseen.length ? unseen : reminders.value
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
  if (!currentBubble.value && reminders.value.length && !panelOpen.value) {
    rotateBubble()
  }
}

function startStreaming() {
  const base = (import.meta.env.VITE_API_BASE_URL || "/api/v1").replace(/\/$/, "")
  const token = localStorage.getItem("access_token")
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
  if (val) resetSeen()
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
.pet-body { position: absolute; left: 0; top: 0; width: 92px; height: 98px; cursor: pointer; transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.pet-body:hover { transform: translateY(-4px) scale(1.06); }
.pet-char {
  display: block; width: 88px; height: 94px; margin: 2px;
  overflow: visible;
  filter: drop-shadow(0 10px 22px rgba(220, 38, 38, 0.35));
  animation: breathe 3.4s ease-in-out infinite;
  transform-origin: center 78%;
  cursor: pointer;
}
.pet-char.squash { animation: squash 0.26s ease-in-out; }
.pet-char.jumping { animation: jump 0.9s ease-in-out infinite; }
/* ===== 身体与配色 ===== */
.svg-body { fill: #dc2626; transition: fill 0.3s ease; }
.svg-body-high { fill: rgba(255,255,255,0.35); }
.ear { fill: #b91c1c; transition: fill 0.3s ease; }
.cheek { fill: rgba(255,161,161,0.55); }
.foot { fill: rgba(15,23,42,0.16); }
/* ===== 天线 ===== */
.antenna { stroke: #64748b; }
.antenna-ball { fill: #22c55e; box-shadow: none; }
.antenna-ball.blink-warning { fill: #ef4444; animation: blink-warning 1s infinite; }
/* ===== 眼睛与瞳孔 ===== */
.eye { }
.eyeball { fill: #1e293b; transition: fill 0.25s ease; transform-box: fill-box; transform-origin: center; }
.pupil {
  fill: #fff;
  transform: translate(var(--eye-x, 0px), var(--eye-y, 0px));
  transition: transform 0.12s ease-out;
}
/* ===== 眉毛（SVG 线条绕中心旋转） ===== */
.brow { stroke: #1e293b; stroke-width: 2.4; stroke-linecap: round; transform-box: fill-box; transform-origin: center; transition: transform 0.25s ease; }
/* ===== 嘴形（按状态显示/隐藏） ===== */
.mouth { }
.mouth-flat { display: none; }
.mouth-open { display: none; }
/* ===== 健康：放松上扬眉毛 + 微笑 ===== */
.mood-healthy .left-brow { transform: rotate(14deg); }
.mood-healthy .right-brow { transform: rotate(-14deg); }
.mood-healthy .mouth-smile { display: block; }
/* ===== 一般：内端下压眉毛 + 平嘴 ===== */
.mood-attention .left-brow { transform: rotate(-9deg); }
.mood-attention .right-brow { transform: rotate(9deg); }
.mood-attention .eyeball { transform: scale(0.92, 0.8); }
.mood-attention .mouth-flat { display: block; }
/* ===== 告警：竖眉瞪眼张嘴（眼/身转红） ===== */
.mood-alert .left-brow { transform: rotate(22deg) translateY(1px); }
.mood-alert .right-brow { transform: rotate(-22deg) translateY(1px); }
.mood-alert .eyeball { fill: #7f1d1d; }
.mood-alert .pupil { fill: #fecaca; }
.mood-alert .mouth-open { display: block; }
.mood-alert .svg-body { fill: #ef4444; }
.mood-alert .ear { fill: #dc2626; }
.mood-alert .svg-body-high { fill: rgba(255,200,200,0.4); }
.mood-alert .cheek { fill: rgba(255,200,200,0.5); }
.mood-alert .antenna-ball { fill: #ef4444; box-shadow: none; }
.mood-attention .svg-body { fill: #f59e0b; }
.mood-attention .ear { fill: #d97706; }
.mood-attention .svg-body-high { fill: rgba(255,235,200,0.4); }
.mood-healthy .antenna-ball { fill: #22c55e; box-shadow: none; }
/* 默认隐藏所有嘴形，健康态显微笑已在上方覆盖 */
.mouth-smile, .mouth-flat, .mouth-open { }
.mood-attention .mouth-smile, .mood-attention .mouth-open { display: none; }
.mood-alert .mouth-smile, .mood-alert .mouth-flat { display: none; }
.pet-badge { position: absolute; top: -2px; right: -2px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: #ef4444; color: #fff; font-size: 11px; line-height: 20px; text-align: center; box-shadow: 0 2px 8px rgba(239,68,68,0.5); }
.reminder-bubble { position: absolute; left: 84px; top: 0; min-width: 230px; max-width: 300px; background: #fff; border-radius: 14px; box-shadow: 0 12px 32px rgba(15,23,42,0.18); padding: 12px 14px; cursor: pointer; border-left: 4px solid #3b82f6; }
.reminder-bubble.level-warning { border-left-color: #f59e0b; }
.reminder-bubble.level-danger { border-left-color: #ef4444; }
.bubble-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.bubble-title { font-weight: 600; font-size: 13px; color: #1e293b; }
.bubble-close { color: #94a3b8; cursor: pointer; font-size: 14px; }
.bubble-content { font-size: 12px; color: #475569; line-height: 1.5; }
.bubble-view { display: inline-flex; align-items: center; gap: 4px; margin-top: 10px; padding: 4px 12px; border-radius: 999px; background: #eff6ff; color: #2563eb; font-size: 12px; font-weight: 600; cursor: pointer; transition: background 0.2s; }
.bubble-view:hover { background: #dbeafe; }
.bubble-view .el-icon { font-size: 13px; }
.pet-panel { position: absolute; left: 84px; top: 60px; width: 320px; max-height: 62vh; overflow-y: auto; background: #fff; border-radius: 16px; box-shadow: 0 20px 50px rgba(15,23,42,0.22); padding: 14px; cursor: default; }
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
.icon-alert { background: #ef4444; } .icon-env { background: #3b82f6; } .icon-capacity { background: #f59e0b; }
.item-main { flex: 1; min-width: 0; }
.item-title { font-size: 12px; font-weight: 600; color: #334155; }
.item-content { font-size: 11px; color: #64748b; margin-top: 2px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.item-view { display: inline-flex; align-items: center; gap: 2px; margin-left: 6px; padding: 3px 8px; border-radius: 6px; background: #eff6ff; color: #2563eb; font-size: 11px; font-weight: 600; cursor: pointer; flex-shrink: 0; }
.item-view:hover { background: #dbeafe; }
.item-view .el-icon { font-size: 12px; }
.item-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.item-action { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 6px; background: #ecfdf5; color: #059669; font-size: 11px; font-weight: 600; cursor: pointer; border: 1px solid #a7f3d0; }
.item-action:hover { background: #d1fae5; }
.bubble-actions { display: flex; gap: 6px; margin-top: 8px; }
.bubble-action { display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 999px; background: #ecfdf5; color: #059669; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid #a7f3d0; }
.bubble-action:hover { background: #d1fae5; }
.icon-trend { background: #8b5cf6; }
.panel-footer { display: flex; align-items: center; gap: 6px; color: #3b82f6; font-size: 12px; font-weight: 600; padding: 10px; border-top: 1px solid #e2e8f0; margin-top: 8px; cursor: pointer; }
.foot-arrow { margin-left: auto; }
@keyframes breathe { 0%,100% { transform: translateY(0) scaleY(1); } 50% { transform: translateY(-3px) scaleY(1.02); } }
@keyframes jump { 0%,100% { transform: translateY(0); } 30% { transform: translateY(-8px) rotate(-2deg); } 55% { transform: translateY(-2px) scaleY(0.96); } 75% { transform: translateY(-5px); } }
@keyframes squash { 0% { transform: scale(1.25, 0.75); } 50% { transform: scale(0.92, 1.12); } 100% { transform: scale(1, 1); } }
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
