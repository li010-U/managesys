<template>
  <div class="dashboard">
    <el-card class="welcome-banner" :body-style="{ padding: 0 }">
      <div class="welcome-content">
        <div class="welcome-text">
          <h2>{{ greeting }}，{{ authStore.user?.real_name || authStore.user?.username }}</h2>
          <p>欢迎使用设计总院 · 数据中心资源管理系统</p>
        </div>
        <div class="welcome-weather">
          <div class="date-info">{{ currentDate }}</div>
          <div class="week-info">{{ currentWeekday }}</div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20" class="stats-row">
      <el-col :span="6" v-for="(card, idx) in stats" :key="card.label">
        <el-card shadow="never" class="stat-card">
          <div class="stat-content">
            <div class="stat-info">
              <div class="stat-value">{{ card.animatedValue }}</div>
              <div class="stat-label">{{ card.label }}</div>
            </div>
            <div class="stat-icon" :style="{ background: card.bg }">
              <el-icon :size="24" color="#fff"><component :is="card.icon" /></el-icon>
            </div>
          </div>
          <div class="stat-trend" :style="{ color: card.trendColor }">{{ card.trend }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="section-card">
          <template #header><span class="section-title">快捷入口</span></template>
          <el-row :gutter="16">
            <el-col :span="6" v-for="(item, idx) in quickLinks" :key="item.label">
              <el-card shadow="never" class="quick-link" @click="item.action">
                <div class="quick-icon" :style="{ background: item.bg }">
                  <el-icon :size="22" color="#fff"><component :is="item.icon" /></el-icon>
                </div>
                <div class="quick-label">{{ item.label }}</div>
                <div class="quick-desc">{{ item.desc }}</div>
              </el-card>
            </el-col>
          </el-row>
        </el-card>

        <el-card class="section-card activity-card">
          <template #header>
            <span class="section-title">最近活动</span>
            <el-tag size="small" type="info">实时</el-tag>
          </template>
          <div class="activity-timeline">
            <div class="timeline-item" v-for="(act, idx) in activities" :key="idx">
              <div class="timeline-dot" :style="{ background: act.color }"></div>
              <div class="timeline-content">
                <div class="timeline-title">{{ act.text }}</div>
                <div class="timeline-time">{{ act.time }}</div>
              </div>
            </div>
            <el-empty v-if="activities.length === 0" :image-size="60" description="暂无活动记录" />
          </div>
        </el-card>
      </el-col>

      <el-col :span="8">
        <el-card class="section-card">
          <template #header><span class="section-title">当前用户</span></template>
          <div class="user-card">
            <el-avatar :size="56" class="user-avatar">{{ userNameInitial }}</el-avatar>
            <div class="user-detail">
              <div class="user-name">{{ authStore.user?.real_name || authStore.user?.username }}</div>
              <div class="user-role">{{ authStore.user?.roles?.map(r => r.name).join('、') || '-' }}</div>
              <div class="user-dept">{{ authStore.user?.department || '设计总院' }}</div>
            </div>
          </div>
          <el-divider class="info-divider" />
          <div class="info-list">
            <div class="info-item"><span class="info-label">邮箱</span><span class="info-value">{{ authStore.user?.email || '-' }}</span></div>
            <div class="info-item"><span class="info-label">手机</span><span class="info-value">{{ authStore.user?.phone || '-' }}</span></div>
          </div>
        </el-card>

        <el-card class="section-card sys-info-card">
          <template #header><span class="section-title">系统信息</span></template>
          <div class="sys-info-list">
            <div class="sys-info-item"><span class="sys-label">系统版本</span><span class="sys-value">v1.0.0</span></div>
            <div class="sys-info-item"><span class="sys-label">运行环境</span><el-tag size="small" type="success">运行中</el-tag></div>
            <div class="sys-info-item"><span class="sys-label">数据库</span><el-tag size="small" type="info">SQLite</el-tag></div>
            <div class="sys-info-item"><span class="sys-label">服务器时间</span><span class="sys-value">{{ currentTime }}</span></div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, markRaw, onMounted, onUnmounted } from "vue"
import { useRouter } from "vue-router"
import { useAuthStore } from "../../stores/auth"
import { Cpu, OfficeBuilding, WarningFilled, Monitor, Setting, UserFilled } from "@element-plus/icons-vue"
import { getDevicesApi } from "../../api/device"
import { getRoomsApi, getRacksApi } from "../../api/facility"
import { getAlertStatsApi } from "../../api/alert"

