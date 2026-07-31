/* ===== 告警管理 API ===== */
import http from './index'

export interface AlertRuleInfo {
  id: number; name: string; code: string; metric: string; condition: string
  threshold: number; alert_level: string; enabled: boolean; notify_methods: any; alert_count: number
  created_at: string; updated_at: string
}
export interface AlertRulePage { items: AlertRuleInfo[]; total: number; page: number; page_size: number }

export function getAlertRulesApi(params: { page: number; page_size: number; keyword?: string; enabled?: boolean }) {
  return http.get<AlertRulePage>('/alerts/rules', { params })
}
export function createAlertRuleApi(data: any) {
  return http.post<AlertRuleInfo>('/alerts/rules', data)
}
export function updateAlertRuleApi(id: number, data: any) {
  return http.put<AlertRuleInfo>(`/alerts/rules/${id}`, data)
}
export function deleteAlertRuleApi(id: number) {
  return http.delete(`/alerts/rules/${id}`)
}

export interface AlertInfo {
  id: number; alert_rule_id: number | null; device_id: number | null
  target_type: string; target_id: string; title: string; description: string | null
  level: string; status: string; source: string; rule_name: string | null
  device_name: string | null; created_at: string
}
export interface AlertPage { items: AlertInfo[]; total: number; page: number; page_size: number }

export function getAlertsApi(params: { page: number; page_size: number; keyword?: string; level?: string; status?: string; target_type?: string }) {
  return http.get<AlertPage>('/alerts', { params })
}
export function getAlertStatsApi() {
  return http.get<{total:number;new:number;acknowledged:number;resolved:number;ignored:number}>('/alerts/stats')
}
export function handleAlertApi(id: number, data: { action_type: string; operator?: string; remark?: string; root_cause?: string }) {
  return http.put(`/alerts/${id}/handle`, data)
}

/* ===== 业务系统管理 API ===== */
export interface BizSystemInfo {
  id: number; name: string; code: string; category: string; access_url: string | null
  admin_name: string | null; admin_phone: string | null; admin_email: string | null
  remark: string | null; status: string; device_count: number; doc_count: number
  created_at: string; updated_at: string
}
export interface BizSystemPage { items: BizSystemInfo[]; total: number; page: number; page_size: number }

export function getBizSystemsApi(params: { page: number; page_size: number; keyword?: string; category?: string; status?: string }) {
  return http.get<BizSystemPage>('/systems', { params })
}
export function getBizSystemApi(id: number) {
  return http.get<BizSystemInfo>(`/systems/${id}`)
}
export function createBizSystemApi(data: any) {
  return http.post<BizSystemInfo>('/systems', data)
}
export function updateBizSystemApi(id: number, data: any) {
  return http.put<BizSystemInfo>(`/systems/${id}`, data)
}
export function deleteBizSystemApi(id: number) {
  return http.delete(`/systems/${id}`)
}

export interface DeploymentInfo {
  id: number; system_id: number; device_id: number; service_port: string | null
  process_name: string | null; system_version: string | null; middleware_version: string | null
  device_name: string | null; created_at: string
}

export function getDeploymentsApi(systemId: number) {
  return http.get<DeploymentInfo[]>(`/systems/${systemId}/deployments`)
}
export function createDeploymentApi(systemId: number, data: any) {
  return http.post<DeploymentInfo>(`/systems/${systemId}/deployments`, data)
}
export function deleteDeploymentApi(systemId: number, depId: number) {
  return http.delete(`/systems/${systemId}/deployments/${depId}`)
}
