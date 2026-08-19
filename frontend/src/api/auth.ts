import http from './index'

export interface LoginRequest {
  username: string
  password: string
  captcha_id?: string
  captcha_code?: string
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type: string
  expires_in?: number
}

export interface RegisterRequest {
  username: string
  password: string
  real_name?: string
  email?: string
  phone?: string
  department?: string
}

export interface CaptchaResponse {
  captcha_id: string
  captcha_image: string
}

export interface LoginLogItem {
  id: number
  username: string
  ip_address: string | null
  location?: string | null
  anomaly?: string[] | null
  login_status: string
  fail_reason: string | null
  created_at: string
}

/** 登录 */
export function loginApi(data: LoginRequest) {
  return http.post<TokenResponse>('/auth/login', data)
}

/** 注册 */
export function registerApi(data: RegisterRequest) {
  return http.post('/auth/register', data)
}

/** 修改密码 */
export function changePasswordApi(data: { old_password: string; new_password: string }) {
  return http.post('/auth/change-password', data)
}

/** 退出登录 */
export function logoutApi() {
  return http.post('/auth/logout')
}

/** 刷新令牌 */
export function refreshApi(refresh_token: string) {
  return http.post<TokenResponse>('/auth/refresh', { refresh_token })
}

/** 获取当前用户信息 */
export function getCurrentUserApi() {
  return http.get('/auth/me')
}

/** 获取验证码 */
export function getCaptchaApi() {
  return http.get<CaptchaResponse>('/auth/captcha')
}

/** 获取登录日志 */
export function getLoginLogsApi() {
  return http.get<LoginLogItem[]>('/auth/login-logs')
}
