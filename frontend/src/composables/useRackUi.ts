/**
 * 机架 UI 纯工具函数集合。
 * 从 RackView.vue 巨型组件中抽离的、不依赖组件状态/响应式引用的纯函数，
 * 便于单元测试与复用。改动机架列表/详情相关展示逻辑时优先改这里。
 */
import type { RackInfo } from '../api/facility'

/** 设备状态 -> Element Plus tag 类型 */
export function deviceStatusType(s: string): string {
  if (s === 'running') return 'success'
  if (s === 'mounted' || s === 'in_stock') return 'info'
  return 'danger'
}

/** 设备状态 -> 中文文案 */
export function deviceStatusLabel(s: string): string {
  const map: Record<string, string> = { running: '运行中', mounted: '已上架', in_stock: '在库', offline: '离线', scrapped: '已报废' }
  return map[s] || s
}

/** 数值 -> 中文序数（机架/槽位，0~20） */
export function toChineseOrdinal(n: number): string {
  const cn = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十']
  return cn[n] || String(n)
}

/** 机架利用率（0~100 整数） */
export function rackUtilPercent(rack: RackInfo): number {
  if (!rack.total_units) return 0
  return Math.round((rack.total_units - rack.available_units) / rack.total_units * 100)
}

/** 机架利用率 -> 颜色 */
export function rackUtilColor(rack: RackInfo): string {
  const u = rackUtilPercent(rack)
  return u >= 80 ? '#e74c3c' : u >= 50 ? '#e67e22' : '#27ae60'
}

/** 负载百分比 -> 颜色 */
export function powerLoadColor(pct: number): string {
  return pct >= 90 ? '#e74c3c' : pct >= 70 ? '#e67e22' : '#27ae60'
}

/** 机架已用/总 U 文案 */
export function getRackUnitText(rack: RackInfo): string {
  return (rack.total_units - rack.available_units) + '/' + rack.total_units + 'U'
}

/** 生命周期动作 -> 中文文案 */
export function lifecycleActionLabel(a: string): string {
  const map: Record<string, string> = { create: '创建', mount: '上架', unmount: '下架', move: '挪位', change: '状态变更', delete: '删除' }
  return map[a] || a
}

/** 生命周期动作 -> tag 类型 */
export function lcTagType(a: string): string {
  const map: Record<string, string> = { create: 'success', mount: 'primary', unmount: 'warning', move: 'info', change: 'warning', delete: 'danger' }
  return map[a] || 'info'
}

/** 机架利用率 -> css class */
export function utilClass(rack: RackInfo): string {
  const u = rackUtilPercent(rack)
  return u >= 80 ? 'rack-util-high' : u >= 50 ? 'rack-util-mid' : 'rack-util-low'
}

/** 时间戳 -> 中文本地时间 */
export function fmtTime(ts: string): string {
  if (!ts) return '--'
  return new Date(ts).toLocaleString('zh-CN')
}

/** 利用率数值 -> 颜色 */
export function utilColorFor(v: number): string {
  return v >= 80 ? '#e74c3c' : v >= 50 ? '#e67e22' : '#27ae60'
}