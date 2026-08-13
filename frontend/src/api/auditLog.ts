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
  request_path?: string
  user_agent?: string
  created_at: string
}

export interface AuditLogPageResponse {
  items: AuditLogResponse[]
  total: number
  page: number
  page_size: number
}

export interface AuditCountItem {
  name: string
  count: number
}

export interface AuditTrendItem {
  date: string
  count: number
}

export interface AuditSummaryResponse {
  total: number
  by_action: AuditCountItem[]
  by_target: AuditCountItem[]
  by_user: AuditCountItem[]
  trend: AuditTrendItem[]
}

export interface AuditLogQuery {
  page?: number
  page_size?: number
  keyword?: string
  action?: string
  target_type?: string
  username?: string
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

/** 审计统计 */
export function getAuditSummaryApi(params: { days?: number; start_date?: string; end_date?: string }) {
  return http.get<AuditSummaryResponse>('/audit-logs/summary', { params })
}

/** 导出审计日志 CSV */
export function exportAuditLogsApi(params: AuditLogQuery) {
  return http.get('/audit-logs/export', { params, responseType: 'blob' })
}

/** 按保留策略清理历史审计日志 */
export function cleanupAuditLogsApi(days: number) {
  return http.delete('/audit-logs/retention', { params: { days } })
}
