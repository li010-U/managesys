import { describe, it, expect } from 'vitest'
import { computeExportLayout, wrapText, rackLabel } from './exportRender'

// ---- 导出布局回归防卫（防导出空白 bug） ----
// 原 bug：当 2D 块更宽时，3D 块被裁切导致导出画布下方空白
// 画布需同时容纳 2D 与 3D，二者都必须完整落在画布内
describe('computeExportLayout (export blank regression guard)', () => {
  it('always sizes the canvas tall enough so BOTH blocks stay fully inside', () => {
    // 覆盖 2D 宽 < / = / > 3D 宽三种情况
    const cases = [
      { bw: 1000, bh: 500, tw: 800, th: 400 },
      { bw: 1000, bh: 500, tw: 1000, th: 400 },
      { bw: 1000, bh: 500, tw: 1600, th: 400 }, // 2D 宽 -> 3D 按 2D 宽等比缩放（曾触发原 bug 的情景）
    ]
    for (const c of cases) {
      const l = computeExportLayout(c.bw, c.bh, c.tw, c.th)
      // 高度 = 标题(titleH+30) + 3D 块(threeH) + 间隔 + 2D 块
      const required = l.titleH + 30 + l.threeH + l.gap + c.th + 30
      expect(l.H).toBe(required)
      // 2D 块顶部 twoTop + 30 + 块高 必须留在画布内
      expect(l.twoTop + 30 + c.th).toBeLessThanOrEqual(l.H)
      // 3D 块底部 titleH+30+threeH+gap 恰为 2D 块顶部 twoTop 的位置
      expect(l.titleH + 30 + l.threeH + l.gap).toBe(l.twoTop)
    }
  })

  it('scales 3D height with width when 2D is wider (the original blank bug)', () => {
    const l = computeExportLayout(1000, 500, 1600, 400)
    expect(l.W).toBe(1600)
    expect(l.threeScale).toBeCloseTo(1.6, 5)
    expect(l.threeH).toBe(800) // 500 * 1.6
    // 3D 高应按 2D 宽缩放（500 -> 对应约三倍高）=> threeH=800
    expect(l.threeH).toBeGreaterThan(500)
  })
})

// ---- wrapText 名称截断回归防卫 ----
// 原 bug：wrapText 想把超长设备名换行显示，曾丢失字符
describe('wrapText (name truncation regression guard)', () => {
  function mockCtx(widths: Record<string, number>) {
    return {
      font: '',
      measureText(t: string) {
        // 按单字符宽度累加估算字符串宽度
        let w = 0
        for (const ch of t) w += widths[ch] ?? 1
        return { width: w }
      },
    }
  }

  it('returns the FULL text split across lines without dropping any char', () => {
    const name = 'ThisIsAVeryLongDeviceDisplayNameThatMustNeverBeTrimmed'
    const ctx = mockCtx({})
    const lines = wrapText(name, 10, ctx as never, '12px sans-serif')
    const joined = lines.join('')
    expect(joined).toBe(name) // 拼接后应与原名称完全一致
    expect(lines.length).toBeGreaterThan(1)
  })

  it('single char per line still preserves all chars', () => {
    const name = 'abcdef'
    const lines = wrapText(name, 1, { measureText: (t: string) => ({ width: t.length }) } as never, '12px')
    expect(lines.join('')).toBe(name)
  })

  it('empty input yields an empty line (no crash)', () => {
    const lines = wrapText('', 100, { measureText: (t: string) => ({ width: t.length }) } as never, '12px')
    expect(lines).toEqual([''])
  })
})

// ---- rackLabel 拼接规则 + 兜底 ----
describe('rackLabel', () => {
  it('concatenates code and name with a space', () => {
    expect(rackLabel('RM-01-03-01', '机房01')).toBe('RM-01-03-01 机房01')
  })
  it('falls back gracefully when parts are missing', () => {
    expect(rackLabel('RM-01', null)).toBe('RM-01')
    expect(rackLabel(null, '机房')).toBe('机房')
    expect(rackLabel(null, null)).toBe('')
  })
})
