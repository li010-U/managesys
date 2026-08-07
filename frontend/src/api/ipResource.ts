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
