import { computed, type ComputedRef } from 'vue'
import type { ComposerTranslation } from 'vue-i18n'
import {
  edgeMidpoint,
  formatDirectionLabel,
  gridCellToIsoCenter,
  gridSpanToIsoTile,
  isoTileBoundsPoints,
  LOGICAL_HUB_ANCHOR_RX,
  LOGICAL_HUB_ANCHOR_RY,
  pointsToSvgPoints,
  trimLogicalRoomEdge,
  type MapPoint,
} from '@/utils/mapLayout'
import type { AgentMapPresence, SemanticMapEdge, SemanticMapNode } from '@/types/world'

export type MapBounds = {
  minX: number
  minY: number
  width: number
  height: number
}

export type RenderedMapNode = SemanticMapNode & {
  left: string
  top: string
  displayName: string
}

const ROOM_CONTENT_GROUP_RE = /^cluster:room:\d+:(occupant|device|item)$/

export function isRoomContentGroup(node: SemanticMapNode): boolean {
  return /^cluster:room:\d+:(device|item)$/.test(node.id)
}

export function hasFloorPlanGrid(node: SemanticMapNode): boolean {
  return node.mapGridCol != null && node.mapGridRow != null
}

export function isFloorPlanTile(node: SemanticMapNode, layout?: string): boolean {
  return layout === 'grid' && hasFloorPlanGrid(node)
}

export type RenderedFloorPlanTile = SemanticMapNode & {
  topPoints: string
  sideEastPoints: string
  sideSouthPoints: string
  labelX: number
  labelY: number
  displayName: string
  sortKey: number
}

function semanticMapPosition(node: SemanticMapNode, layout?: string): MapPoint {
  if (layout === 'grid' && hasFloorPlanGrid(node)) {
    return gridCellToIsoCenter(
      node.mapGridCol!,
      node.mapGridRow!,
      node.mapGridSpanW ?? 1,
      node.mapGridSpanH ?? 1,
    )
  }
  return { x: node.x, y: node.y }
}

function toViewportPoint(point: MapPoint, minX: number, minY: number, scale: number): MapPoint {
  return {
    x: (point.x - minX) * scale,
    y: (point.y - minY) * scale,
  }
}

export function computeFloorPlanBounds(nodes: SemanticMapNode[], pad: number): MapBounds {
  const tiles = nodes.filter(hasFloorPlanGrid)
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  const absorb = (point: MapPoint) => {
    minX = Math.min(minX, point.x)
    minY = Math.min(minY, point.y)
    maxX = Math.max(maxX, point.x)
    maxY = Math.max(maxY, point.y)
  }

  for (const node of tiles) {
    for (const point of isoTileBoundsPoints(
      node.mapGridCol!,
      node.mapGridRow!,
      node.mapGridSpanW ?? 1,
      node.mapGridSpanH ?? 1,
    )) {
      absorb(point)
    }
  }
  for (const node of nodes) {
    if (!hasFloorPlanGrid(node)) {
      absorb({ x: node.x, y: node.y })
    }
  }

  if (!Number.isFinite(minX)) {
    return computeMapBounds(nodes, pad)
  }
  return {
    minX: minX - pad,
    minY: minY - pad,
    width: Math.max(80, maxX - minX + pad * 2),
    height: Math.max(80, maxY - minY + pad * 2),
  }
}

export function roomContentGroupLabel(node: SemanticMapNode, t: ComposerTranslation): string {
  const match = node.id.match(ROOM_CONTENT_GROUP_RE)
  if (!match) {
    return node.name
  }
  const count = node.objectIds?.length ?? 0
  return t(`worldInteraction.map.contentGroups.${match[1]}`, { count })
}

export type RenderedMapEdge = SemanticMapEdge & {
  x1: number
  y1: number
  x2: number
  y2: number
  className: string
  title: string
  labelX: number
  labelY: number
  directionText: string
}

export type RenderedMapAgent = AgentMapPresence & {
  left?: string
  top?: string
  right?: string
  bottom?: string
  floating: boolean
}

