import request from '@/utils/request'

// ============ 工单分类 ============
export const getWorkOrderCategories = () => {
  return request.get('/work-orders/categories')
}

export const createWorkOrderCategory = (data: any) => {
  return request.post('/work-orders/categories', data)
}

export const updateWorkOrderCategory = (id: number, data: any) => {
  return request.put(\/work-orders/categories/\\, data)
}

export const deleteWorkOrderCategory = (id: number) => {
  return request.delete(\/work-orders/categories/\\)
}

// ============ 工单 ============
export const getWorkOrders = (params?: any) => {
  return request.get('/work-orders', { params })
}

export const createWorkOrder = (data: any) => {
  return request.post('/work-orders', data)
}

export const updateWorkOrder = (id: number, data: any) => {
  return request.put(\/work-orders/\\, data)
}

export const deleteWorkOrder = (id: number) => {
  return request.delete(\/work-orders/\\)
}

// ============ 工单消息 ============
export const getWorkOrderMessages = (orderId: number) => {
  return request.get(\/work-orders/\/messages\)
}

export const addWorkOrderMessage = (orderId: number, data: any) => {
  return request.post(\/work-orders/\/messages\, data)
}

// ============ 工单处理 ============
export const handleWorkOrder = (id: number, data: any) => {
  return request.post(\/work-orders/\/handle\, data)
}

export const completeWorkOrder = (id: number, data: any) => {
  return request.post(\/work-orders/\/complete\, data)
}