import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import { useAuthStore } from '../stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/login/LoginView.vue'),
    meta: { requiresAuth: false, title: '登录' },
  },
  {
    path: '/',
    component: () => import('../layouts/MainLayout.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/dashboard/DashboardView.vue'),
        meta: { title: '工作台', icon: 'Odometer', permission: '' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('../views/system/ProfileView.vue'),
        meta: { title: '个人中心', icon: 'User', permission: '' },
      },
      {
        path: 'system/users',
        name: 'Users',
        component: () => import('../views/system/UserView.vue'),
        meta: { title: '用户管理', icon: 'UserFilled', permission: 'user:view' },
      },
      {
        path: 'system/roles',
        name: 'Roles',
        component: () => import('../views/system/RoleView.vue'),
        meta: { title: '角色管理', icon: 'Setting', permission: 'role:view' },
      },
      {
        path: 'system/audit-logs',
        name: 'AuditLogs',
        component: () => import('../views/system/AuditLogView.vue'),
        meta: { title: '审计日志', icon: 'Document', permission: 'audit:view' },
      },
      {
        path: 'workorder/list',
        name: 'WorkOrderList',
        component: () => import('../views/workorder/WorkOrderView.vue'),
        meta: { title: '运维工单', icon: 'Tickets', permission: 'work:view' },
      },
      {
        path: 'inspection',
        name: 'Inspection',
        component: () => import('../views/inspection/InspectionView.vue'),
        meta: { title: '设备巡检', icon: 'DocumentChecked', permission: 'inspection:view' },
      },
      {
        path: 'room/facility',
        name: 'Facility',
        component: () => import('../views/room/FacilityView.vue'),
        meta: { title: '机柜管理', icon: 'OfficeBuilding', permission: '' },
      },
      {
        path: 'room/racks',
        name: 'Racks',
        component: () => import('../views/room/RackView.vue'),
        meta: { title: '机柜视图', icon: 'Monitor', permission: '' },
      },
      {
        path: 'device/list',
        name: 'DeviceList',
        component: () => import('../views/device/DeviceView.vue'),
        meta: { title: '设备台账', icon: 'Cpu', permission: '' },
      },
      {
        path: 'device/types',
        name: 'DeviceTypes',
        component: () => import('../views/device/DeviceTypeView.vue'),
        meta: { title: '设备类型', icon: 'Collection', permission: '' },
      },
      {
        path: 'environment',
        name: 'Environment',
        component: () => import('../views/environment/EnvironmentView.vue'),
        meta: { title: '环境监测', icon: 'ColdDrink', permission: '' },
      },
      {
        path: 'monitor/dashboard',
        name: 'MonitorDashboard',
        component: () => import('../views/monitor/MonitorDashboard.vue'),
        meta: { title: '可视化监控', icon: 'DataAnalysis', permission: '' },
      },
      {
        path: 'monitor/alerts',
        name: 'AlertManagement',
        component: () => import('../views/monitor/AlertView.vue'),
        meta: { title: '告警管理', icon: 'Bell', permission: 'monitor:view_alerts' },
      },
      {
        path: 'system/business',
        name: 'BusinessSystems',
        component: () => import('../views/system/SystemView.vue'),
        meta: { title: '系统台账', icon: 'Tickets', permission: 'system:view' },
      },
      // ===== Canvas 可视化投屏 =====
      {
        path: 'canvas',
        name: 'CanvasView',
        component: () => import('../views/canvas/CanvasView.vue'),
        meta: { title: 'Canvas投屏', icon: 'Monitor', permission: '' },
      },
    ],
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('../views/error/ForbiddenView.vue'),
    meta: { requiresAuth: false, title: '权限不足' },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('../views/error/NotFoundView.vue'),
    meta: { requiresAuth: false, title: '页面不存在' },
  },
]

// 记录进行中的导航数量，保证 start()/done() 始终配对，
// 快速连续点击菜单时不会卡在加载进度状态。
let pendingNavCount = 0

function beginNavigation() {
  pendingNavCount++
  NProgress.start()
}

function finishNavigation() {
  pendingNavCount = Math.max(0, pendingNavCount - 1)
  if (pendingNavCount === 0) {
    NProgress.done()
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  beginNavigation()

  // 通知全局请求层：路由开始切换，中止上一个页面的在途请求，
  // 避免快速连续点击功能时旧请求残留导致新页面加载异常。
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('app:navigate'))
  }

  const authStore = useAuthStore()

  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    next('/login')
    return
  }

  // 已登录但用户信息尚未加载（如刷新页面）：先拉取一次用户信息，
  // 避免权限校验失败被误跳 /403、用户名缺失等刷新后的不稳定现象。
  if (authStore.isAuthenticated && !authStore.user) {
    try {
      await authStore.fetchUserInfo()
    } catch {
      // token 失效等情况：axios 拦截器会处理提示，这里回到登录页
      next('/login')
      return
    }
  }

  if (to.path === '/login' && authStore.isAuthenticated) {
    next('/dashboard')
    return
  }

  const requiredPermission = to.meta.permission as string
  if (requiredPermission && authStore.isAuthenticated) {
    if (!authStore.hasPermission(requiredPermission)) {
      next('/403')
      return
    }
  }

  next()
})

router.afterEach((_to, _from, failure) => {
  // 无论成功、被重定向还是导航被中止，都结束本次导航的进度
  finishNavigation()
})

router.onError((_error) => {
  finishNavigation()
})

export default router

