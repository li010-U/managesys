import { defineStore } from "pinia"
import { ref, computed } from "vue"
import type { RouteLocationNormalized } from "vue-router"

export interface TabItem {
  title: string
  name: string
  path: string
  icon?: string
  closable: boolean
}

export const useTabsStore = defineStore("tabs", () => {
  const tabs = ref<TabItem[]>([
    { title: "工作台", name: "Dashboard", path: "/dashboard", closable: false },
  ])
  const activeTab = ref("/dashboard")
  const tabNames = computed(() => new Set(tabs.value.map(t => t.path)))

  function addTab(route: RouteLocationNormalized) {
    const path = route.path
    if (tabNames.value.has(path)) {
      activeTab.value = path
      return
    }
    const title = (route.meta?.title as string) || route.name?.toString() || path.split("/").filter(Boolean).pop() || "未知"
    tabs.value.push({
      title,
      name: (route.name as string) || path,
      path,
      closable: tabs.value.length > 0,
    })
    activeTab.value = path
  }

  function removeTab(path: string) {
    const idx = tabs.value.findIndex(t => t.path === path)
    if (idx === -1 || !tabs.value[idx].closable) return
    tabs.value.splice(idx, 1)
    if (activeTab.value === path) {
      const nextIdx = Math.min(idx, tabs.value.length - 1)
      activeTab.value = tabs.value[nextIdx]?.path || "/dashboard"
    }
  }

  function clearTabs() {
    tabs.value = tabs.value.filter(t => !t.closable)
    activeTab.value = tabs.value[0]?.path || "/dashboard"
  }

  function setActiveTab(path: string) {
    activeTab.value = path
  }

  return { tabs, activeTab, addTab, removeTab, clearTabs, setActiveTab }
})
