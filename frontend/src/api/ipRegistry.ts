import http from './index'

export interface IpSubnet {
  id: number
  name: string
  network: string
  prefix: number
  cidr: string
  gateway?: string
  vlan?: string
  description?: string
  status: string
  capacity: number
  allocated: number
  reserved: number
  free: number
  usage: number
}

export interface IpRegistryAddress {
  id: number
  address: string
  status: string
  subnet_id?: number
  subnet?: string
  device_id?: number
  device_name?: string
  used_as?: string
  remark?: string
  updated_at?: string
}

export function getIpSubnetsApi() {
  return http.get<IpSubnet[]>('/ip-registry/subnets')
}

export function createIpSubnetApi(data: any) {
  return http.post('/ip-registry/subnets', data)
}

export function updateIpSubnetApi(id: number, data: any) {
  return http.put(`/ip-registry/subnets/${id}`, data)
}

export function deleteIpSubnetApi(id: number) {
  return http.delete(`/ip-registry/subnets/${id}`)
}

export function getIpRegistryAddressesApi(params: any) {
  return http.get('/ip-registry/addresses', { params })
}

export function saveIpRegistryAddressApi(data: any) {
  return http.post('/ip-registry/addresses', data)
}

export function deleteIpRegistryAddressApi(id: number) {
  return http.delete(`/ip-registry/addresses/${id}`)
}

export function importDeviceIpsApi() {
  return http.post('/ip-registry/import-device-ips')
}
