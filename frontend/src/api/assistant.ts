import http from "./index"

export interface AlertStats {
  total: number
  new: number
  acknowledged: number
  resolved: number
  ignored: number
}

export interface Reminder {
  type: string
  level: "info" | "warning" | "danger"
  title: string
  content: string
}

export interface Advisor {
  status: "healthy" | "attention" | "alert"
  mood: string
  summary: string
  metrics: Record<string, number>
}

export interface AssistantSnapshot {
  timestamp: string
  alert_stats: AlertStats
  sensor: {
    total: number
    online: number
    offline: number
    abnormal: number
    abnormal_items: Array<{
      id: number
      name: string
      room_id: number
      sensor_type: string
      sensor_type_name: string
      current_value: string | null
      threshold_min: number | null
      threshold_max: number | null
    }>
  }
  rack: {
    total: number
    used_units: number
    capacity_units: number
    avg_usage: number
  }
  device_count: number
  room_count: number
  latest_alerts: Array<{
    id: number
    title: string
    level: string
    status: string
    target_type: string
    created_at: string
  }>
  high_usage_racks: Array<{ id: number; code: string; name: string; usage: number; room_id: number }>
}

export interface AssistantPayload {
  seq: number
  snapshot: AssistantSnapshot
  reminders: Reminder[]
  advisor: Advisor
}

export function getAssistantSnapshotApi() {
  return http.get<AssistantPayload>("/assistant/snapshot")
}
