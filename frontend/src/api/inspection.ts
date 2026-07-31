import http from "./index"

// ============ 巡检模板 ============
export const getInspectionTemplates = (deviceTypeId?: number) => {
  return http.get("/inspection/templates", { params: { device_type_id: deviceTypeId } })
}

export const createInspectionTemplate = (data: any) => {
  return http.post("/inspection/templates", data)
}

export const updateInspectionTemplate = (id: number, data: any) => {
  return http.put(`/inspection/templates/${id}`, data)
}

export const deleteInspectionTemplate = (id: number) => {
  return http.delete(`/inspection/templates/${id}`)
}

// ============ 巡检计划 ============
export const getInspectionPlans = (params?: any) => {
  return http.get("/inspection/plans", { params })
}

export const createInspectionPlan = (data: any) => {
  return http.post("/inspection/plans", data)
}

export const updateInspectionPlan = (id: number, data: any) => {
  return http.put(`/inspection/plans/${id}`, data)
}

export const deleteInspectionPlan = (id: number) => {
  return http.delete(`/inspection/plans/${id}`)
}

// ============ 巡检任务 ============
export const getInspectionTasks = (params?: any) => {
  return http.get("/inspection/tasks", { params })
}

export const getInspectionTaskDetail = (id: number) => {
  return http.get(`/inspection/tasks/${id}`)
}

export const createInspectionTask = (data: { plan_id: number; facility_id?: number; scheduled_date?: string }) => {
  return http.post("/inspection/tasks", null, { params: data })
}

export const startInspectionTask = (id: number) => {
  return http.post(`/inspection/tasks/${id}/start`)
}

export const completeInspectionTask = (id: number) => {
  return http.post(`/inspection/tasks/${id}/complete`)
}

// ============ 巡检记录 ============
export const addInspectionRecord = (taskId: number, data: any) => {
  return http.post(`/inspection/tasks/${taskId}/records`, data)
}

export const updateInspectionRecord = (id: number, data: any) => {
  return http.put(`/inspection/records/${id}`, data)
}

// ============ 巡检问题 ============
export const getInspectionIssues = (params?: any) => {
  return http.get("/inspection/issues", { params })
}

export const getInspectionIssueDetail = (id: number) => {
  return http.get(`/inspection/issues/${id}`)
}

export const createInspectionIssue = (taskId: number, data: any) => {
  return http.post("/inspection/issues", data, { params: { task_id: taskId } })
}

export const updateInspectionIssue = (id: number, data: any) => {
  return http.put(`/inspection/issues/${id}`, data)
}

// ============ 统计 ============
export const getInspectionStats = () => {
  return http.get("/inspection/stats")
}

export const generateInspectionTasks = () => {
  return http.post("/inspection/generate-tasks")
}