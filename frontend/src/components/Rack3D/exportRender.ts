// Pure helpers for the 3D/2D export rendering geometry and text wrapping.
// Extracted out of Rack3DScene.vue so the historical UI regressions can be
// guarded by automated tests ("export blank", "name truncated").

export interface ExportLayout {
  titleH: number
  gap: number
  W: number
  threeScale: number
  threeH: number
  H: number
  twoTop: number
}

// Compute the final export canvas dimensions.
// Historical "partial blank export" regression: threeH MUST scale with width,
// otherwise the 3D block is drawn scaled up beyond its allocated height and
// pushes the lower 2D U-bit block out of the canvas (leaving it blank).
export function computeExportLayout(
  threeBigW: number,
  threeBigH: number,
  twoWidth: number,
  twoHeight: number,
  titleH = 56,
  gap = 16,
): ExportLayout {
  const W = Math.max(threeBigW, twoWidth)
  const threeScale = W / threeBigW
  const threeH = Math.round(threeBigH * threeScale)
  const H = titleH + 30 + threeH + gap + twoHeight + 30
  const twoTop = titleH + 30 + threeH + gap
  return { titleH, gap, W, threeScale, threeH, H, twoTop }
}

// Wrap text into full lines without ever truncating (historical "name shown
// incompletely" regression). ctx is any 2D context / mock exposing measureText.
export function wrapText(
  text: string,
  maxW: number,
  ctx: { measureText(t: string): { width: number }; font?: string },
  font: string,
): string[] {
  const mw = Math.max(maxW, 12)
  const words = String(text || '').split('')
  const lines: string[] = []
  let cur = ''
  if (ctx) ctx.font = font
  for (const ch of words) {
    const test = cur + ch
    if (ctx && ctx.measureText(test).width > mw && cur) {
      lines.push(cur)
      cur = ch
    } else {
      cur = test
    }
  }
  if (cur) lines.push(cur)
  return lines.length ? lines : ['']
}

// Full rack display label: code + (space) + name, never truncated.
export function rackLabel(code?: string | null, name?: string | null): string {
  const c = code || ''
  const n = name || ''
  return c ? c + (n ? ' ' + n : '') : n
}
