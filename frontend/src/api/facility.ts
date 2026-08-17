import http from "./index"
import { dictGet } from "./dictCache"

/* ===== DataCenter ===== */
export interface DataCenterInfo {
  id: number
  name: string
  code: string
  address?: string
  description?: string
  contact_person?: string
  contact_phone?: string
  contact_email?: string
    status: string
  room_count: number
  created_at: string
  updated_at: string
}

export interface DataCenterPage {
  items: DataCenterInfo[]
  total: number
  page: number
  page_size: number
}

export function getDataCentersApi(params: { page: number; page_size: number; keyword?: string }) {
  return http.get<DataCenterPage>("/facilities/data-centers", { params })
}

export function getAllDataCentersApi() {
  return dictGet<DataCenterInfo[]>("/facilities/data-centers/all")
}

export function getDataCenterApi(id: number) {
  return http.get<DataCenterInfo>(`/facilities/data-centers/${id}`)
}

export function createDataCenterApi(data: any) {
  return http.post<DataCenterInfo>("/facilities/data-centers", data)
}

export function updateDataCenterApi(id: number, data: any) {
  return http.put<DataCenterInfo>(`/facilities/data-centers/${id}`, data)
}

export function deleteDataCenterApi(id: number) {
  return http.delete(`/facilities/data-centers/${id}`)
}

/* ===== Room ===== */
export interface RoomInfo {
  id: number
  data_center_id: number
  name: string
  code: string
  floor?: string
  area?: number
  load_rating?: string
  admin_name?: string
  admin_phone?: string
  admin_email?: string
  tier_level?: string
  description?: string
    status: string
  rack_count: number
  data_center_name: string
  created_at: string
  updated_at: string
}

export interface RoomPage {
  items: RoomInfo[]
  total: number
  page: number
  page_size: number
}

export function getRoomsApi(params: { page: number; page_size: number; keyword?: string; data_center_id?: number }) {
  return http.get<RoomPage>("/facilities/rooms", { params })
}

export function getAllRoomsApi(data_center_id?: number) {
  return dictGet<RoomInfo[]>("/facilities/rooms/all", { data_center_id })
}

export function getRoomApi(id: number) {
  return http.get<RoomInfo>(`/facilities/rooms/${id}`)
}

export function createRoomApi(data: any) {
  return http.post<RoomInfo>("/facilities/rooms", data)
}

export function updateRoomApi(id: number, data: any) {
  return http.put<RoomInfo>(`/facilities/rooms/${id}`, data)
}

export function deleteRoomApi(id: number) {
  return http.delete(`/facilities/rooms/${id}`)
}

/* ===== Rack ===== */
export interface RackInfo {
  id: number
  room_id: number
  name: string
  code: string
  row_pos?: number
  col_pos?: number
  total_units: number
  available_units: number
  rated_power?: number
  pos_x_m?: number
  pos_z_m?: number
  width_m?: number
  depth_m?: number
  facing_deg?: number
    status: string
  description?: string
  device_count: number
  room_name: string
  created_at: string
  updated_at: string
}

export interface RackPage {
  items: RackInfo[]
  total: number
  page: number
  page_size: number
}

export function getRacksApi(params: { page: number; page_size: number; keyword?: string; room_id?: number }) {
  return http.get<RackPage>("/facilities/racks", { params })
}

export function getAllRacksApi(room_id?: number) {
  return dictGet<RackInfo[]>("/facilities/racks/all", { room_id })
}

export function getRackApi(id: number) {
  return http.get<RackInfo>(`/facilities/racks/${id}`)
}

export function createRackApi(data: any) {
  return http.post<RackInfo>("/facilities/racks", data)
}

export function updateRackApi(id: number, data: any) {
  return http.put<RackInfo>(`/facilities/racks/${id}`, data)
}

export function deleteRackApi(id: number) {
  return http.delete(`/facilities/racks/${id}`)
}
export function getRoomRack3dApi(roomId: number) {
  return http.get<any>(`/facilities/rooms/${roomId}/rack3d`)
}
export function getRackEnvironmentApi(id: number) {
  return http.get<{ rack_id: number; room_id: number; sensors: any[]; active_alerts: number; rack_alerts: Record<number, number> }>(`/facilities/racks/${id}/environment`)
}

export interface RoomResourceRack {
  id: number
  name: string
  code: string
  rated_power_kw?: number
  total_units?: number
  available_units?: number
  used_u: number
  device_count: number
  cpu_cores: number
  memory_gb: number
  disk_gb: number
  gpu_count: number
  gpu_mem_gb: number
  compute_tflops: number
  power_kw: number
}

export interface RoomResources {
  room: { id: number; name: string; code: string; floor?: string }
  totals: {
    device_count: number
    cpu_cores: number
    memory_gb: number
    disk_gb: number
    gpu_count: number
    gpu_mem_gb: number
    compute_tflops: number
    power_kw: number
    rack_count: number
    used_u: number
    total_u: number
  }
  racks: RoomResourceRack[]
  cpu_distribution: Record<string, number>
}

export function getRoomResourcesApi(roomId: number) {
  return http.get<RoomResources>(`/facilities/rooms/${roomId}/resources`)
}
