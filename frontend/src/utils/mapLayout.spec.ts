import { describe, expect, it, vi } from 'vitest'
import { edgeMidpoint, formatDirectionLabel } from './mapLayout'

describe('mapLayout', () => {
  it('computes edge midpoint', () => {
    expect(edgeMidpoint({ x: 0, y: 0 }, { x: 10, y: 20 })).toEqual({ x: 5, y: 10 })
  })

  it('formats known direction labels via i18n', () => {
    const t = vi.fn((key: string) => (key.endsWith('.north') ? 'North' : key))
    expect(formatDirectionLabel('north', t)).toBe('North')
  })
})
