import http from "./index"

/* ===== 自学习基线 ===== */
export interface BaselineSlot {
  hour: number; count: number
  mean: number; median: number; min: number; max: number
  low: number | null; high: number | null
}
export interface BaselineResult {
  found: boolean
  sensor_id: number
  sensor_name?: string
  sensor_type?: string
  samples?: number
  lookback_days?: number
  overall_mean?: number | null
  current_value?: number | null
  baseline?: Record<string, BaselineSlot> | null
  assessment?: { status: string; msg: string } | null
}
export function getSensorBaselineApi(sensorId: number, lookbackDays = 30) {
  return http.get<BaselineResult>(`/insight/baseline/${sensorId}`, { params: { lookback_days: lookbackDays } })
}

/* ===== 趋势预测 ===== */
export interface ForecastPoint { value: number; low: number; high: number }
export interface ForecastResult {
  found: boolean
  sensor_id: number
  sensor_name?: string
  sensor_type?: string
  samples?: number
  history?: { value: number; ts: string }[]
  forecast?: ForecastPoint[] | null
  direction?: "up" | "down" | "flat"
}
export function getSensorForecastApi(sensorId: number, lookback = 120, horizon = 6) {
  return http.get<ForecastResult>(`/insight/forecast/${sensorId}`, { params: { lookback, horizon } })
}

/* ===== 容量规划 ===== */
export interface RackCapacity {
  rack_id: number; rack_code: string; room_id: number; room_name?: string
  total_units: number; available_units: number; used_units: number
  utilization_pct: number; device_count: number
  power_used_kw: number; rated_power_kw: number; power_util_pct: number
  estimate_full_months: number | null; estimate_full_date: string | null
}
export interface CapacityResult { room_id: number | null; count: number; racks: RackCapacity[] }
export function getRackCapacityApi(roomId?: number) {
  return http.get<CapacityResult>("/insight/capacity", { params: { room_id: roomId } })
}

/* ===== 可靠性 ===== */
export interface ReliabilityResult {
  days: number; room_id?: number | null; alert_count: number
  emergency_count: number; serious_count: number
  avg_mttr_hours: number | null; availability_pct: number
  estimated_outage_hours: number
  top_failure_device_id?: string | null; top_failure_target_type?: string | null
  device_health: { device_id: string; device_name?: string; asset_number?: string; alert_count: number; mtbf_hours?: number | null }[]
  type_health: { target_type: string; alert_count: number; mtbf_hours?: number | null }[]
}
export function getReliabilityApi(roomId?: number, days = 90) {
  return http.get<ReliabilityResult>("/insight/reliability", { params: { room_id: roomId, days } })
}

/* ===== LLM 数据追溯 ===== */
export interface TraceResult {
  query: string; since?: string; matched: number
  alerts: {
    id: number; title?: string; description?: string; level: string; status: string
    target_type: string; source?: string; occurrences?: number | null
    created_at?: string; resolved_at?: string | null
  }[]
  top_recurrent_titles: { title: string; count: number }[]
  top_frequent_targets: { target: string; count: number }[]
}
export function getAlertTraceApi(q: string, limit = 20) {
  return http.get<TraceResult>("/insight/trace", { params: { q, limit } })
}

/* ===== 告警智能 ===== */
export function getCorrelateRoomApi(roomId: number) {
  return http.get<any>(`/insight/correlate/${roomId}`)
}
export function triggerAlertEscalateApi(minutes = 30) {
  return http.post<{ escalated_count: number; escalated_ids: number[] }>("/insight/alerts/escalate", undefined, { params: { minutes } })
}

/* ===== AI 巡检 ===== */
export interface InspectionChecklist {
  found: boolean
  room_id?: number; room_name?: string; room_code?: string
  days?: number; clue_count?: number
  checklist?: { type: string; priority: string; title: string; occurrences: number; source: string }[]
  generated_at?: string; llm_note?: string | null
}
export function getInspectionChecklistApi(roomId: number, days = 7, withLlm = false) {
  return http.get<InspectionChecklist>(`/insight/inspection/${roomId}`, { params: { days, with_llm: withLlm } })
}