const router = useRouter()
const authStore = useAuthStore()
const currentDate = ref("")
const currentWeekday = ref("")
const currentTime = ref("")
let timer: ReturnType<typeof setInterval> | null = null

const userNameInitial = computed(() => {
  const name = authStore.user?.real_name || authStore.user?.username || "U"
  return name.charAt(0).toUpperCase()
})

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return "夜深了"
  if (hour < 9) return "早上好"
  if (hour < 12) return "上午好"
  if (hour < 14) return "中午好"
  if (hour < 18) return "下午好"
  return "晚上好"
})

const activities = ref<{ text: string; time: string; color: string }[]>([])

const stats = ref([
  { label: "设备总数", value: 0, animatedValue: 0, icon: markRaw(Cpu), bg: "linear-gradient(135deg, #1a5276, #2980b9)", trend: "待接入数据", trendColor: "#909399", target: 0 },
  { label: "机房数量", value: 0, animatedValue: 0, icon: markRaw(OfficeBuilding), bg: "linear-gradient(135deg, #1b7a5a, #27ae60)", trend: "待接入数据", trendColor: "#909399", target: 0 },
  { label: "机柜数量", value: 0, animatedValue: 0, icon: markRaw(Monitor), bg: "linear-gradient(135deg, #7d3c98, #9b59b6)", trend: "待接入数据", trendColor: "#909399", target: 0 },
  { label: "告警数量", value: 0, animatedValue: 0, icon: markRaw(WarningFilled), bg: "linear-gradient(135deg, #c0392b, #e74c3c)", trend: "暂无告警", trendColor: "#67C23A", target: 0 },
])

const quickLinks = [
  { label: "机柜视图", desc: "可视化机柜布局", icon: "Monitor", bg: "linear-gradient(135deg, #3498db, #2980b9)", action: () => router.push("/room/racks") },
  { label: "设备台账", desc: "设备清单管理", icon: "Cpu", bg: "linear-gradient(135deg, #2ecc71, #27ae60)", action: () => router.push("/device/list") },
  { label: "环境监测", desc: "温湿度监控", icon: "DataAnalysis", bg: "linear-gradient(135deg, #f39c12, #e67e22)", action: () => router.push("/environment") },
  { label: "监控看板", desc: "可视化监控", icon: "TrendCharts", bg: "linear-gradient(135deg, #9b59b6, #8e44ad)", action: () => router.push("/monitor/dashboard") },
]

async function loadStats() {
  try {
    const [devicePage, roomPage, rackPage, alertStats] = await Promise.all([
      getDevicesApi({ page: 1, page_size: 1 }),
      getRoomsApi({ page: 1, page_size: 1 }),
      getRacksApi({ page: 1, page_size: 1 }),
      getAlertStatsApi(),
    ])
    const deviceTotal = devicePage?.data?.total ?? 0
    const roomTotal = roomPage?.data?.total ?? 0
    const rackTotal = rackPage?.data?.total ?? 0
    const alertTotal = alertStats?.data?.total ?? 0
    const alertNew = alertStats?.data?.new ?? 0
    stats.value = stats.value.map((s) => {
      if (s.label === "\u8bbe\u5907\u603b\u6570") {
        s.value = deviceTotal; s.target = deviceTotal; s.trend = `${deviceTotal} \u9879\u7eb3\u5165\u53f0\u8d26`; s.trendColor = "#409EFF"
      } else if (s.label === "\u673a\u623f\u6570\u91cf") {
        s.value = roomTotal; s.target = roomTotal; s.trend = `${roomTotal} \u5904\u673a\u623f\u7ba1\u7406`; s.trendColor = "#409EFF"
      } else if (s.label === "\u673a\u67dc\u6570\u91cf") {
        s.value = rackTotal; s.target = rackTotal; s.trend = `${rackTotal} \u4e2a\u673a\u67dc`; s.trendColor = "#409EFF"
      } else if (s.label === "\u544a\u8b66\u6570\u91cf") {
        s.value = alertTotal; s.target = alertTotal
        if (alertNew > 0) { s.trend = `${alertNew} \u6761\u672a\u5904\u7406`; s.trendColor = "#E74C3C" }
        else { s.trend = "\u6682\u65e0\u672a\u5904\u7406\u544a\u8b66"; s.trendColor = "#67C23A" }
      }
      return s
    })
    stats.value.forEach((s) => animateValue(s))
  } catch (e) {
    // load failed
  }
}

