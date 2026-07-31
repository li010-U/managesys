<template>
  <div class="app-container" :class="{ dark: themeStore.isDark }">
    <el-container>
      <el-aside width="200px" class="sidebar">
        <div class="logo">
          <div class="logo-icon">
            <el-icon size="22"><DataBoard /></el-icon>
          </div>
          <span v-show="!appStore.sidebarCollapsed" class="logo-text">数据中心</span>
        </div>
        <el-menu 
          :default-active="route.path" 
          :collapse="appStore.sidebarCollapsed" 
          :collapse-transition="false" 
          router 
          background-color="transparent" 
          class="sidebar-menu"
          :class="{ 'menu-collapsed': appStore.sidebarCollapsed }"
        >
          <el-menu-item index="/dashboard">
            <el-icon><Odometer /></el-icon>
            <template #title>工作台</template>
          </el-menu-item>
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
        <div v-show="!appStore.sidebarCollapsed" class="sidebar-footer">
          <span class="footer-text">设计院: LATCDI</span>
        </div>
      </el-aside>
      <el-container class="main-container">
        <el-header class="app-header">
          <div class="header-left">
            <div class="collapse-btn" @click="appStore.toggleSidebar">
              <el-icon size="20">
                <Fold v-if="!appStore.sidebarCollapsed" />
                <Expand v-else />
              </el-icon>
            </div>
            <el-breadcrumb separator="/">
              <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
              <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
            </el-breadcrumb>
          </div>
          <div class="header-right">
            <ChatPanel v-model="chatVisible" />
            <el-button text class="header-btn" @click="chatVisible = true">
              <el-icon size="20"><ChatDotRound /></el-icon>
            </el-button>
            <div class="theme-toggle">
              <el-switch 
                v-model="themeStore.isDark" 
                @change="themeStore.toggle()" 
                inline-prompt 
                active-icon="Moon"
                inactive-icon="Sunny" 
                style="--el-switch-on-color: var(--el-color-primary)"
              />
            </div>
            <div class="user-info">
              <el-dropdown trigger="click" @command="handleCommand">
                <div class="user-avatar">
                  <el-avatar :size="36" class="avatar">
                    {{ authStore.user?.username?.[0]?.toUpperCase() }}
                  </el-avatar>
                  <span class="username">{{ authStore.user?.username }}</span>
                </div>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="profile">
                      <el-icon><User /></el-icon>个人中心
                    </el-dropdown-item>
                    <el-dropdown-item divided command="logout">
                      <el-icon><SwitchButton /></el-icon>退出登录
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>
          </div>
        </el-header>
        <div class="tab-bar">
          <div class="tab-items">
            <div 
              v-for="tab in tabsStore.tabs" 
              :key="tab.path" 
              :class="['tab-item', { active: tabsStore.activeTab === tab.path }]"
              @click="router.push(tab.path)"
            >
              <span>{{ tab.title }}</span>
              <el-icon 
                v-if="tab.path !== '/dashboard'" 
                class="tab-close"
                @click.stop="tabsStore.removeTab(tab.path)"
              >
                <Close />
              </el-icon>
            </div>
          </div>
        </div>
        <el-main class="app-main">
          <router-view v-slot="{ Component, route: currentRoute }">
            <transition name="page-fade" mode="out-in">
              <component :is="Component" :key="currentRoute.path" />
            </transition>
          </router-view>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { 
  Odometer, OfficeBuilding, Cpu, DataAnalysis, Setting, 
  Fold, Expand, ChatDotRound, User, SwitchButton, Close, DataBoard 
} from "@element-plus/icons-vue"
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
  if (cmd === "logout") { 
    authStore.logout(); 
    router.push("/login") 
  }
  else if (cmd === "profile") router.push("/profile")
}
</script>

<style scoped>
.app-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--app-bg-page);
}

.main-container {
  display: flex;
  flex-direction: column;
}

/* 侧边栏 */
.sidebar {
  background: var(--app-sidebar-bg) !important;
  border-right: none;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 12px rgba(0,0,0,0.08);
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  overflow: hidden;
}

.logo-icon {
  width: 36px;
  height: 36px;
  background: var(--app-gradient-primary);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(67, 97, 238, 0.4);
}

.logo-text {
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  white-space: nowrap;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.sidebar-menu {
  border: none;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 8px 0;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 200px;
}

:deep(.el-menu-item),
:deep(.el-sub-menu__title) {
  height: 48px;
  line-height: 48px;
  margin: 4px 8px;
  border-radius: 10px;
  color: var(--app-sidebar-text);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

:deep(.el-menu-item:hover),
:deep(.el-sub-menu__title:hover) {
  background: rgba(255,255,255,0.1) !important;
  color: #fff;
}

:deep(.el-menu-item.is-active) {
  background: rgba(67, 97, 238, 0.3) !important;
  color: #fff;
  border-left: 3px solid #4361ee;
}

:deep(.el-sub-menu .el-menu-item) {
  padding-left: 50px !important;
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
}

:deep(.el-sub-menu .el-menu-item.is-active) {
  background: rgba(67, 97, 238, 0.2) !important;
}

:deep(.el-sub-menu__title) {
  padding-left: 12px !important;
}

:deep(.el-icon) {
  margin-right: 8px;
}

.sidebar-footer {
  text-align: center;
  padding: 16px 0;
  border-top: 1px solid rgba(255,255,255,0.1);
}

.footer-text {
  font-size: 11px;
  color: rgba(255,255,255,0.5);
  letter-spacing: 0.5px;
}

/* 头部 */
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 60px;
  padding: 0 20px;
  background: var(--app-header-bg);
  border-bottom: 1px solid var(--app-border);
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.collapse-btn {
  cursor: pointer;
  color: var(--app-text-secondary);
  padding: 8px;
  border-radius: 8px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.collapse-btn:hover {
  color: var(--app-primary);
  background: var(--el-color-primary-light-9);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-btn {
  padding: 8px;
  border-radius: 8px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.header-btn:hover {
  background: var(--el-color-primary-light-9);
  color: var(--app-primary);
}

.theme-toggle {
  margin: 0 8px;
}

.user-info {
  cursor: pointer;
  margin-left: 8px;
}

.user-avatar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 12px 4px 4px;
  border-radius: 24px;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.user-avatar:hover {
  background: var(--el-fill-color-light);
}

.avatar {
  background: var(--app-gradient-primary);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(67, 97, 238, 0.3);
}

.username {
  font-size: 14px;
  color: var(--app-text-primary);
  font-weight: 500;
}

/* 标签栏 */
.tab-bar {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 12px;
  background: var(--app-bg-card);
  border-bottom: 1px solid var(--app-border);
  flex-shrink: 0;
}

.tab-items {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  flex: 1;
  padding: 4px 0;
}

.tab-items::-webkit-scrollbar {
  height: 0;
}

.tab-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
  color: var(--app-text-secondary);
  background: transparent;
  border: 1px solid transparent;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-item:hover {
  background: var(--el-fill-color-light);
  color: var(--app-text-primary);
}

.tab-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--app-primary);
  border-color: var(--el-color-primary-light-7);
  font-weight: 500;
}

html.dark .tab-item.active {
  background: rgba(67, 97, 238, 0.2);
}

.tab-close {
  font-size: 12px;
  padding: 2px;
  border-radius: 4px;
  transition: all 0.2s;
}

.tab-close:hover {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

/* 主内容区 */
.app-main {
  padding: 20px;
  overflow-y: auto;
  background: var(--app-bg-page);
  flex: 1;
}
</style>