export function edgeMidpoint(
  from: { x: number; y: number },
  to: { x: number; y: number },
): { x: number; y: number } {
  return {
    x: (from.x + to.x) / 2,
    y: (from.y + to.y) / 2,
  }
}

export function formatDirectionLabel(
  direction: string | undefined,
  translate: (key: string) => string,
): string {
  const raw = String(direction || '').trim().toLowerCase()
  if (!raw) return ''
  const key = `worldInteraction.map.direction.${raw}`
  const translated = translate(key)
  return translated === key ? raw : translated
}

export const COMPASS_ROSE_SIZE = 36
