import request from '@/utils/request'

// ============ 巡检模板 ============
export const getInspectionTemplates = (deviceTypeId?: number) => {
  return request.get('/inspection/templates', { params: { device_type_id: deviceTypeId } })
}

export const createInspectionTemplate = (data: any) => {
  return request.post('/inspection/templates', data)
}

export const updateInspectionTemplate = (id: number, data: any) => {
  return request.put(\/inspection/templates/\\, data)
}

export const deleteInspectionTemplate = (id: number) => {
  return request.delete(\/inspection/templates/\\)
}

// ============ 巡检计划 ============
export const getInspectionPlans = (params?: any) => {
  return request.get('/inspection/plans', { params })
}

export const createInspectionPlan = (data: any) => {
  return request.post('/inspection/plans', data)
}

export const updateInspectionPlan = (id: number, data: any) => {
  return request.put(\/inspection/plans/\\, data)
}

export const deleteInspectionPlan = (id: number) => {
  return request.delete(\/inspection/plans/\\)
}

// ============ 巡检任务 ============
export const getInspectionTasks = (params?: any) => {
  return request.get('/inspection/tasks', { params })
}

export const getInspectionTaskDetail = (id: number) => {
  return request.get(\/inspection/tasks/\\)
}

export const createInspectionTask = (data: { plan_id: number; facility_id?: number; scheduled_date?: string }) => {
  return request.post('/inspection/tasks', null, { params: data })
}

export const startInspectionTask = (id: number) => {
  return request.post(\/inspection/tasks/\/start\)
}

export const completeInspectionTask = (id: number) => {
  return request.post(\/inspection/tasks/\/complete\)
}

// ============ 巡检记录 ============
export const addInspectionRecord = (taskId: number, data: any) => {
  return request.post(\/inspection/tasks/\/records\, data)
}

export const updateInspectionRecord = (id: number, data: any) => {
  return request.put(\/inspection/records/\\, data)
}

// ============ 巡检问题 ============
export const getInspectionIssues = (params?: any) => {
  return request.get('/inspection/issues', { params })
}

export const getInspectionIssueDetail = (id: number) => {
  return request.get(\/inspection/issues/\\)
}

export const createInspectionIssue = (taskId: number, data: any) => {
  return request.post(\/inspection/issues\, data, { params: { task_id: taskId } })
}

export const updateInspectionIssue = (id: number, data: any) => {
  return request.put(\/inspection/issues/\\, data)
}

// ============ 统计 ============
export const getInspectionStats = () => {
  return request.get('/inspection/stats')
}

export const generateInspectionTasks = () => {
  return request.post('/inspection/generate-tasks')
}