function updateTime() {
  const now = new Date()
  currentDate.value = now.toLocaleDateString("zh-CN")
  currentWeekday.value = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][now.getDay()]
  currentTime.value = now.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })
}

function animateValue(card: { value: number; animatedValue: number; target: number }) {
  const target = card.target || card.value
  const duration = 1000
  const start = performance.now()
  const from = card.animatedValue

  function step(now: number) {
    const progress = Math.min((now - start) / duration, 1)
    card.animatedValue = Math.round(from + (target - from) * progress)
    if (progress < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

onMounted(() => {
  updateTime()
  timer = setInterval(updateTime, 1000)
  loadStats()
  stats.value.forEach(s => animateValue(s))
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.dashboard { max-width: 1400px; animation: fadeIn 0.4s ease; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

.welcome-banner { margin-bottom: 20px; border-radius: 12px; border: none; overflow: hidden; }
.welcome-content { display: flex; justify-content: space-between; align-items: center; padding: 28px 32px; background: linear-gradient(135deg, #1a5276 0%, #2980b9 50%, #1f6f8b 100%); color: #fff; }
.welcome-text h2 { font-size: 22px; margin: 0 0 6px; font-weight: 600; }
.welcome-text p { font-size: 14px; margin: 0; opacity: 0.75; }
.welcome-weather { text-align: right; }
.date-info { font-size: 16px; font-weight: 500; }
.week-info { font-size: 13px; opacity: 0.7; margin-top: 2px; }

.stats-row { margin-bottom: 20px; }
.stat-card { border-radius: 10px; border: 1px solid var(--el-border-color-light); animation: cardFadeIn 0.5s ease both; }
@keyframes cardFadeIn { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.stat-content { display: flex; align-items: center; justify-content: space-between; }
.stat-info { flex: 1; }
.stat-value { font-size: 28px; font-weight: 700; color: var(--el-text-color-primary); }
.stat-label { font-size: 13px; color: var(--el-text-color-secondary); margin-top: 2px; }
.stat-icon { width: 48px; height: 48px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.stat-trend { font-size: 12px; margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--el-border-color-lighter); }

.section-card { border-radius: 10px; border: 1px solid var(--el-border-color-light); margin-bottom: 20px; }
.section-header { display: flex; align-items: center; justify-content: space-between; }
.section-title { font-size: 15px; font-weight: 600; }

.quick-link { text-align: center; cursor: pointer; transition: all 0.3s; border-radius: 8px; border: none; padding: 16px 8px; background: var(--el-fill-color-lighter); }
.quick-link:hover { transform: translateY(-2px); }
.quick-icon { width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin: 0 auto 10px; }
.quick-label { font-size: 14px; font-weight: 500; margin-bottom: 4px; }
.quick-desc { font-size: 12px; color: var(--el-text-color-secondary); }

.activity-timeline { padding: 4px 0; }
.timeline-item { display: flex; gap: 12px; padding: 10px 0; position: relative; }
.timeline-item:not(:last-child)::after { content: ''; position: absolute; left: 5px; top: 24px; bottom: 0; width: 1px; background: var(--el-border-color-lighter); }
.timeline-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: 4px; }
.timeline-content { flex: 1; min-width: 0; }
.timeline-title { font-size: 13px; }
.timeline-time { font-size: 11px; color: var(--el-text-color-secondary); margin-top: 2px; }

.user-card { display: flex; align-items: center; gap: 14px; }
.user-avatar { background: linear-gradient(135deg, #409EFF, #66b1ff); color: #fff; font-size: 18px; font-weight: 600; flex-shrink: 0; }
.user-detail { flex: 1; min-width: 0; }
.user-name { font-size: 16px; font-weight: 600; }
.user-role { font-size: 13px; color: #409EFF; margin-top: 2px; }
.user-dept { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 2px; }
.info-divider { margin: 16px 0; }
.info-list { display: flex; flex-direction: column; gap: 10px; }
.info-item { display: flex; justify-content: space-between; font-size: 13px; }
.info-label { color: var(--el-text-color-secondary); }
.info-value { color: var(--el-text-color-primary); }

.sys-info-card { margin-top: 20px; }
.sys-info-list { display: flex; flex-direction: column; gap: 12px; }
.sys-info-item { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.sys-label { color: var(--el-text-color-secondary); }
.sys-value { color: var(--el-text-color-primary); }
</style>