export type MinimapNode = SemanticMapNode & {
  miniX: number
  miniY: number
}

export function computeMapBounds(nodes: SemanticMapNode[], pad: number): MapBounds {
  if (!nodes.length) {
    return { minX: 0, minY: 0, width: 100, height: 100 }
  }
  const xs = nodes.map(node => node.x)
  const ys = nodes.map(node => node.y)
  const minX = Math.min(...xs) - pad
  const minY = Math.min(...ys) - pad
  const maxX = Math.max(...xs) + pad
  const maxY = Math.max(...ys) + pad
  return {
    minX,
    minY,
    width: Math.max(80, maxX - minX),
    height: Math.max(80, maxY - minY),
  }
}

function edgeClassName(edge: SemanticMapEdge): string {
  const classes: string[] = []
  const dir = String(edge.direction || '').toLowerCase()
  if (dir === 'up' || dir === 'down') {
    classes.push('edge-vertical')
  }
  if (edge.crossBuilding || edge.status === 'cross-building') {
    classes.push('edge-cross-building')
  }
  return classes.join(' ')
}

function edgeTitle(edge: SemanticMapEdge, t: ComposerTranslation): string {
  if (edge.status === 'locked') {
    return t('worldInteraction.map.edgeLockedHint')
  }
  if (edge.crossBuilding || edge.status === 'cross-building') {
    const target = edge.targetLabel || ''
    return target
      ? t('worldInteraction.map.crossBuildingExit', { target })
      : t('worldInteraction.map.crossBuildingExitGeneric')
  }
  return edge.targetLabel || ''
}

