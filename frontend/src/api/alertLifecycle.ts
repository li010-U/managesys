/* ===== 告警生命周期与环境关联统计 API ===== */
import http from './index'

export interface SignalResult {
  action: string
  alert_id?: number | null
  status?: string
  transient?: boolean
  duration_seconds?: number
  cooldown_until?: string | null
}

export function postAlertSignalApi(data: {
  target_type: string
  target_id: string
  is_abnormal: boolean
  title?: string
  level?: string
  device_id?: number | null
  metric?: string
  source?: string
  observed_at?: string | null
}) {
  return http.post<SignalResult>('/alert-lifecycle/signal', data)
}

export function runAlertSweepApi() {
  return http.post<{ resolved_count: number; resolved_ids: number[] }>('/alert-lifecycle/sweep')
}

export interface EnvWeatherInfo {
  id: number
  location_id: number | null
  location_name: string | null
  temperature: number | null
  humidity: number | null
  weather: string | null
  windspeed: number | null
  recorded_at: string
}

export function recordEnvApi(data: {
  temperature?: number | null
  humidity?: number | null
  weather?: string | null
  windspeed?: number | null
  location_id?: number | null
  location_name?: string | null
  recorded_at?: string | null
}) {
  return http.post<EnvWeatherInfo>('/alert-lifecycle/env', data)
}

export function getRecentEnvApi(limit = 20) {
  return http.get<EnvWeatherInfo[]>('/alert-lifecycle/env/recent', { params: { limit } })
}

export interface EnvTrendPoint {
  recorded_at: string
  temperature: number | null
  humidity: number | null
  windspeed: number | null
}

export function getEnvTrendApi(params: { hours?: number; limit?: number }) {
  return http.get<EnvTrendPoint[]>('/alert-lifecycle/env/trend', { params })
}


export interface TransientEventInfo {
  id: number
  alert_id: number | null
  target_type: string
  target_id: string
  metric: string | null
  title: string
  started_at: string
  recovered_at: string | null
  duration_seconds: number
  env_temperature: number | null
  env_humidity: number | null
  env_weather: string | null
  env_windspeed: number | null
  location_id: number | null
  location_name: string | null
}

export function getTransientEventsApi(limit = 100) {
  return http.get<TransientEventInfo[]>('/alert-lifecycle/transient', { params: { limit } })
}

export interface BucketItem { bucket: string; count: number; ratio: number }
export interface CorrelationReport {
  since: string
  days: number
  summary: {
    count: number
    avg_duration_seconds: number
    max_duration_seconds: number
    min_duration_seconds: number
    total_duration_seconds: number
  }
  by_hour: { hour: number; count: number; ratio: number }[]
  by_weather: { weather: string; count: number; ratio: number }[]
  by_env_bucket: {
    temperature: BucketItem[]
    humidity: BucketItem[]
    windspeed: BucketItem[]
  }
}

export function getCorrelationApi(days?: number) {
  return http.get<CorrelationReport>('/alert-lifecycle/correlation', { params: { days } })
}

export function getCorrelationReportHtmlApi(days?: number) {
  return http.get<string>('/alert-lifecycle/correlation/report', { params: { days } })
}
