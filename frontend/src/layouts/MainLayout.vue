<template>
  <div class="app-container" :class="{ dark: themeStore.isDark }">
    <el-container>
      <el-aside width="200px" class="sidebar">
        <div class="logo">
          <span v-show="!appStore.sidebarCollapsed">数据中心</span>
        </div>
        <el-menu :default-active="route.path" :collapse="appStore.sidebarCollapsed" :collapse-transition="false" router background-color="transparent" class="sidebar-menu">
          <el-menu-item index="/dashboard"><el-icon><Odometer /></el-icon><template #title>工作台</template></el-menu-item>
          <el-sub-menu index="/room">
            <template #title><el-icon><OfficeBuilding /></el-icon><span>机房管理</span></template>
            <el-menu-item index="/room/facility">机房管理</el-menu-item>
            <el-menu-item index="/room/racks">机柜视图</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="/device">
            <template #title><el-icon><Cpu /></el-icon><span>设备管理</span></template>
            <el-menu-item index="/device/list">设备台账</el-menu-item>
            <el-menu-item index="/device/types">设备类型</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="/env">
            <template #title><el-icon><DataAnalysis /></el-icon><span>监控管理</span></template>
            <el-menu-item index="/environment">环境监测</el-menu-item>
            <el-menu-item index="/monitor/dashboard">可视化监控</el-menu-item>
            <el-menu-item index="/monitor/alerts">告警管理</el-menu-item>
            <el-menu-item index="/canvas">Canvas投屏</el-menu-item>
          </el-sub-menu>
          <el-sub-menu index="/system">
            <template #title><el-icon><Setting /></el-icon><span>系统管理</span></template>
            <el-menu-item index="/system/users">用户管理</el-menu-item>
            <el-menu-item index="/system/roles">角色管理</el-menu-item>
            <el-menu-item index="/system/business">系统台账</el-menu-item>
            <el-menu-item index="/system/audit-logs">审计日志</el-menu-item>
          </el-sub-menu>
        </el-menu>
        <div v-show="!appStore.sidebarCollapsed" class="sidebar-footer"><span class="footer-text">设计院 路 ATCDI</span></div>
      </el-aside>
      <el-container>
        <el-header class="app-header">
          <div class="header-left">
            <div class="collapse-btn" @click="appStore.toggleSidebar"><el-icon size="20"><Fold v-if="!appStore.sidebarCollapsed" /><Expand v-else /></el-icon></div>
            <el-breadcrumb separator="/"><el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item><el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item></el-breadcrumb>
          </div>
          <div class="header-right">
            <ChatPanel v-model="chatVisible" />
            <el-button text @click="chatVisible = true"><el-icon size="20"><ChatDotRound /></el-icon></el-button>
            <el-switch v-model="themeStore.isDark" @change="themeStore.toggle()" inline-prompt active-icon="Moon" inactive-icon="Sunny" style="--el-switch-on-color: var(--el-color-primary)" />
            <div class="user-info">
              <el-dropdown trigger="click" @command="handleCommand">
                <div class="user-avatar"><el-avatar :size="32">{{ authStore.user?.username?.[0]?.toUpperCase() }}</el-avatar></div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="profile"><el-icon><User /></el-icon>个人中心</el-dropdown-item>
                    <el-dropdown-item divided command="logout"><el-icon><SwitchButton /></el-icon>退出登录</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </el-header>
        <div class="tab-bar">
          <div class="tab-items">
            <div v-for="tab in tabsStore.tabs" :key="tab.path" :class="['tab-item', { active: tabsStore.activeTab === tab.path }]" @click="router.push(tab.path)">
              <span>{{ tab.title }}</span>
              <el-icon v-if="tab.path !== '/dashboard'" class="tab-close" @click.stop="tabsStore.removeTab(tab.path)"><Close /></el-icon>
            </div>
          </div>
        </div>
        <el-main class="app-main"><router-view /></el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Odometer, OfficeBuilding, Cpu, DataAnalysis, Setting, Fold, Expand, ChatDotRound, User, SwitchButton, Close } from "@element-plus/icons-vue"
import { useAppStore } from "../stores"
import { useAuthStore } from "../stores/auth"
import { useThemeStore } from "../stores/theme"
import { useTabsStore } from "../stores/tabs"
import ChatPanel from "../components/chat/ChatPanel.vue"

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()
const themeStore = useThemeStore()
const tabsStore = useTabsStore()
const chatVisible = ref(false)

function handleCommand(cmd: string) {
  if (cmd === "logout") { authStore.logout(); router.push("/login") }
  else if (cmd === "profile") router.push("/profile")
}
</script>

<style scoped>
.app-container { width: 100vw; height: 100vh; overflow: hidden; background: var(--el-bg-color); }
.sidebar { background: var(--el-bg-color-page); border-right: 1px solid var(--el-border-color-light); display: flex; flex-direction: column; }
.logo { height: 50px; display: flex; align-items: center; padding: 0 16px; font-weight: 600; font-size: 16px; border-bottom: 1px solid var(--el-border-color-light); }
.sidebar-menu { border: none; flex: 1; overflow-y: auto; padding: 8px 0; }
:deep(.el-menu-item), :deep(.el-sub-menu__title) { height: 44px; line-height: 44px; }
:deep(.el-menu-item.is-active) { background: var(--el-color-primary-light-9) !important; }
:deep(.el-sub-menu .el-menu-item) { padding-left: 50px !important; }
.sidebar-footer { text-align: center; padding: 12px 0; border-top: 1px solid var(--el-border-color-light); }
.footer-text { font-size: 11px; color: var(--el-text-color-secondary); }
.app-header { display: flex; align-items: center; justify-content: space-between; height: 50px; padding: 0 16px; background: var(--el-bg-color); border-bottom: 1px solid var(--el-border-color); flex-shrink: 0; }
.header-left { display: flex; align-items: center; gap: 12px; }
.collapse-btn { cursor: pointer; color: var(--el-text-color-secondary); padding: 4px; border-radius: 6px; }
.collapse-btn:hover { color: var(--el-color-primary); background: var(--el-fill-color-light); }
.header-right { display: flex; align-items: center; gap: 12px; }
.user-info { cursor: pointer; }
.tab-bar { display: flex; align-items: center; height: 36px; padding: 0 8px; background: var(--el-bg-color); border-bottom: 1px solid var(--el-border-color); }
.tab-items { display: flex; gap: 4px; overflow-x: auto; flex: 1; }
.tab-items::-webkit-scrollbar { height: 0; }
.tab-item { display: flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 4px; font-size: 13px; cursor: pointer; white-space: nowrap; color: var(--el-text-color-secondary); }
.tab-item:hover { background: var(--el-fill-color-light); }
.tab-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.tab-close { font-size: 12px; }
.tab-close:hover { background: var(--el-color-danger-light-8); color: var(--el-color-danger); border-radius: 2px; }
.app-main { padding: 16px; overflow-y: auto; background: var(--el-bg-color-page); }
</style>