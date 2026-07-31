import http from "./index";

export interface ThresholdConfig {
  metric: string;
  label: string;
  min_value: number | null;
  max_value: number | null;
  unit: string;
  alert_level: string;
  enabled: boolean;
}

export interface DeviceTypeInfo {
  id: number;
  name: string;
  code: string;
  category: string;
  manufacturer?: string;
  model?: string;
  spec_description?: string;
  thresholds?: ThresholdConfig[];
  height_units?: number;
  max_power?: number;
  weight?: number;
  depth?: number;
  rated_current?: number;
  device_count: number;
  created_at: string;
  updated_at: string;
}

export interface DeviceTypePage {
  items: DeviceTypeInfo[];
  total: number;
  page: number;
  page_size: number;
}

export function getDeviceTypesApi(params: { page: number; page_size: number; keyword?: string; category?: string }) {
  return http.get<DeviceTypePage>("/devices/types", { params });
}

export function getAllDeviceTypesApi() {
  return http.get<DeviceTypeInfo[]>("/devices/types/all");
}

export function getDeviceTypeApi(id: number) {
  return http.get<DeviceTypeInfo>(`/devices/types/${id}`);
}

export function createDeviceTypeApi(data: any) {
  return http.post<DeviceTypeInfo>("/devices/types", data);
}

export function updateDeviceTypeApi(id: number, data: any, isThreshold = false) {
  const url = isThreshold ? `/devices/types/${id}/thresholds` : `/devices/types/${id}`;
  return http.put<DeviceTypeInfo>(url, data);
}

export function deleteDeviceTypeApi(id: number) {
  return http.delete(`/devices/types/${id}`);
}

export interface DeviceInfo {
  id: number;
  device_type_id: number;
  rack_id?: number;
  name: string;
  asset_number: string;
  serial_number?: string;
  brand?: string;
  model?: string;
  cpu_info?: string;
  memory_info?: string;
  disk_info?: string;
  network_info?: string;
  purchase_order?: string;
  purchase_date?: string;
  vendor?: string;
  purchase_price?: number;
  warranty_start?: string;
  warranty_end?: string;
  warranty_vendor?: string;
  start_u?: number;
  end_u?: number;
  management_ip?: string;
  business_ip?: string;
  mac_address?: string;
  out_of_band_ip?: string;
  status: string;
  device_type_name: string;
  device_type_category: string;
  rack_name: string;
  room_name: string;
  created_at: string;
  updated_at: string;
}

export interface DevicePage {
  items: DeviceInfo[];
  total: number;
  page: number;
  page_size: number;
}

export function getDevicesApi(params: { page: number; page_size: number; keyword?: string; device_type_id?: number; rack_id?: number; status?: string }) {
  return http.get<DevicePage>("/devices", { params });
}

export function getAllRacksApi(room_id?: number) {
  return http.get("/facilities/racks/all", { params: { room_id } });
}

export function getDeviceApi(id: number) {
  return http.get<DeviceInfo>(`/devices/${id}`);
}

export function createDeviceApi(data: any) {
  return http.post<DeviceInfo>("/devices", data);
}

export function updateDeviceApi(id: number, data: any) {
  return http.put<DeviceInfo>(`/devices/${id}`, data);
}

export function deleteDeviceApi(id: number) {
  return http.delete(`/devices/${id}`);
}

export function changeDeviceStatusApi(id: number, params: { status: string; operator?: string; remark?: string }) {
  return http.put(`/devices/${id}/status`, null, { params });
}

export function getDeviceLifecyclesApi(id: number) {
  return http.get(`/devices/${id}/lifecycles`);
}

export interface RackInfo {
  id: number;
  room_id: number;
  name: string;
  code: string;
  total_units: number;
}