import type { AxiosResponse } from "axios"
import http from "./index"

// 轻量字典数据缓存：用于不常变的基础数据（设备类型、机房、机柜、数据中心等下拉/字典），
// 避免每个页面首次打开都重复请求，减少来回切换时的网络与后端压力。
// 特性：TTL 缓存 + 并发去重（同一时间多个组件请求同一地址时共享一次请求）。
// 语义与 http.get 完全一致：resolve 时返回 AxiosResponse，调用方用 .data 取值。

// 基础字典数据不常变，缓存期放宽到 5 分钟，减少重复请求
const TTL_MS = 5 * 60 * 1000

interface CacheEntry {
  data: unknown
  expiresAt: number
}

const cache = new Map<string, CacheEntry>()
const inflight = new Map<string, Promise<AxiosResponse>>()

function keyOf(method: string, url: string, params?: Record<string, unknown>) {
  return `${method} ${url} ${JSON.stringify(params || {})}`
}

function makeResponse(data: unknown): AxiosResponse {
  return { data, status: 200, statusText: "OK", headers: {}, config: {} } as AxiosResponse
}

/**
 * 带 TTL 缓存的 GET 请求，返回 AxiosResponse（调用方用 .data 取值）。
 * @param url  请求路径（相对 baseURL）
 * @param params 查询参数
 * @param force 为 true 时跳过缓存强制刷新
 */
export function dictGet<T = unknown>(url: string, params?: Record<string, unknown>, force = false): Promise<AxiosResponse<T>> {
  const key = keyOf("GET", url, params)

  if (!force) {
    const hit = cache.get(key)
    if (hit && hit.expiresAt > Date.now()) {
      return Promise.resolve(makeResponse(hit.data) as AxiosResponse<T>)
    }
  }

  const pending = inflight.get(key)
  if (pending) return pending as Promise<AxiosResponse<T>>

  const task = http
    .get<T>(url, { params })
    .then((resp) => {
      cache.set(key, { data: resp.data, expiresAt: Date.now() + TTL_MS })
      return resp
    })
    .finally(() => {
      inflight.delete(key)
    })

  inflight.set(key, task)
  return task
}

/** 清空全部字典缓存（在新增/删除基础数据后可调用，保证下次读取最新） */
/**
 * 登录后预热基础字典数据缓存：提前拉取设备类型、数据中心、机房、机柜，
 * 让用户进入各功能页时直接用缓存，省去每个页面首次的下拉请求。
 * 失败静默忽略（不影响登录/页面正常加载）。
 */
export function prefetchDict() {
  const points: Array<[string, Record<string, unknown> | undefined]> = [
    ["/devices/types/all", undefined],
    ["/facilities/data-centers/all", undefined],
    ["/facilities/rooms/all", { data_center_id: undefined }],
    ["/facilities/racks/all", { room_id: undefined }],
  ]
  points.forEach(([url, params]) => {
    dictGet(url, params).catch(() => { /* 预热失败不阻塞 */ })
  })
}

export function clearDictCache() {
  cache.clear()
}