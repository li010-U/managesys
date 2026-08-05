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
      @click="togglePanel"
      :title="advisor?.mood || ''"
    >
      <div class="pet-char" :class="{ sleeping: !panelOpen && !hasReminder }">
        <div class="eye left-eye">
          <div class="pupil"></div>
        </div>
        <div class="eye right-eye">
          <div class="pupil"></div>
        </div>
        <div class="mouth"></div>
        <div class="antenna">
          <div class="antenna-ball" :class="{ 'blink-warning': dangerCount > 0 }"></div>
        </div>
      </div>
      <transition name="pop">
        <div v-if="newReminders > 0" class="pet-badge">{{ newReminders }}</div>
      </transition>
    </div>

    <transition name="bubble">
      <div
        v-if="currentBubble"
        class="reminder-bubble"
        :class="'level-' + currentBubble.level"
        @click.stop="openPanel"
      >
        <div class="bubble-head">
          <span class="bubble-title">{{ currentBubble.title }}</span>
          <el-icon class="bubble-close" @click.stop="dismissBubble"><Close /></el-icon>
        </div>
        <div class="bubble-content">{{ currentBubble.content }}</div>
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
            @click="showReminder(r)"
          >
            <span class="item-icon" :class="'icon-' + r.type"></span>
            <div class="item-main">
              <div class="item-title">{{ r.title }}</div>
              <div class="item-content">{{ r.content }}</div>
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
import { Close, ChatDotRound, ArrowRight } from "@element-plus/icons-vue"
import { getAssistantSnapshotApi, type AssistantPayload, type Reminder } from "../../api/assistant"

const emit = defineEmits<{ (e: "open-chat"): void }>()

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

function showReminder(r: Reminder) {
  currentBubble.value = r
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
          if (done) { startPolling(); return }
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() || ""
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const chunk = line.slice(6)
              if (chunk === "[DONE]") { startPolling(); return }
              try {
                const payload = JSON.parse(chunk) as AssistantPayload
                data.value = payload
                maybeBubble()
              } catch { /* ignore */ }
            }
          }
          pump()
        }).catch((err) => {
          if (streamAbort?.signal.aborted) return
          startPolling()
        })
      }
      pump()
    })
    .catch(() => {
      if (streamAbort?.signal.aborted) return
      startPolling()
    })
}

let streamActive = false
function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(() => applyData(null), 15000)
}

function stopStreaming() {
  if (streamAbort) { streamAbort.abort(); streamAbort = null }
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
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
})
</script>

<style scoped>
.pet-assistant { position: fixed; z-index: 3000; user-select: none; }
.pet-body { position: absolute; left: 0; top: 0; width: 72px; height: 76px; cursor: pointer; transition: transform 0.25s; }
.pet-body:hover { transform: translateY(-4px); }
.pet-char {
  position: relative; width: 64px; height: 64px; margin: 4px;
  border-radius: 46% 54% 50% 50% / 44% 44% 56% 56%;
  background: linear-gradient(145deg, #7dd3fc, #3b82f6);
  box-shadow: 0 10px 24px rgba(59, 130, 246, 0.45);
  animation: idle 3.2s ease-in-out infinite;
}
.pet-char::after { content: ""; position: absolute; bottom: -8px; width: 34px; height: 10px; background: rgba(15,23,42,0.18); border-radius: 50%; filter: blur(2px); }
.eye { position: absolute; width: 9px; height: 12px; background: #1e293b; border-radius: 50%; top: 26px; overflow: hidden; animation: blink 4s infinite; }
.left-eye { left: 18px; } .right-eye { right: 18px; }
.pupil { width: 4px; height: 4px; background: #fff; border-radius: 50%; position: absolute; bottom: 1px; left: 2px; }
.mood-alert .pet-char { background: linear-gradient(145deg, #fca5a5, #ef4444); box-shadow: 0 10px 24px rgba(239,68,68,0.5); }
.mood-alert .eye { background: #7f1d1d; }
.mood-attention .pet-char { background: linear-gradient(145deg, #fcd34d, #f59e0b); box-shadow: 0 10px 24px rgba(245,158,11,0.5); }
.mouth { position: absolute; bottom: 14px; width: 18px; height: 8px; border-bottom: 2.5px solid #1e293b; border-radius: 0 0 12px 12px; }
.mood-healthy .mouth { width: 16px; height: 9px; border: 2.5px solid #1e293b; border-top: none; border-radius: 0 0 16px 16px; }
.antenna { position: absolute; top: -10px; left: 50%; transform: translateX(-50%); width: 2px; height: 12px; background: #64748b; }
.antenna-ball { position: absolute; top: -8px; left: 50%; transform: translateX(-50%); width: 10px; height: 10px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.8); }
.antenna-ball.blink-warning { background: #ef4444; box-shadow: 0 0 10px rgba(239,68,68,0.9); animation: blink-warning 1s infinite; }
.pet-badge { position: absolute; top: -2px; right: -2px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 10px; background: #ef4444; color: #fff; font-size: 11px; line-height: 20px; text-align: center; box-shadow: 0 2px 8px rgba(239,68,68,0.5); }
.reminder-bubble { position: absolute; left: 84px; top: 0; min-width: 230px; max-width: 300px; background: #fff; border-radius: 14px; box-shadow: 0 12px 32px rgba(15,23,42,0.18); padding: 12px 14px; cursor: pointer; border-left: 4px solid #3b82f6; }
.reminder-bubble.level-warning { border-left-color: #f59e0b; }
.reminder-bubble.level-danger { border-left-color: #ef4444; }
.bubble-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.bubble-title { font-weight: 600; font-size: 13px; color: #1e293b; }
.bubble-close { color: #94a3b8; cursor: pointer; font-size: 14px; }
.bubble-content { font-size: 12px; color: #475569; line-height: 1.5; }
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
.panel-footer { display: flex; align-items: center; gap: 6px; color: #3b82f6; font-size: 12px; font-weight: 600; padding: 10px; border-top: 1px solid #e2e8f0; margin-top: 8px; cursor: pointer; }
.foot-arrow { margin-left: auto; }
@keyframes idle { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-3px) rotate(-1deg); } }
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
