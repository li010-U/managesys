import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

// 用 vi.hoisted 让 mock 工厂能引用 spy（vitest 会提升 vi.mock）
const { errorSpy, routerPush } = vi.hoisted(() => ({
  errorSpy: vi.fn(),
  routerPush: vi.fn(),
}))

// 拦截 element-plus 的消息弹窗与 vue-router，避免真实副作用
vi.mock('element-plus', () => ({
  ElMessage: { error: (...args: unknown[]) => errorSpy(...args) },
}))

vi.mock('../router', () => ({
  default: { push: routerPush },
}))

// node 环境无 window/localStorage，这里补一个最小桩，满足模块执行
if (typeof (globalThis as any).localStorage === 'undefined') {
  const store = new Map<string, string>()
  ;(globalThis as any).localStorage = {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, v) },
    removeItem: (k: string) => { store.delete(k) },
  }
}

import http from './index'

type Resp = { status: number; data: any }

/**
 * 通过自定义 adapter 触发 http 实例的响应错误拦截器，
 * 捕获其到底调用 ElMessage.error 的哪一句文案。
 */
async function fireError(opts: { code?: string; message?: string; resp?: Resp }) {
  const config: any = { url: '/test', method: 'get' }
  const adapter = async () => {
    const err = new axios.AxiosError(
      opts.message ?? 'Request failed',
      opts.code ?? 'ERR_BAD_RESPONSE',
      config,
      {},
      opts.resp ? { status: opts.resp.status, data: opts.resp.data, statusText: '', headers: {}, config } : undefined,
    )
    throw err
  }
  try {
    await http.get('/test', { adapter } as any)
  } catch {
    // 拦截器 reject 属预期
  }
}

beforeEach(() => {
  errorSpy.mockClear()
  routerPush.mockClear()
  ;(globalThis as any).localStorage.removeItem('access_token')
  ;(globalThis as any).localStorage.removeItem('refresh_token')
})

describe('API 响应错误提示逻辑（回归防护）', () => {
  it('5xx -> 提示“服务器繁忙，请稍后重试”，不误报网络错误', async () => {
    await fireError({ resp: { status: 500, data: { detail: null } } })
    expect(errorSpy).toHaveBeenCalledTimes(1)
    expect(errorSpy.mock.calls[0][0]).toBe('服务器繁忙，请稍后重试')
  })

  it('5xx 优先用后端 detail', async () => {
    await fireError({ resp: { status: 502, data: { detail: '网关错误' } } })
    expect(errorSpy.mock.calls[0][0]).toBe('网关错误')
  })

  it('403 -> 权限不足；404 -> 资源不存在', async () => {
    await fireError({ resp: { status: 403, data: {} } })
    expect(errorSpy.mock.calls[0][0]).toBe('权限不足')
    await fireError({ resp: { status: 404, data: {} } })
    expect(errorSpy.mock.calls[1][0]).toBe('资源不存在')
  })

  it('其余 4xx（如 400）-> 请求失败', async () => {
    await fireError({ resp: { status: 400, data: {} } })
    expect(errorSpy.mock.calls[0][0]).toBe('请求失败')
  })

  it('无响应 + 超时（ECONNABORTED/timeout）-> 请求超时，而非网络错误', async () => {
    await fireError({ code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
    expect(errorSpy.mock.calls[0][0]).toBe('请求超时，请稍后重试')
  })

  it('无响应 + 非超时（ERR_NETWORK）-> 网络错误，请检查连接', async () => {
    await fireError({ code: 'ERR_NETWORK', message: 'Network Error' })
    expect(errorSpy.mock.calls[0][0]).toBe('网络错误，请检查连接')
  })

  it('401 且无可用 refresh token -> 清除登录态并跳登录页', async () => {
    await fireError({ resp: { status: 401, data: {} } })
    expect(routerPush).toHaveBeenCalledWith('/login')
    expect(errorSpy.mock.calls[0][0]).toBe('登录已过期，请重新登录')
  })
})
