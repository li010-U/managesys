import http from './index'

export interface PermissionInfo {
  id: number
  name: string
  code: string
  module: string
}

export interface RoleInfo {
  id: number
  name: string
  code: string
  description?: string
  is_builtin: boolean
  created_at: string
  updated_at: string
  permissions: PermissionInfo[]
}

/** 获取角色列表 */
export function getRolesApi() {
  return http.get<RoleInfo[]>('/roles')
}

/** 获取角色详情 */
export function getRoleApi(id: number) {
  return http.get<RoleInfo>(`/roles/${id}`)
}

/** 创建角色 */
export function createRoleApi(data: { name: string; code: string; description?: string; permissions?: number[] }) {
  return http.post<RoleInfo>('/roles', data)
}

/** 更新角色 */
export function updateRoleApi(id: number, data: { name?: string; description?: string; permissions?: number[] }) {
  return http.put<RoleInfo>(`/roles/${id}`, data)
}

/** 删除角色 */
export function deleteRoleApi(id: number) {
  return http.delete(`/roles/${id}`)
}

/** 获取权限列表 */
export function getPermissionsApi() {
  return http.get<PermissionInfo[]>('/roles/permissions/list')
}
