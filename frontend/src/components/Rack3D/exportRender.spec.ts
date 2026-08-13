import { describe, it, expect } from 'vitest'
import { computeExportLayout, wrapText, rackLabel } from './exportRender'

// ---- ??????????????? ----
// ?? bug??????????? threeBigH?? 3D ?????????
// ???? 2D U ???????? -> ?????
describe('computeExportLayout (export blank regression guard)', () => {
  it('always sizes the canvas tall enough so BOTH blocks stay fully inside', () => {
    // ?? 2D ?? < / = / > 3D ??????
    const cases = [
      { bw: 1000, bh: 500, tw: 800, th: 400 },
      { bw: 1000, bh: 500, tw: 1000, th: 400 },
      { bw: 1000, bh: 500, tw: 1600, th: 400 }, // 2D ?? -> 3D ???????? bug ??
    ]
    for (const c of cases) {
      const l = computeExportLayout(c.bw, c.bh, c.tw, c.th)
      // ?????????????? + 3D ?(threeH) + ?? + 2D ?
      const required = l.titleH + 30 + l.threeH + l.gap + c.th + 30
      expect(l.H).toBe(required)
      // 2D ????twoTop + 30 + two.height????????
      expect(l.twoTop + 30 + c.th).toBeLessThanOrEqual(l.H)
      // 3D ????titleH + 30 + threeH????? 2D ????twoTop???
      expect(l.titleH + 30 + l.threeH + l.gap).toBe(l.twoTop)
    }
  })

  it('scales 3D height with width when 2D is wider (the original blank bug)', () => {
    const l = computeExportLayout(1000, 500, 1600, 400)
    expect(l.W).toBe(1600)
    expect(l.threeScale).toBeCloseTo(1.6, 5)
    expect(l.threeH).toBe(800) // 500 * 1.6
    // ??????? 500???? 2D ???? -> ????? threeH=800
    expect(l.threeH).toBeGreaterThan(500)
  })
})

// ---- ???????/?????????? ----
// ?? bug???????wrapText ???????????????????
describe('wrapText (name truncation regression guard)', () => {
  function mockCtx(widths: Record<string, number>) {
    return {
      font: '',
      measureText(t: string) {
        // ??????????????????
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
    expect(joined).toBe(name) // ??????? -> ????????
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

// ---- ??????? + ?????? ----
describe('rackLabel', () => {
  it('concatenates code and name with a space', () => {
    expect(rackLabel('RM-01-03-01', '??01')).toBe('RM-01-03-01 ??01')
  })
  it('falls back gracefully when parts are missing', () => {
    expect(rackLabel('RM-01', null)).toBe('RM-01')
    expect(rackLabel(null, '???')).toBe('???')
    expect(rackLabel(null, null)).toBe('')
  })
})
