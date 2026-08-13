import http from "./index"

export interface IpOverview {
  total_entries: number
  unique_ips: number
  device_count: number
  role_counts: Record<string, number>
  role_labels: Record<string, string>
  conflicts: Array<{ ip: string; role: string; devices: any[] }>
  potential_conflicts: Array<{ ip: string; roles: string[] }>
  conflict_count: number
  subnets: Array<{ subnet: string; total: number; public: number; private: number; ips: any[] }>
}

export function getIpOverviewApi() {
  return http.get<IpOverview>("/ip-resources/overview")
}


export interface ConflictDevice {
  id: number
  name: string
  asset_number: string
  status?: string
  rack_id?: number
  rack_name?: string
  room_id?: number
  role: string
}

export interface IpConflict {
  ip: string
  role?: string
  roles?: string[]
  devices?: ConflictDevice[]
  conflict_type: 'explicit' | 'potential'
}

export interface IpConflicts {
  explicit: IpConflict[]
  potential: IpConflict[]
  total: number
}

export function getIpConflictsApi() {
  return http.get<IpConflicts>("/ip-resources/conflicts")
}

export function resolveIpConflictApi(data: { device_id: number; role: string; new_ip: string }) {
  return http.post("/ip-resources/resolve", data)
}
