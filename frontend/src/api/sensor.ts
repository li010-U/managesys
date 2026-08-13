import http from "./index"

/* ===== Sensor ===== */
export interface SensorInfo {
  id: number; room_id: number
  name: string; code: string; sensor_type: string
  install_position?: string; status: string
  current_value?: { value: number; unit: string } | null
  last_update_time?: string | null
  threshold_min?: number | null; threshold_max?: number | null
  alert_level: string
  room_name: string
  created_at: string; updated_at: string
}
export interface SensorPage { items: SensorInfo[]; total: number; page: number; page_size: number }
export interface SensorDataInfo {
  id: number; sensor_id: number; value: number; recorded_at: string
}

export function getSensorsApi(params: { page: number; page_size: number; room_id?: number; sensor_type?: string; keyword?: string }) {
  return http.get<SensorPage>("/sensors", { params })
}
export function getAllSensorsApi(params?: { room_id?: number }) {
  return http.get<SensorInfo[]>("/sensors/all", { params })
}
export function getSensorApi(id: number) {
  return http.get<SensorInfo>("/sensors/" + id)
}
export function createSensorApi(data: any) {
  return http.post<SensorInfo>("/sensors", data)
}
export function updateSensorApi(id: number, data: any) {
  return http.put<SensorInfo>("/sensors/" + id, data)
}
export function deleteSensorApi(id: number) {
  return http.delete("/sensors/" + id)
}
export function getSensorDataApi(id: number, limit?: number) {
  return http.get<SensorDataInfo[]>("/sensors/" + id + "/data", { params: { limit: limit || 20 } })
}
export function recordSensorDataApi(id: number, value: number) {
  return http.post<SensorDataInfo>("/sensors/" + id + "/data?value=" + value)
}

/* ===== 数据保留与异常留痕 ===== */
export interface RetentionStatus {
  retention_days: number
  buffer_days: number
  task_enabled: boolean
  cutoff?: string | null
  sensor_data_count: number
  sensor_data_oldest?: string | null
  sensor_data_newest?: string | null
  anomaly_gap_count: number
  anomaly_gap_oldest?: string | null
  anomaly_gap_newest?: string | null
}
export interface AnomalyGapInfo {
  id: number; sensor_id: number; sensor_name?: string | null
  alert_id?: number | null; detected_at: string
  window_start?: string | null; window_end?: string | null
  anomaly_type: string; severity: string; remark?: string | null
  created_at: string
}
export function getRetentionStatusApi() {
  return http.get<RetentionStatus>("/sensors/retention-status")
}
export function getAnomalyGapsApi(params?: { sensor_id?: number; limit?: number }) {
  return http.get<AnomalyGapInfo[]>("/sensors/anomaly-gaps", { params })
}
