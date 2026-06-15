import { describe, expect, it, vi } from 'vitest'
import {
  edgeMidpoint,
  formatDirectionLabel,
  gridCellToIsoCenter,
  gridCornerToIso,
  gridSpanToIsoCorners,
  gridSpanToIsoTile,
  pointsToSvgPoints,
} from './mapLayout'

describe('mapLayout', () => {
  it('computes edge midpoint', () => {
    expect(edgeMidpoint({ x: 0, y: 0 }, { x: 10, y: 20 })).toEqual({ x: 5, y: 10 })
  })

  it('formats known direction labels via i18n', () => {
    const t = vi.fn((key: string) => (key.endsWith('.north') ? 'North' : key))
    expect(formatDirectionLabel('north', t)).toBe('North')
  })

  it('projects grid corners to isometric coordinates', () => {
    const nw = gridCornerToIso(4, 2)
    const east = gridCornerToIso(7, 2)
    expect(nw.x).toBeLessThan(east.x)
    expect(nw.y).toBeLessThan(east.y)
  })

  it('builds iso tile faces for a grid span', () => {
    const tile = gridSpanToIsoTile(4, 2, 2, 1)
    expect(tile.top).toHaveLength(4)
    expect(tile.sideEast).toHaveLength(4)
    expect(tile.sideSouth).toHaveLength(4)
    expect(tile.sortKey).toBe(6)
    expect(pointsToSvgPoints(tile.top).split(' ')).toHaveLength(4)
  })

  it('centers iso tile within its corner bounds', () => {
    const corners = gridSpanToIsoCorners(6, 8, 1, 1)
    const center = gridCellToIsoCenter(6, 8, 1, 1)
    const minX = Math.min(...corners.map(point => point.x))
    const maxX = Math.max(...corners.map(point => point.x))
    const minY = Math.min(...corners.map(point => point.y))
    const maxY = Math.max(...corners.map(point => point.y))
    expect(center.x).toBeGreaterThanOrEqual(minX)
    expect(center.x).toBeLessThanOrEqual(maxX)
    expect(center.y).toBeGreaterThanOrEqual(minY)
    expect(center.y).toBeLessThanOrEqual(maxY)
  })
})
