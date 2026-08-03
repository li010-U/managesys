import http from './index'

export interface UserInfo {
  id: number
  username: string
  real_name?: string
  email?: string
  phone?: string
  department?: string
  position?: string
  is_active: boolean
  is_super_admin: boolean
  _loading?: boolean
  last_login?: string
  created_at: string
  updated_at: string
  roles: Array<{ id: number; name: string; code: string; permission_codes: string[] }>
}

export interface UserPageResponse {
  items: UserInfo[]
  total: number
  page: number
  page_size: number
}

export interface UserCreateRequest {
  username: string
  password: string
  real_name?: string
  email?: string
  phone?: string
  department?: string
  position?: string
  is_active?: boolean
  roles?: number[]
}

export interface UserUpdateRequest {
  real_name?: string
  email?: string
  phone?: string
  department?: string
  position?: string
  is_active?: boolean
  roles?: number[]
}

/** 获取用户列表 */
export function getUsersApi(params: { page: number; page_size: number; keyword?: string }) {
  return http.get<UserPageResponse>('/users', { params })
}

/** 获取用户详情 */
export function getUserApi(id: number) {
  return http.get<UserInfo>(`/users/${id}`)
}

/** 创建用户 */
export function createUserApi(data: UserCreateRequest) {
  return http.post<UserInfo>('/users', data)
}

/** 更新用户 */
export function updateUserApi(id: number, data: UserUpdateRequest) {
  return http.put<UserInfo>(`/users/${id}`, data)
}

/** 删除用户 */
export function deleteUserApi(id: number) {
  return http.delete(`/users/${id}`)
}

