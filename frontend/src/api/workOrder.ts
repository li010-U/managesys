import http from "./index"

// ============ 工单分类 ============
export interface WorkOrderCategory {
  id: number
  name: string
  code: string
  description?: string
  sla_hours: number  // SLA时限（小时）
  enabled: boolean
}

export function getWorkOrderCategories() {
  return http.get<WorkOrderCategory[]>("/work-orders/categories")
}

export function createWorkOrderCategory(data: any) {
  return http.post("/work-orders/categories", data)
}

export function updateWorkOrderCategory(id: number, data: any) {
  return http.put(`/work-orders/categories/${id}`, data)
}

export function deleteWorkOrderCategory(id: number) {
  return http.delete(`/work-orders/categories/${id}`)
}

// ============ 工单 ============
export type WorkOrderStatus = "pending" | "assigned" | "processing" | "pending_verify" | "completed" | "closed" | "rejected"
export type WorkOrderPriority = "low" | "normal" | "high" | "urgent"

export interface WorkOrderInfo {
  id: number
  order_no: string
  title: string
  description?: string
  category_id: number
  category_name: string
  priority: WorkOrderPriority
  status: WorkOrderStatus
  creator_id: number
  creator_name: string
  assignee_id?: number
  assignee_name?: string
  device_id?: number
  device_name?: string
  facility_id?: number
  plan_date?: string
  due_date?: string  // 截止日期
  actual_hours?: number  // 实际耗时
  // SLA相关
  sla_hours?: number  // SLA时限
  sla_status?: "normal" | "warning" | "overdue"  // SLA状态
  sla_remaining_hours?: number  // 剩余时间（小时）
  // 评价
  satisfaction?: number  // 满意度评分 1-5
  feedback?: string  // 反馈内容
  // 时间
  created_at: string
  updated_at: string
  completed_at?: string
  closed_at?: string
}

export interface WorkOrderPage {
  items: WorkOrderInfo[]
  total: number
  page: number
  page_size: number
}

export function getWorkOrders(params: {
  page: number
  page_size: number
  status?: string
  priority?: string
  keyword?: string
  assignee_id?: number
  category_id?: number
  start_date?: string
  end_date?: string
}) {
  return http.get<WorkOrderPage>("/work-orders", { params })
}

export function getWorkOrderApi(id: number) {
  return http.get<WorkOrderInfo>(`/work-orders/${id}`)
}

export function createWorkOrder(data: any) {
  return http.post<WorkOrderInfo>("/work-orders", data)
}

export function updateWorkOrder(id: number, data: any) {
  return http.put<WorkOrderInfo>(`/work-orders/${id}`, data)
}

export function deleteWorkOrder(id: number) {
  return http.delete(`/work-orders/${id}`)
}

// ============ 工单操作 ============
// 分配
export function assignWorkOrder(id: number, data: { assignee_id: number; remark?: string }) {
  return http.post(`/work-orders/${id}/assign`, data)
}

// 开始处理
export function startWorkOrder(id: number) {
  return http.post(`/work-orders/${id}/start`)
}

// 完成处理
export function completeWorkOrder(id: number, data: { result: string; actual_hours?: number }) {
  return http.post(`/work-orders/${id}/complete`, data)
}

// 验收
export function verifyWorkOrder(id: number, data: { accept: boolean; satisfaction?: number; feedback?: string }) {
  return http.post(`/work-orders/${id}/verify`, data)
}

// 关闭
export function closeWorkOrder(id: number, data: { remark?: string }) {
  return http.post(`/work-orders/${id}/close`, data)
}

// 驳回
export function rejectWorkOrder(id: number, data: { reason: string }) {
  return http.post(`/work-orders/${id}/reject`, data)
}

// 撤回
export function withdrawWorkOrder(id: number, data: { reason?: string }) {
  return http.post(`/work-orders/${id}/withdraw`, data)
}

// ============ 工单消息 ============
export interface WorkOrderComment {
  id: number
  work_order_id: number
  user_id: number
  user_name: string
  content: string
  comment_type: "normal" | "system" | "internal"
  created_at: string
}

export function getWorkOrderMessages(orderId: number) {
  return http.get<WorkOrderComment[]>(`/work-orders/${orderId}/messages`)
}

export function addWorkOrderComment(orderId: number, data: { content: string; comment_type?: string }) {
  return http.post<WorkOrderComment>(`/work-orders/${orderId}/messages`, data)
}

// ============ 工单统计 ============
export interface WorkOrderStats {
  total: number
  pending: number
  processing: number
  completed: number
  closed: number
  my_pending: number
  my_processing: number
  // SLA统计
  sla_warning: number  // SLA预警
  sla_overdue: number  // SLA超时
  // 评价统计
  avg_satisfaction: number  // 平均满意度
  satisfaction_distribution: { [key: number]: number }  // 各评分数量
  // 趋势
  daily_stats: { date: string; created: number; completed: number }[]
}

export function getWorkOrderStats() {
  return http.get<WorkOrderStats>("/work-orders/stats")
}

export function getWorkOrderTrend(params: { start_date: string; end_date: string }) {
  return http.get<{ date: string; created: number; completed: number }[]>("/work-orders/stats/trend", { params })
}

// ============ 分类管理 ============
export function getAssignableUsers() {
  return http.get<{ id: number; username: string; real_name?: string }[]>("/work-orders/assignable-users")
}