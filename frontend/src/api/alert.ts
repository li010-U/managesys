/* ===== 告警管理 API ===== */
import http from "./index"

// ============ 告警规则 ============
export interface AlertCondition {
  metric: string
  condition: string  // gt, lt, eq, gte, lte, neq
  threshold: number
  threshold_value?: number  // for between conditions
}

export interface AlertEscalation {
  enabled: boolean
  timeout_minutes: number  // 超时多少分钟触发升级
  escalate_to_level: string  // 升级到哪个级别
  escalate_to_role?: number  // 升级给哪个角色
  notify_once: boolean  // 是否只通知一次
}

export interface AlertRuleInfo {
  id: number
  name: string
  code: string
  metric: string
  condition: string
  threshold: number
  threshold_value?: number  // for between conditions
  alert_level: string  // general, serious, emergency
  enabled: boolean
  // 高级配置
  conditions?: AlertCondition[]  // 复合条件
  condition_logic?: "and" | "or"  // 条件逻辑关系
  escalation?: AlertEscalation  // 升级规则
  // 通知配置
  notify_methods: string[]  // ["email", "sms", "webhook"]
  notify_targets?: string[]  // 通知目标
  notify_template?: string  // 通知模板
  // 抑制配置
  suppress_enabled: boolean  // 是否启用抑制
  suppress_minutes: number  // 抑制时间（分钟）
  // 统计
  alert_count: number
  trigger_count: number  // 累计触发次数
  last_triggered_at?: string
  created_at: string
  updated_at: string
}

export interface AlertRulePage {
  items: AlertRuleInfo[]
  total: number
  page: number
  page_size: number
}

export function getAlertRulesApi(params: {
  page: number
  page_size: number
  keyword?: string
  enabled?: boolean
  alert_level?: string
}) {
  return http.get<AlertRulePage>("/alerts/rules", { params })
}

export function getAllAlertRulesApi() {
  return http.get<AlertRuleInfo[]>("/alerts/rules/all")
}

export function createAlertRuleApi(data: any) {
  return http.post<AlertRuleInfo>("/alerts/rules", data)
}

export function updateAlertRuleApi(id: number, data: any) {
  return http.put<AlertRuleInfo>(`/alerts/rules/${id}`, data)
}

export function deleteAlertRuleApi(id: number) {
  return http.delete(`/alerts/rules/${id}`)
}

export function toggleAlertRuleApi(id: number) {
  return http.post(`/alerts/rules/${id}/toggle`)
}

// ============ 告警记录 ============
export interface AlertInfo {
  id: number
  alert_rule_id: number | null
  device_id: number | null
  target_type: string
  target_id: string
  title: string
  description: string | null
  level: string
  status: string  // new, acknowledged, resolved, ignored, escalated
  source: string
  rule_name: string | null
  device_name: string | null
  // 升级相关
  escalated_from_id?: number
  escalated_at?: string
  escalation_level?: string
  // 处理信息
  handler?: string
  handled_at?: string
  remark?: string
  root_cause?: string
  // 时间
  created_at: string
  updated_at: string
}

export interface AlertPage {
  items: AlertInfo[]
  total: number
  page: number
  page_size: number
}

export function getAlertsApi(params: {
  page: number
  page_size: number
  keyword?: string
  level?: string
  status?: string
  target_type?: string
  start_date?: string
  end_date?: string
}) {
  return http.get<AlertPage>("/alerts", { params })
}

export function getAlertApi(id: number) {
  return http.get<AlertInfo>(`/alerts/${id}`)
}

export function handleAlertApi(id: number, data: {
  action_type: string
  operator?: string
  remark?: string
  root_cause?: string
}) {
  return http.put(`/alerts/${id}/handle`, data)
}

export function batchHandleAlertsApi(ids: number[], data: {
  action_type: string
  operator?: string
  remark?: string
}) {
  return http.put("/alerts/batch-handle", { ids, ...data })
}

export function acknowledgeAlertApi(id: number, remark?: string) {
  return http.post(`/alerts/${id}/acknowledge`, { remark })
}

export function resolveAlertApi(id: number, data: {
  remark?: string
  root_cause?: string
}) {
  return http.post(`/alerts/${id}/resolve`, data)
}

// ============ 告警统计 ============
export interface AlertStats {
  total: number
  new: number
  acknowledged: number
  resolved: number
  ignored: number
  escalated: number
  // 按级别统计
  by_level: {
    general: number
    serious: number
    emergency: number
  }
  // 按类型统计
  by_type: {
    [key: string]: number
  }
}

export interface AlertTrendItem {
  date: string
  count: number
  resolved: number
}

export interface AlertLevelDistribution {
  level: string
  count: number
  percentage: number
}

export function getAlertStatsApi() {
  return http.get<AlertStats>("/alerts/stats")
}

export function getAlertTrendApi(params: {
  start_date: string
  end_date: string
  group_by?: "day" | "week" | "month"
}) {
  return http.get<AlertTrendItem[]>("/alerts/stats/trend", { params })
}

export function getAlertLevelDistributionApi() {
  return http.get<AlertLevelDistribution[]>("/alerts/stats/level-distribution")
}

export function getAlertSourceDistributionApi() {
  return http.get<{ source: string; count: number }[]>("/alerts/stats/source-distribution")
}

// ============ 通知配置 ============
export interface NotifyTemplateInfo {
  id: number
  name: string
  code: string
  type: string  // email, sms, webhook
  subject?: string  // for email
  content: string
  variables?: string[]  // 可用变量
  enabled: boolean
  created_at: string
}

export function getNotifyTemplatesApi() {
  return http.get<NotifyTemplateInfo[]>("/alerts/notify-templates")
}

export function createNotifyTemplateApi(data: any) {
  return http.post<NotifyTemplateInfo>("/alerts/notify-templates", data)
}

export function updateNotifyTemplateApi(id: number, data: any) {
  return http.put<NotifyTemplateInfo>(`/alerts/notify-templates/${id}`, data)
}

// ============ 业务系统管理 API ========
export interface BizSystemInfo {
  id: number
  name: string
  code: string
  category: string
  access_url: string | null
  admin_name: string | null
  admin_phone: string | null
  admin_email: string | null
  remark: string | null
  status: string
  device_count: number
  doc_count: number
  created_at: string
  updated_at: string
}

export interface BizSystemPage {
  items: BizSystemInfo[]
  total: number
  page: number
  page_size: number
}

export function getBizSystemsApi(params: {
  page: number
  page_size: number
  keyword?: string
  category?: string
  status?: string
}) {
  return http.get<BizSystemPage>("/systems", { params })
}

export function getBizSystemApi(id: number) {
  return http.get<BizSystemInfo>(`/systems/${id}`)
}

export function createBizSystemApi(data: any) {
  return http.post<BizSystemInfo>("/systems", data)
}

export function updateBizSystemApi(id: number, data: any) {
  return http.put<BizSystemInfo>(`/systems/${id}`, data)
}

export function deleteBizSystemApi(id: number) {
  return http.delete(`/systems/${id}`)
}

export interface DeploymentInfo {
  id: number
  system_id: number
  device_id: number
  service_port: string | null
  process_name: string | null
  system_version: string | null
  middleware_version: string | null
  device_name: string | null
  created_at: string
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