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

/** Backend floor grid constants (semantic map units). */
export const MAP_GRID_CELL_PX = 4
export const MAP_GRID_ORIGIN_X = 10
export const MAP_GRID_ORIGIN_Y = 10

/** 2:1 isometric tile ratio (common in floor / city maps). */
export const ISO_TILE_WIDTH = MAP_GRID_CELL_PX * 2
export const ISO_TILE_HEIGHT = MAP_GRID_CELL_PX
export const ISO_EXTRUDE_DEPTH = MAP_GRID_CELL_PX * 0.42

export type MapPoint = { x: number; y: number }

export function gridTileBounds(
  col: number,
  row: number,
  spanW = 1,
  spanH = 1,
): { x: number; y: number; width: number; height: number } {
  return {
    x: MAP_GRID_ORIGIN_X + col * MAP_GRID_CELL_PX,
    y: MAP_GRID_ORIGIN_Y + row * MAP_GRID_CELL_PX,
    width: Math.max(1, spanW) * MAP_GRID_CELL_PX,
    height: Math.max(1, spanH) * MAP_GRID_CELL_PX,
  }
}

/** Project a grid corner to isometric semantic coordinates (north-up grid). */
export function gridCornerToIso(col: number, row: number): MapPoint {
  const halfW = ISO_TILE_WIDTH / 2
  const halfH = ISO_TILE_HEIGHT / 2
  return {
    x: MAP_GRID_ORIGIN_X + (col - row) * halfW,
    y: MAP_GRID_ORIGIN_Y + (col + row) * halfH,
  }
}

export function gridSpanToIsoCorners(
  col: number,
  row: number,
  spanW = 1,
  spanH = 1,
): [MapPoint, MapPoint, MapPoint, MapPoint] {
  return [
    gridCornerToIso(col, row),
    gridCornerToIso(col + spanW, row),
    gridCornerToIso(col + spanW, row + spanH),
    gridCornerToIso(col, row + spanH),
  ]
}

export function gridCellToIsoCenter(
  col: number,
  row: number,
  spanW = 1,
  spanH = 1,
): MapPoint {
  const corners = gridSpanToIsoCorners(col, row, spanW, spanH)
  return {
    x: corners.reduce((sum, point) => sum + point.x, 0) / corners.length,
    y: corners.reduce((sum, point) => sum + point.y, 0) / corners.length,
  }
}

export type IsoTileFaces = {
  top: [MapPoint, MapPoint, MapPoint, MapPoint]
  sideEast: [MapPoint, MapPoint, MapPoint, MapPoint]
  sideSouth: [MapPoint, MapPoint, MapPoint, MapPoint]
  sortKey: number
}

function extrudeIsoPoint(point: MapPoint, depth = ISO_EXTRUDE_DEPTH): MapPoint {
  return { x: point.x, y: point.y + depth }
}

/** Top face + shallow SE extrusion for pseudo-3D isometric tiles. */
export function gridSpanToIsoTile(
  col: number,
  row: number,
  spanW = 1,
  spanH = 1,
): IsoTileFaces {
  const [nw, ne, se, sw] = gridSpanToIsoCorners(col, row, spanW, spanH)
  const seD = extrudeIsoPoint(se)
  const neD = extrudeIsoPoint(ne)
  const swD = extrudeIsoPoint(sw)
  return {
    top: [nw, ne, se, sw],
    sideEast: [ne, se, seD, neD],
    sideSouth: [sw, se, seD, swD],
    sortKey: col + row,
  }
}

export function pointsToSvgPoints(points: MapPoint[]): string {
  return points.map(point => `${point.x},${point.y}`).join(' ')
}

export function isoTileBoundsPoints(
  col: number,
  row: number,
  spanW = 1,
  spanH = 1,
): MapPoint[] {
  const faces = gridSpanToIsoTile(col, row, spanW, spanH)
  return [...faces.top, ...faces.sideEast, ...faces.sideSouth]
}

/** Hub pill anchor radii in semantic map units (room logical layout). */
export const LOGICAL_HUB_ANCHOR_RX = 12
export const LOGICAL_HUB_ANCHOR_RY = 5
export const LOGICAL_EXIT_ANCHOR_R = 4.5

/** Point on an axis-aligned ellipse boundary toward ``toward``. */
export function anchorOnBoundary(
  center: MapPoint,
  toward: MapPoint,
  rx: number,
  ry: number = rx,
): MapPoint {
  const dx = toward.x - center.x
  const dy = toward.y - center.y
  if (Math.abs(dx) < 1e-6 && Math.abs(dy) < 1e-6) {
    return { ...center }
  }
  const denom = Math.sqrt((dx * dx) / (rx * rx) + (dy * dy) / (ry * ry))
  if (denom < 1e-6) {
    return { ...center }
  }
  const scale = 1 / denom
  return {
    x: center.x + dx * scale,
    y: center.y + dy * scale,
  }
}

/** Trim hub-to-exit edges so connectors attach at node rims, not centers. */
export function trimLogicalRoomEdge(
  from: MapPoint,
  to: MapPoint,
  options: { fromHub?: boolean; toExit?: boolean },
): { from: MapPoint; to: MapPoint } {
  let trimmedFrom = from
  let trimmedTo = to
  if (options.fromHub) {
    trimmedFrom = anchorOnBoundary(from, to, LOGICAL_HUB_ANCHOR_RX, LOGICAL_HUB_ANCHOR_RY)
  }
  if (options.toExit) {
    trimmedTo = anchorOnBoundary(to, from, LOGICAL_EXIT_ANCHOR_R)
  }
  return { from: trimmedFrom, to: trimmedTo }
}
