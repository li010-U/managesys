import { describe, it, expect } from 'vitest'
import {
  deviceStatusType, deviceStatusLabel, toChineseOrdinal, rackUtilPercent,
  rackUtilColor, powerLoadColor, getRackUnitText, lifecycleActionLabel,
  lcTagType, utilClass, fmtTime, utilColorFor,
} from './useRackUi'
import type { RackInfo } from '../api/facility'

const rack = (total: number, available: number): RackInfo => ({
  id: 1, room_id: 1, name: 'R1', code: 'r1', total_units: total,
  available_units: available, status: 'active', device_count: 0,
  room_name: 'room', created_at: '', updated_at: '',
})

describe('useRackUi (RackView 抽离纯函数)', () => {
  it('deviceStatusType / deviceStatusLabel map states', () => {
    expect(deviceStatusType('running')).toBe('success')
    expect(deviceStatusType('mounted')).toBe('info')
    expect(deviceStatusType('unknown')).toBe('danger')
    expect(deviceStatusLabel('running')).toBe('运行中')
    expect(deviceStatusLabel('scrapped')).toBe('已报废')
    expect(deviceStatusLabel('foo')).toBe('foo')
  })

  it('toChineseOrdinal renders 0~20 and falls back', () => {
    expect(toChineseOrdinal(0)).toBe('〇')
    expect(toChineseOrdinal(10)).toBe('十')
    expect(toChineseOrdinal(20)).toBe('二十')
    expect(toChineseOrdinal(99)).toBe('99')
  })

  it('rackUtilPercent computes rounded utilization', () => {
    expect(rackUtilPercent(rack(42, 21))).toBe(50)
    expect(rackUtilPercent(rack(10, 0))).toBe(100)
    expect(rackUtilPercent(rack(0, 0))).toBe(0)
  })

  it('rackUtilColor / utilClass / utilColorFor color tiers', () => {
    expect(rackUtilColor(rack(42, 0))).toBe('#e74c3c')     // 100
    expect(rackUtilColor(rack(42, 20))).toBe('#e67e22')    // ~52
    expect(rackUtilColor(rack(42, 30))).toBe('#27ae60')    // ~29
    expect(utilClass(rack(42, 0))).toBe('rack-util-high')
    expect(utilClass(rack(42, 15))).toBe('rack-util-mid')  // 27/42 -> 64%
    expect(utilClass(rack(42, 35))).toBe('rack-util-low')
    expect(utilColorFor(90)).toBe('#e74c3c')
    expect(utilColorFor(50)).toBe('#e67e22')
    expect(utilColorFor(10)).toBe('#27ae60')
  })

  it('powerLoadColor tiers', () => {
    expect(powerLoadColor(95)).toBe('#e74c3c')
    expect(powerLoadColor(75)).toBe('#e67e22')
    expect(powerLoadColor(50)).toBe('#27ae60')
  })

  it('getRackUnitText shows used/total', () => {
    expect(getRackUnitText(rack(42, 10))).toBe('32/42U')
  })

  it('lifecycleActionLabel / lcTagType map actions', () => {
    expect(lifecycleActionLabel('mount')).toBe('上架')
    expect(lifecycleActionLabel('unknown')).toBe('unknown')
    expect(lcTagType('create')).toBe('success')
    expect(lcTagType('unknown')).toBe('info')
  })

  it('fmtTime formats and guards empty', () => {
    expect(fmtTime('')).toBe('--')
    expect(fmtTime('2026-01-02T03:04:05')).toContain('2026')
  })
})