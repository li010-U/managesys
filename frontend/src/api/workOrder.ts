import http from "./index"

// ============ 工单分类 ============
export const getWorkOrderCategories = () => {
  return http.get("/work-orders/categories")
}

export const createWorkOrderCategory = (data: any) => {
  return http.post("/work-orders/categories", data)
}

export const updateWorkOrderCategory = (id: number, data: any) => {
  return http.put(`/work-orders/categories/${id}`, data)
}

export const deleteWorkOrderCategory = (id: number) => {
  return http.delete(`/work-orders/categories/${id}`)
}

// ============ 工单 ============
export const getWorkOrders = (params?: any) => {
  return http.get("/work-orders", { params })
}

export const createWorkOrder = (data: any) => {
  return http.post("/work-orders", data)
}

export const updateWorkOrder = (id: number, data: any) => {
  return http.put(`/work-orders/${id}`, data)
}

export const deleteWorkOrder = (id: number) => {
  return http.delete(`/work-orders/${id}`)
}

// ============ 工单消息 ============
export const getWorkOrderMessages = (orderId: number) => {
  return http.get(`/work-orders/${orderId}/messages`)
}

export const addWorkOrderMessage = (orderId: number, data: any) => {
  return http.post(`/work-orders/${orderId}/messages`, data)
}

// ============ 工单处理 ============
export const handleWorkOrder = (id: number, data: any) => {
  return http.post(`/work-orders/${id}/handle`, data)
}

export const completeWorkOrder = (id: number, data: any) => {
  return http.post(`/work-orders/${id}/complete`, data)
}