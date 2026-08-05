<template>
  <el-popover
    :visible="visible"
    placement="bottom-end"
    :width="360"
    trigger="click"
    @update:visible="(val: boolean) => visible = val"
  >
    <template #reference>
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-icon :size="20" class="notification-icon">
          <Bell />
        </el-icon>
      </el-badge>
    </template>

    <div class="notification-panel">
      <div class="notification-header">
        <span class="title">消息通知</span>
        <el-button type="primary" text size="small" @click="markAllRead" v-if="unreadCount > 0">
          全部已读
        </el-button>
      </div>

      <div class="notification-list" v-if="notifications.length > 0">
        <div
          v-for="item in notifications"
          :key="item.id"
          :class="['notification-item', { unread: !item.read }]"
          @click="handleClick(item)"
        >
          <div class="item-icon" :style="{ background: getTypeColor(item.type) }">
            <el-icon><component :is="getTypeIcon(item.type)" /></el-icon>
          </div>
          <div class="item-content">
            <div class="item-title">{{ item.title }}</div>
            <div class="item-desc">{{ item.content }}</div>
            <div class="item-time">{{ formatTime(item.created_at) }}</div>
          </div>
          <el-badge is-dot v-if="!item.read" class="unread-dot" />
        </div>
      </div>

      <el-empty v-else description="暂无消息" :image-size="60" />

      <div class="notification-footer" v-if="notifications.length > 0">
        <el-button type="primary" text size="small" @click="visible = false">
          查看更多
        </el-button>
      </div>
    </div>
  </el-popover>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { Bell, Warning, InfoFilled, CircleCheck, Message } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

interface Notification {
  id: number;
  type: "info" | "warning" | "success" | "alert";
  title: string;
  content: string;
  read: boolean;
  created_at: string;
}

const visible = ref(false);
const notifications = ref<Notification[]>([]);
let timer: ReturnType<typeof setInterval> | null = null;
let visibilityHandler: (() => void) | null = null;

const unreadCount = computed(() => notifications.value.filter(n => !n.read).length);

function getTypeColor(type: string) {
  const colors: Record<string, string> = {
    info: "#409EFF",
    warning: "#E6A23C",
    success: "#67C23A",
    alert: "#F56C6C",
  };
  return colors[type] || colors.info;
}

function getTypeIcon(type: string) {
  const icons: Record<string, string> = {
    info: "InfoFilled",
    warning: "Warning",
    success: "CircleCheck",
    alert: "Warning",
  };
  return icons[type] || "InfoFilled";
}

function formatTime(timeStr: string) {
  if (!timeStr) return "";
  const d = new Date(timeStr);
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return Math.floor(diff / 60000) + "分钟前";
  if (diff < 86400000) return Math.floor(diff / 3600000) + "小时前";
  return d.toLocaleDateString("zh-CN");
}

function handleClick(item: Notification) {
  if (!item.read) {
    item.read = true;
  }
  if (item.content.includes("告警")) {
    ElMessage.warning(item.content);
  }
}

function markAllRead() {
  notifications.value.forEach(n => n.read = true);
}

function loadNotifications() {
  // 模拟消息数据
  notifications.value = [
    {
      id: 1,
      type: "alert",
      title: "温度告警",
      content: "主机房温度超过28°C，请检查空调运行状态",
      read: false,
      created_at: new Date(Date.now() - 300000).toISOString(),
    },
    {
      id: 2,
      type: "success",
      title: "设备上线",
      content: "服务器 SRV-001 已成功上架到机柜 A-01",
      read: false,
      created_at: new Date(Date.now() - 3600000).toISOString(),
    },
    {
      id: 3,
      type: "info",
      title: "巡检提醒",
      content: "设备巡检任务将于明天到期，请及时处理",
      read: true,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    },
  ];
}

function startPolling() {
  if (timer) return;
  timer = setInterval(loadNotifications, 60000);
}
function stopPolling() {
  if (timer) { clearInterval(timer); timer = null; }
}

onMounted(() => {
  loadNotifications();
  // 每分钟刷新一次
  startPolling();
  visibilityHandler = () => {
    if (document.hidden) stopPolling();
    else startPolling();
  };
  document.addEventListener("visibilitychange", visibilityHandler);
});

onUnmounted(() => {
  if (visibilityHandler) document.removeEventListener("visibilitychange", visibilityHandler);
  stopPolling();
});
</script>

<style scoped>
.notification-panel {
  margin: -12px;
}

.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.notification-header .title {
  font-weight: 600;
  font-size: 15px;
}

.notification-list {
  max-height: 400px;
  overflow-y: auto;
}

.notification-item {
  display: flex;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
  position: relative;
}

.notification-item:hover {
  background: var(--el-fill-color-light);
}

.notification-item.unread {
  background: var(--el-color-primary-light-9);
}

.item-icon {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-weight: 500;
  font-size: 14px;
  margin-bottom: 4px;
}

.item-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}

.unread-dot {
  position: absolute;
  top: 16px;
  right: 16px;
}

.notification-footer {
  padding: 8px 16px;
  border-top: 1px solid var(--el-border-color-lighter);
  text-align: center;
}

.notification-icon {
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: color 0.2s;
}

.notification-icon:hover {
  color: var(--el-color-primary);
}
</style>