export function useSemanticMapRender(options: {
  nodes: ComputedRef<SemanticMapNode[]>
  edges: ComputedRef<SemanticMapEdge[]>
  agentPresences: ComputedRef<AgentMapPresence[]>
  bounds: ComputedRef<MapBounds>
  coordUnitPx: number
  minimapW: number
  minimapH: number
  minimapPad: number
  layout?: ComputedRef<string | undefined>
  t: ComposerTranslation
}) {
  const nodePositionById = computed(() => {
    const positions = new Map<string, { x: number; y: number }>()
    const { minX, minY } = options.bounds.value
    const scale = options.coordUnitPx
    const layout = options.layout?.value
    for (const node of options.nodes.value) {
      const semantic = semanticMapPosition(node, layout)
      positions.set(node.id, toViewportPoint(semantic, minX, minY, scale))
    }
    return positions
  })

  const renderNodes = computed<RenderedMapNode[]>(() => {
    const positions = nodePositionById.value
    return options.nodes.value.map(node => {
      const point = positions.get(node.id) ?? { x: 0, y: 0 }
      return {
        ...node,
        left: `${point.x}px`,
        top: `${point.y}px`,
        displayName: roomContentGroupLabel(node, options.t),
      }
    })
  })

  const renderEdges = computed<RenderedMapEdge[]>(() => {
    const { minX, minY } = options.bounds.value
    const scale = options.coordUnitPx
    const layout = options.layout?.value
    const nodeById = new Map(options.nodes.value.map(node => [node.id, node]))

    return options.edges.value.map(edge => {
      const fromNode = nodeById.get(edge.from)
      const toNode = nodeById.get(edge.to)
      let fromSemantic = fromNode ? semanticMapPosition(fromNode, layout) : { x: 0, y: 0 }
      let toSemantic = toNode ? semanticMapPosition(toNode, layout) : { x: 0, y: 0 }

      if (layout === 'logical') {
        const trimmed = trimLogicalRoomEdge(fromSemantic, toSemantic, {
          fromHub: fromNode?.logicalZone === 'hub',
          toExit: toNode?.logicalZone === 'exit',
        })
        fromSemantic = trimmed.from
        toSemantic = trimmed.to
      }

      const from = toViewportPoint(fromSemantic, minX, minY, scale)
      const to = toViewportPoint(toSemantic, minX, minY, scale)
      const labelPos = edgeMidpoint(from, to)
      return {
        ...edge,
        x1: from.x,
        y1: from.y,
        x2: to.x,
        y2: to.y,
        className: edgeClassName(edge),
        title: edgeTitle(edge, options.t),
        labelX: labelPos.x,
        labelY: labelPos.y,
        directionText: formatDirectionLabel(edge.direction || edge.label, options.t),
      }
    })
  })

  const logicalHubRing = computed(() => {
    if (options.layout?.value !== 'logical') {
      return null
    }
    const hub = options.nodes.value.find(node => node.logicalZone === 'hub')
    if (!hub) {
      return null
    }
    const { minX, minY } = options.bounds.value
    const scale = options.coordUnitPx
    const center = toViewportPoint(semanticMapPosition(hub, 'logical'), minX, minY, scale)
    return {
      cx: center.x,
      cy: center.y,
      rx: LOGICAL_HUB_ANCHOR_RX * scale,
      ry: LOGICAL_HUB_ANCHOR_RY * scale,
    }
  })

  const labeledRenderEdges = computed(() =>
    renderEdges.value.filter(edge => edge.status !== 'locked' && Boolean(edge.direction)),
  )

  const renderAgents = computed<RenderedMapAgent[]>(() => {
    const positions = nodePositionById.value
    const nodeById = new Map(options.nodes.value.map(node => [node.id, node]))
    return options.agentPresences.value.map(agent => {
      const anchor = nodeById.get(agent.currentSpaceId)
      if (!anchor) {
        return {
          ...agent,
          right: '12px',
          bottom: '12px',
          floating: true,
        }
      }
      const point = positions.get(anchor.id) ?? { x: 0, y: 0 }
      return {
        ...agent,
        left: `${point.x + 28}px`,
        top: `${point.y - 18}px`,
        floating: false,
      }
    })
  })

  const minimapScale = computed(() => {
    const bw = Math.max(1, options.bounds.value.width)
    const bh = Math.max(1, options.bounds.value.height)
    const pad = options.minimapPad
    return Math.min(
      (options.minimapW - pad * 2) / bw,
      (options.minimapH - pad * 2) / bh,
    )
  })

  const minimapNodes = computed<MinimapNode[]>(() => {
    const { minX, minY } = options.bounds.value
    const pad = options.minimapPad
    const scale = minimapScale.value
    const layout = options.layout?.value
    return options.nodes.value.map(node => {
      const semantic = semanticMapPosition(node, layout)
      return {
        ...node,
        miniX: pad + (semantic.x - minX) * scale,
        miniY: pad + (semantic.y - minY) * scale,
      }
    })
  })

  const renderFloorPlanTiles = computed<RenderedFloorPlanTile[]>(() => {
    if (options.layout?.value !== 'grid') {
      return []
    }
    const { minX, minY } = options.bounds.value
    const scale = options.coordUnitPx
    return options.nodes.value
      .filter(node => hasFloorPlanGrid(node))
      .map(node => {
        const faces = gridSpanToIsoTile(
          node.mapGridCol!,
          node.mapGridRow!,
          node.mapGridSpanW ?? 1,
          node.mapGridSpanH ?? 1,
        )
        const center = gridCellToIsoCenter(
          node.mapGridCol!,
          node.mapGridRow!,
          node.mapGridSpanW ?? 1,
          node.mapGridSpanH ?? 1,
        )
        const label = toViewportPoint(center, minX, minY, scale)
        const mapTop = (points: MapPoint[]) =>
          pointsToSvgPoints(points.map(point => toViewportPoint(point, minX, minY, scale)))
        return {
          ...node,
          topPoints: mapTop(faces.top),
          sideEastPoints: mapTop(faces.sideEast),
          sideSouthPoints: mapTop(faces.sideSouth),
          labelX: label.x,
          labelY: label.y,
          displayName: node.name,
          sortKey: faces.sortKey,
        }
      })
      .sort((a, b) => a.sortKey - b.sortKey)
  })

  return {
    renderNodes,
    renderFloorPlanTiles,
    renderEdges,
    labeledRenderEdges,
    renderAgents,
    minimapNodes,
    minimapScale,
    logicalHubRing,
  }
}
