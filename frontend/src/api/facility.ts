import http from "./index"

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
  return http.get<DataCenterInfo[]>("/facilities/data-centers/all")
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
  return http.get<RoomInfo[]>("/facilities/rooms/all", { params: { data_center_id } })
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
  return http.get<RackInfo[]>("/facilities/racks/all", { params: { room_id } })
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
