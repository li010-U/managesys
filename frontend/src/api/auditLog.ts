import http from './index'

export interface AuditLogResponse {
  id: number
  user_id?: number
  username: string
  action: string
  target_type: string
  target_id?: string
  detail?: string
  ip_address?: string
  created_at: string
}

export interface AuditLogPageResponse {
  items: AuditLogResponse[]
  total: number
  page: number
  page_size: number
}

export interface AuditLogQuery {
  page?: number
  page_size?: number
  keyword?: string
  action?: string
  target_type?: string
  start_date?: string
  end_date?: string
}

/** 获取审计日志列表 */
export function getAuditLogsApi(params: AuditLogQuery) {
  return http.get<AuditLogPageResponse>('/audit-logs', { params })
}

/** 获取审计日志详情 */
export function getAuditLogApi(id: number) {
  return http.get<AuditLogResponse>(`/audit-logs/${id}`)
}
