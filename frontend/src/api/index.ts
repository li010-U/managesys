import axios from 'axios'
import type { AxiosInstance, InternalAxiosRequestConfig, AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const http: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// ===== 请求取消管理 =====
// 路由切换时中止旧页面的在途请求，避免“快速连续点击两个功能”时，
// 上一个页面的慢请求继续占用资源/抛出过期错误导致新页面看起来加载不出来。
const pendingControllers = new Set<AbortController>()

function abortPendingRequests() {
  for (const controller of pendingControllers) {
    controller.abort()
  }
  pendingControllers.clear()
}

// 监听路由导航事件（由 router/index.ts 派发），统一中止在途请求。
if (typeof window !== 'undefined') {
  window.addEventListener('app:navigate', abortPendingRequests)
}

function removeController(config?: InternalAxiosRequestConfig) {
  const controller = (config as InternalAxiosRequestConfig & { _abortController?: AbortController } | undefined)?._abortController
  if (controller) {
    pendingControllers.delete(controller)
  }
}

// 请求拦截器：为每个请求绑定 AbortSignal 并登记，添加JWT令牌
http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    // 只为浏览器请求附加取消控制器
    if (typeof window !== 'undefined' && !config.signal) {
      const controller = new AbortController()
      config.signal = controller.signal
      ;(config as InternalAxiosRequestConfig & { _abortController?: AbortController })._abortController = controller
      pendingControllers.add(controller)
    }
    return config
  },
  (error) => Promise.reject(error),
)

// 响应拦截器：统一错误处理，并在请求结束后清理登记
http.interceptors.response.use(
  (response) => {
    // 请求成功完成后移除登记，避免集合无限增长
    removeController(response?.config as InternalAxiosRequestConfig)
    return response
  },
  (error: AxiosError) => {
    // 请求结束（成功或失败）都清理登记
    removeController(error?.config as InternalAxiosRequestConfig)
    // 因路由切换主动中止的请求：静默忽略，不弹出过期错误，不打断新页面。
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject(error)
    }
    if (error.response) {
      const { status, data } = error.response as { status: number; data: any }
      if (status === 401) {
        localStorage.removeItem('access_token')
        router.push('/login')
        ElMessage.error('登录已过期，请重新登录')
      } else if (status === 403) {
        ElMessage.error(data?.detail || '权限不足')
      } else if (status === 404) {
        ElMessage.error(data?.detail || '资源不存在')
      } else {
        ElMessage.error(data?.detail || '请求失败')
      }
    } else {
      ElMessage.error('网络错误，请检查连接')
    }
    return Promise.reject(error)
  },
)

export default http
