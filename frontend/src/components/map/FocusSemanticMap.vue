<template>
  <section class="map-panel">
    <div class="region-menu">
      <h2>{{ t('worldInteraction.map.title') }}</h2>
      <div class="region-actions">
        <el-button size="small" text @click="mapStore.drillTo('world')">
          {{ t('worldInteraction.map.openFullMap') }}
        </el-button>
        <el-button size="small" text @click="mapStore.drillToCurrentRoom()">
          {{ t('worldInteraction.map.backToRoom') }}
        </el-button>
      </div>
    </div>

    <nav v-if="mapStore.breadcrumb.length > 1" class="map-breadcrumb" :aria-label="t('worldInteraction.map.layersLabel')">
      <template v-for="(crumb, index) in mapStore.breadcrumb" :key="`${crumb.layer}-${crumb.id}`">
        <span v-if="index > 0" class="breadcrumb-sep">›</span>
        <button
          type="button"
          class="breadcrumb-item"
          :class="{ active: index === mapStore.breadcrumb.length - 1 }"
          @click="mapStore.navigateBreadcrumb(crumb)"
        >
          {{ crumb.name }}
        </button>
      </template>
    </nav>

    <div v-if="worldSession.loading" class="empty">{{ t('worldInteraction.map.loading') }}</div>
    <div v-else-if="loadError" class="empty error">
      <p>{{ loadError }}</p>
      <el-button size="small" @click="worldSession.loadCurrent">{{ t('common.retry') }}</el-button>
    </div>
    <div v-else-if="!mapStore.map" class="empty">{{ t('worldInteraction.map.noData') }}</div>
    <div v-else-if="!mapStore.nodes.length && !mapStore.floorRoomList.length" class="empty">
      {{ t('worldInteraction.map.empty') }}
    </div>
    <div v-else class="map-body">
      <p
        v-if="mapStore.map?.layout === 'logical'"
        class="logical-zone-hint"
      >
        {{ logicalZoneHint }}
      </p>
      <p
        v-if="mapStore.viewLayer === 'floor' && !mapStore.floorPlanReady"
        class="floor-plan-hint"
      >
        {{ t('worldInteraction.map.floorPlanNotReady') }}
      </p>
      <ul
        v-if="mapStore.floorRoomList.length"
        class="floor-room-list"
        :aria-label="t('worldInteraction.map.floorRoomListLabel')"
      >
        <li v-for="room in mapStore.floorRoomList" :key="room.id">
          <button
            type="button"
            class="floor-room-item"
            :class="room.status"
            @click="mapStore.drillTo('room', room.id)"
          >
            {{ room.name }}
          </button>
        </li>
      </ul>
      <div ref="mapStageRef" class="map-stage">
      <div
        v-if="mapStore.nodes.length"
        ref="canvasRef"
        class="map-canvas"
      :class="{
        'is-panning': isPanning,
        'is-loading': mapStore.mapLoading,
        [`mode-${mapStore.mode}`]: true,
        'layout-logical': mapStore.map?.layout === 'logical',
        'layout-grid': isFloorPlanLayout,
        'layout-campus-grid': isCampusGridLayout,
      }"
      @wheel.prevent="onWheel"
      @mousedown="onPanStart"
      @mouseup="onCanvasMouseUp"
    >
      <div class="compass-rose" aria-hidden="true" @mousedown.stop>
        <svg :width="COMPASS_ROSE_SIZE" :height="COMPASS_ROSE_SIZE" viewBox="0 0 36 36">
          <polygon points="18,4 22,16 18,14 14,16" fill="rgba(64,158,255,0.9)" />
          <text x="18" y="3" text-anchor="middle" class="compass-n">N</text>
        </svg>
      </div>

      <div class="map-toolbar" @mousedown.stop>
        <el-button-group size="small">
          <el-button :title="t('worldInteraction.map.panLeft')" @click="panBy(-48, 0)">
            <el-icon><ArrowLeft /></el-icon>
          </el-button>
          <el-button :title="t('worldInteraction.map.panRight')" @click="panBy(48, 0)">
            <el-icon><ArrowRight /></el-icon>
          </el-button>
          <el-button :title="t('worldInteraction.map.panUp')" @click="panBy(0, -48)">
            <el-icon><ArrowUp /></el-icon>
          </el-button>
          <el-button :title="t('worldInteraction.map.panDown')" @click="panBy(0, 48)">
            <el-icon><ArrowDown /></el-icon>
          </el-button>
        </el-button-group>
        <el-button-group size="small">
          <el-button :title="t('worldInteraction.map.zoomOut')" @click="zoomBy(0.85)">
            <el-icon><ZoomOut /></el-icon>
          </el-button>
          <el-button :title="t('worldInteraction.map.zoomIn')" @click="zoomBy(1.18)">
            <el-icon><ZoomIn /></el-icon>
          </el-button>
        </el-button-group>
        <span class="zoom-label">{{ zoomPercent }}%</span>
      </div>

      <aside
        v-if="mapStore.viewLayer === 'floor' && mapStore.floorStack.length > 1"
        class="floor-stack-panel"
        :aria-label="t('worldInteraction.map.floorStackLabel')"
        @mousedown.stop
      >
        <h3 class="floor-stack-title">{{ t('worldInteraction.map.floorStackLabel') }}</h3>
        <ul class="floor-stack-list">
          <li v-for="floor in mapStore.floorStack" :key="floor.id">
            <button
              type="button"
              class="floor-stack-item"
              :class="floor.status"
              @click="mapStore.drillTo('floor', floor.id)"
            >
              <span class="floor-stack-name">{{ floor.name }}</span>
              <span v-if="floor.status === 'current'" class="floor-stack-badge">
                {{ t('worldInteraction.map.floorStackYouAreHere') }}
              </span>
            </button>
          </li>
        </ul>
      </aside>

      <aside
        v-if="mapStore.viewLayer === 'room' && roomContentPanelGroups.length"
        class="room-content-panels"
        :aria-label="t('worldInteraction.map.roomContentPanelsLabel')"
        @mousedown.stop
      >
        <section
          v-for="group in roomContentPanelGroups"
          :key="group.id"
          class="room-content-panel"
          :class="[group.status, group.logicalZone]"
        >
          <h3 class="room-content-panel-title">{{ group.displayName }}</h3>
          <ul class="group-member-list">
            <li v-for="member in group.groupMembers ?? []" :key="member.id">
              <button
                type="button"
                class="group-member-item"
                :class="member.status"
                @click.stop="mapStore.selectMapTarget(member.id, { viewLayer: 'room' })"
              >
                {{ member.name }}
              </button>
            </li>
          </ul>
        </section>
      </aside>

      <aside
        v-if="mapStore.viewLayer === 'room' && mapStore.roomOccupants.length"
        class="room-occupants-panel"
        :aria-label="t('worldInteraction.map.roomOccupants.title')"
        @mousedown.stop
      >
        <h3 class="room-occupants-title">{{ t('worldInteraction.map.roomOccupants.title') }}</h3>
        <ul class="room-occupants-list">
          <li v-for="person in mapStore.roomOccupants" :key="person.id">
            <button
              type="button"
              class="room-occupant-item"
              :class="person.status"
              @click="mapStore.selectMapTarget(person.id, { viewLayer: 'room' })"
            >
              {{ person.name }}
            </button>
          </li>
        </ul>
      </aside>

      <div class="map-viewport" :style="viewportStyle">
        <div class="map-content" :class="{ 'floor-plan': isFloorPlanLayout }" :style="contentStyle">
          <svg
            v-if="isFloorPlanLayout && floorGridSvgLines.length"
            class="floor-grid-layer"
            :viewBox="svgViewBox"
            preserveAspectRatio="none"
          >
            <line
              v-for="(line, index) in floorGridSvgLines"
              :key="`grid-${index}`"
              :x1="line.x1"
              :y1="line.y1"
              :x2="line.x2"
              :y2="line.y2"
            />
          </svg>

          <svg
            v-if="isFloorPlanLayout && renderFloorPlanTiles.length"
            class="floor-tile-layer"
            :viewBox="svgViewBox"
            preserveAspectRatio="none"
          >
            <g
              v-for="tile in renderFloorPlanTiles"
              :key="tile.id"
              class="floor-tile-group"
              :class="[tile.status, tile.type, tile.roomType, { outdoor: tile.semanticTags?.includes('environment:outdoor') }]"
              role="button"
              tabindex="0"
              @click.stop="mapStore.handleNodeClick(tile)"
              @keydown.enter.prevent="mapStore.handleNodeClick(tile)"
            >
              <polygon :points="tile.sideSouthPoints" class="floor-tile-side floor-tile-side-south" />
              <polygon :points="tile.sideEastPoints" class="floor-tile-side floor-tile-side-east" />
              <polygon :points="tile.topPoints" class="floor-tile-top" />
              <text
                :x="tile.labelX"
                :y="tile.labelY"
                class="floor-tile-label"
                text-anchor="middle"
                dominant-baseline="middle"
              >
                {{ tile.displayName }}
              </text>
            </g>
          </svg>

          <svg class="path-layer" :viewBox="svgViewBox" preserveAspectRatio="none">
            <ellipse
              v-if="logicalHubRing"
              :cx="logicalHubRing.cx"
              :cy="logicalHubRing.cy"
              :rx="logicalHubRing.rx"
              :ry="logicalHubRing.ry"
              class="logical-hub-ring"
            />
            <path
              v-for="edge in renderEdges"
              v-show="edge.pathD"
              :key="`path-${edge.id}`"
              :d="edge.pathD"
              fill="none"
              :class="['edge', edge.status, edge.className]"
              :title="edge.title"
            />
            <line
              v-for="edge in renderEdges"
              v-show="!edge.pathD"
              :key="edge.id"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              :class="['edge', edge.status, edge.className]"
              :title="edge.title"
            />
            <text
              v-for="edge in labeledRenderEdges"
              :key="`label-${edge.id}`"
              :x="edge.labelX"
              :y="edge.labelY"
              class="edge-label"
              text-anchor="middle"
              dominant-baseline="middle"
            >
              {{ edge.directionText }}
            </text>
          </svg>

          <button
            v-for="node in renderNodes"
            :key="`node-${node.id}`"
            v-show="!isRoomContentGroup(node) && !isFloorPlanTile(node, mapStore.map?.layout)"
            :class="['space-node', node.status, node.type, node.logicalZone, { 'cross-building': node.crossBuilding }]"
            :style="{ left: node.left, top: node.top }"
            type="button"
            @click.stop="mapStore.handleNodeClick(node)"
          >
            <span class="node-dot"></span>
            <span class="node-name">{{ node.displayName }}</span>
          </button>

          <button
            v-for="agent in renderAgents"
            :key="agent.agentId"
            type="button"
            :class="['agent-node', { 'agent-node--floating': agent.floating }]"
            :style="agentStyle(agent)"
            :title="agent.name"
            @click.stop="mapStore.selectAgent(agent.agentId)"
          >
            {{ agent.name.slice(0, 1).toUpperCase() }}
          </button>
        </div>
      </div>
    </div>

      <map-entity-inspect-sheet />

      <div v-if="mapStore.mapLoading" class="map-loading-overlay" aria-live="polite">
        {{ t('worldInteraction.map.loading') }}
      </div>

      <div class="map-minimap" :title="t('worldInteraction.map.minimap')" @mousedown.stop>
        <svg :width="MINIMAP_W" :height="MINIMAP_H" :viewBox="`0 0 ${MINIMAP_W} ${MINIMAP_H}`">
          <rect
            v-for="node in minimapNodes"
            :key="`mini-${node.id}`"
            :x="node.miniX - 2"
            :y="node.miniY - 2"
            width="4"
            height="4"
            :class="['minimap-node', node.status, node.type]"
          />
          <rect
            class="minimap-viewport"
            :x="minimapViewport.x"
            :y="minimapViewport.y"
            :width="minimapViewport.w"
            :height="minimapViewport.h"
          />
        </svg>
      </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ZoomIn,
  ZoomOut,
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { computeFloorPlanBounds, computeMapBounds, isCampusGridLayoutValue, isFloorPlanLayoutValue, isFloorPlanTile, isRoomContentGroup, roomContentGroupLabel, useSemanticMapRender } from '@/composables/useSemanticMapRender'
import { gridCornerToIso } from '@/utils/mapLayout'
import MapEntityInspectSheet from '@/components/map/MapEntityInspectSheet.vue'
import { useWorldMapStore } from '@/stores/worldMap'
import { useWorldSessionStore } from '@/stores/worldSession'
import { COMPASS_ROSE_SIZE } from '@/utils/mapLayout'
import type { RenderedMapAgent } from '@/composables/useSemanticMapRender'

const COORD_UNIT_PX = 10
const BOUNDS_PAD = 14
const MINIMAP_W = 132
const MINIMAP_H = 88
const MINIMAP_PAD = 6

const { t } = useI18n()
const mapStore = useWorldMapStore()
const worldSession = useWorldSessionStore()
const loadError = computed(() => worldSession.error || (worldSession.errorKey ? t(worldSession.errorKey) : ''))

const canvasRef = ref<HTMLElement | null>(null)
const mapStageRef = ref<HTMLElement | null>(null)
provide('mapStageRef', mapStageRef)
const panX = ref(0)
const panY = ref(0)
const userZoom = ref(1)
const fitScale = ref(1)
const isPanning = ref(false)

let panStartX = 0
let panStartY = 0
let panOriginX = 0
let panOriginY = 0

const ROOM_CONTENT_ZONE_ORDER: Record<string, number> = { device: 0, item: 1 }

const spatialNodes = computed(() => {
  if (mapStore.map?.layout === 'logical') {
    return mapStore.nodes.filter(node => !isRoomContentGroup(node))
  }
  return mapStore.nodes
})

const spatialEdges = computed(() => {
  if (mapStore.map?.layout === 'logical') {
    return mapStore.edges.filter(edge => !String(edge.id).startsWith('logical_group_'))
  }
  return mapStore.edges
})

const bounds = computed(() => {
  if (isFloorPlanLayout.value) {
    return computeFloorPlanBounds(mapStore.nodes, BOUNDS_PAD)
  }
  return computeMapBounds(spatialNodes.value, BOUNDS_PAD)
})

const mapLayout = computed(() => mapStore.map?.layout)
const isFloorPlanLayout = computed(() => isFloorPlanLayoutValue(mapLayout.value))
const isCampusGridLayout = computed(() => isCampusGridLayoutValue(mapLayout.value))
const isLogicalRoomLayout = computed(() => mapLayout.value === 'logical')

const {
  renderNodes,
  renderFloorPlanTiles,
  renderEdges,
  labeledRenderEdges,
  renderAgents,
  minimapNodes,
  minimapScale,
  logicalHubRing,
} = useSemanticMapRender({
  nodes: spatialNodes,
  edges: spatialEdges,
  agentPresences: computed(() => mapStore.agentPresences),
  bounds,
  coordUnitPx: COORD_UNIT_PX,
  minimapW: MINIMAP_W,
  minimapH: MINIMAP_H,
  minimapPad: MINIMAP_PAD,
  layout: mapLayout,
  t,
})

const roomContentPanelGroups = computed(() => {
  if (!isLogicalRoomLayout.value) return []
  return mapStore.nodes
    .filter(node => isRoomContentGroup(node))
    .map(node => ({
      ...node,
      displayName: roomContentGroupLabel(node, t),
    }))
    .sort((a, b) => {
      const left = ROOM_CONTENT_ZONE_ORDER[a.logicalZone ?? ''] ?? 9
      const right = ROOM_CONTENT_ZONE_ORDER[b.logicalZone ?? ''] ?? 9
      return left - right
    })
})

const floorGridSvgLines = computed(() => {
  const grid = mapStore.floorGridBounds
  if (!grid || !isFloorPlanLayout.value) {
    return [] as Array<{ x1: number; y1: number; x2: number; y2: number }>
  }
  const { minX, minY } = bounds.value
  const scale = COORD_UNIT_PX
  const { minCol, maxCol, minRow, maxRow } = grid
  const lines: Array<{ x1: number; y1: number; x2: number; y2: number }> = []
  const toPx = (point: { x: number; y: number }) => ({
    x: (point.x - minX) * scale,
    y: (point.y - minY) * scale,
  })
  for (let col = minCol; col <= maxCol; col += 1) {
    const a = toPx(gridCornerToIso(col, minRow))
    const b = toPx(gridCornerToIso(col, maxRow))
    lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y })
  }
  for (let row = minRow; row <= maxRow; row += 1) {
    const a = toPx(gridCornerToIso(minCol, row))
    const b = toPx(gridCornerToIso(maxCol, row))
    lines.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y })
  }
  return lines
})

const mapLayoutKey = computed(() => {
  const nodes = spatialNodes.value
  if (!nodes.length) return ''
  return `${mapStore.viewLayer}:${nodes.length}:${nodes.map(node => `${node.id}@${node.x},${node.y}`).join('|')}`
})

const contentWidthPx = computed(() => bounds.value.width * COORD_UNIT_PX)
const contentHeightPx = computed(() => bounds.value.height * COORD_UNIT_PX)

const contentStyle = computed(() => ({
  width: `${contentWidthPx.value}px`,
  height: `${contentHeightPx.value}px`,
}))

const svgViewBox = computed(() => `0 0 ${contentWidthPx.value} ${contentHeightPx.value}`)

const effectiveScale = computed(() => fitScale.value * userZoom.value)

const viewportStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${effectiveScale.value})`,
}))

const zoomPercent = computed(() => Math.round(userZoom.value * 100))

const logicalZoneHint = computed(() => {
  const items = t('worldInteraction.map.logicalZones.items')
  const dev = t('worldInteraction.map.logicalZones.devices')
  const exits = t('worldInteraction.map.logicalZones.exits')
  return `${items} · ${dev} · ${exits}`
})

const minimapViewport = computed(() => {
  const canvas = canvasRef.value
  if (!canvas || !contentWidthPx.value || !contentHeightPx.value) {
    return { x: MINIMAP_PAD, y: MINIMAP_PAD, w: MINIMAP_W - MINIMAP_PAD * 2, h: MINIMAP_H - MINIMAP_PAD * 2 }
  }
  const viewW = canvas.clientWidth / effectiveScale.value / COORD_UNIT_PX
  const viewH = canvas.clientHeight / effectiveScale.value / COORD_UNIT_PX
  const viewX = -panX.value / effectiveScale.value / COORD_UNIT_PX + bounds.value.minX
  const viewY = -panY.value / effectiveScale.value / COORD_UNIT_PX + bounds.value.minY
  const s = minimapScale.value
  return {
    x: MINIMAP_PAD + (viewX - bounds.value.minX) * s,
    y: MINIMAP_PAD + (viewY - bounds.value.minY) * s,
    w: Math.max(8, viewW * s),
    h: Math.max(8, viewH * s),
  }
})

const agentStyle = (agent: RenderedMapAgent) => {
  if (agent.floating) {
    return { right: agent.right, bottom: agent.bottom }
  }
  return { left: agent.left, top: agent.top }
}

const clampUserZoom = (value: number) => Math.min(3, Math.max(0.35, value))

const fitView = () => {
  const canvas = canvasRef.value
  if (!canvas || !contentWidthPx.value || !contentHeightPx.value) return
  const cw = canvas.clientWidth
  const ch = canvas.clientHeight
  const scale = Math.min(cw / contentWidthPx.value, ch / contentHeightPx.value) * 0.9
  fitScale.value = scale
  panX.value = (cw - contentWidthPx.value * scale * userZoom.value) / 2
  panY.value = (ch - contentHeightPx.value * scale * userZoom.value) / 2
}

const resetView = () => {
  userZoom.value = 1
  nextTick(() => fitView())
}

const zoomBy = (factor: number) => {
  const canvas = canvasRef.value
  if (!canvas) return
  const prevScale = effectiveScale.value
  const centerX = canvas.clientWidth / 2
  const centerY = canvas.clientHeight / 2
  const worldX = (centerX - panX.value) / prevScale
  const worldY = (centerY - panY.value) / prevScale
  userZoom.value = clampUserZoom(userZoom.value * factor)
  const nextScale = effectiveScale.value
  panX.value = centerX - worldX * nextScale
  panY.value = centerY - worldY * nextScale
}

const panBy = (dx: number, dy: number) => {
  panX.value += dx
  panY.value += dy
}

const onWheel = (event: WheelEvent) => {
  zoomBy(event.deltaY < 0 ? 1.12 : 0.9)
}

let panGestureMoved = false

const onPanStart = (event: MouseEvent) => {
  if (event.button !== 0) return
  const target = event.target
  if (target instanceof Element && target.closest('[data-testid="map-inspect-sheet"]')) return
  panGestureMoved = false
  isPanning.value = true
  panStartX = event.clientX
  panStartY = event.clientY
  panOriginX = panX.value
  panOriginY = panY.value
  window.addEventListener('mousemove', onPanMove)
  window.addEventListener('mouseup', onPanEnd)
}

const onPanMove = (event: MouseEvent) => {
  if (Math.abs(event.clientX - panStartX) > 4 || Math.abs(event.clientY - panStartY) > 4) {
    panGestureMoved = true
  }
  panX.value = panOriginX + (event.clientX - panStartX)
  panY.value = panOriginY + (event.clientY - panStartY)
}

const onCanvasMouseUp = (event: MouseEvent) => {
  if (event.button !== 0 || panGestureMoved) return
  if (event.target === canvasRef.value) {
    mapStore.clearMapSelection()
  }
}

const onPanEnd = () => {
  isPanning.value = false
  window.removeEventListener('mousemove', onPanMove)
  window.removeEventListener('mouseup', onPanEnd)
}

watch(
  () => [mapLayoutKey.value, worldSession.loading, mapStore.mapLoading] as const,
  ([layoutKey, sessionLoading, mapLoading]) => {
    if (!sessionLoading && !mapLoading && layoutKey) {
      nextTick(() => resetView())
    }
  },
)

onMounted(() => {
  nextTick(() => {
    resetView()
    if (typeof ResizeObserver !== 'undefined' && canvasRef.value) {
      resizeObserver = new ResizeObserver(() => fitView())
      resizeObserver.observe(canvasRef.value)
    }
  })
})

let resizeObserver: ResizeObserver | null = null

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('mousemove', onPanMove)
  window.removeEventListener('mouseup', onPanEnd)
})
</script>

<style scoped>
.map-panel {
  display: flex;
  flex-direction: column;
  min-height: 360px;
  height: 100%;
}

.region-menu {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  flex-shrink: 0;
}

.region-menu h2 {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
}

.region-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  flex-wrap: wrap;
  justify-content: flex-end;
}

.map-breadcrumb {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 6px var(--spacing-lg);
  border-bottom: 1px solid var(--border-color);
  background: rgba(20, 24, 29, 0.6);
}

.breadcrumb-item {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  padding: 0;
}

.breadcrumb-item.active {
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}

.breadcrumb-sep {
  margin-left: 4px;
  color: var(--text-tertiary);
}

.map-body {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.map-stage {
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.floor-plan-hint {
  margin: 0;
  padding: 6px var(--spacing-lg);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  border-bottom: 1px solid var(--border-color);
}

.floor-room-list {
  list-style: none;
  margin: 0;
  padding: var(--spacing-sm) var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 220px;
  overflow-y: auto;
  border-bottom: 1px solid var(--border-color);
}

.floor-room-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  padding: 6px 10px;
  cursor: pointer;
}

.floor-room-item.current,
.floor-room-item.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.compass-rose {
  position: absolute;
  top: var(--spacing-sm);
  left: var(--spacing-sm);
  z-index: 3;
  pointer-events: none;
}

.compass-n {
  fill: var(--text-tertiary);
  font-size: 8px;
  font-weight: 700;
}

.map-canvas {
  position: relative;
  flex: 1;
  min-height: 420px;
  overflow: hidden;
  background: #14181d;
  cursor: grab;
  touch-action: none;
}

.map-canvas.is-panning {
  cursor: grabbing;
}

.map-canvas.is-loading {
  pointer-events: none;
}

.map-loading-overlay {
  position: absolute;
  inset: 0;
  z-index: 4;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 24, 29, 0.55);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  pointer-events: none;
}

.map-toolbar {
  position: absolute;
  top: var(--spacing-sm);
  right: var(--spacing-sm);
  z-index: 3;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: 4px;
  border-radius: var(--radius-md);
  background: rgba(23, 26, 32, 0.92);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(6px);
}

.room-occupants-panel {
  position: absolute;
  top: calc(48px + var(--spacing-sm));
  right: var(--spacing-sm);
  z-index: 3;
  min-width: 148px;
  max-width: 220px;
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: rgba(23, 26, 32, 0.92);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(6px);
}

.room-occupants-title {
  margin: 0 0 6px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
}

.room-occupants-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 160px;
  overflow-y: auto;
}

.room-occupant-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  padding: 5px 8px;
  cursor: pointer;
}

.room-occupant-item.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.room-occupant-item:hover {
  border-color: rgba(230, 162, 60, 0.65);
  color: var(--text-primary);
}

.room-content-panels {
  position: absolute;
  top: calc(48px + var(--spacing-sm));
  left: var(--spacing-sm);
  z-index: 3;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 148px;
  max-width: 200px;
  max-height: calc(100% - 72px);
  overflow-y: auto;
}

.room-content-panel {
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: rgba(23, 26, 32, 0.92);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(6px);
}

.room-content-panel.device {
  border-color: rgba(103, 194, 58, 0.55);
}

.room-content-panel.item {
  border-color: rgba(144, 147, 153, 0.55);
}

.room-content-panel.active {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35);
}

.room-content-panel-title {
  margin: 0 0 6px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
}

.zoom-label {
  min-width: 40px;
  text-align: center;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.map-viewport {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
  will-change: transform;
}

.map-content.floor-plan {
  background: radial-gradient(ellipse at 50% 20%, rgba(64, 158, 255, 0.06), transparent 55%), #14181d;
}

.floor-grid-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}

.floor-grid-layer line {
  stroke: rgba(255, 255, 255, 0.08);
  stroke-width: 1;
}

.floor-tile-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  z-index: 1;
}

.floor-tile-group {
  cursor: pointer;
}

.floor-tile-side {
  stroke: rgba(0, 0, 0, 0.35);
  stroke-width: 0.5;
}

.floor-tile-side-south {
  fill: rgba(18, 22, 28, 0.95);
}

.floor-tile-side-east {
  fill: rgba(26, 31, 38, 0.95);
}

.floor-tile-top {
  fill: rgba(34, 40, 48, 0.96);
  stroke: rgba(255, 255, 255, 0.24);
  stroke-width: 1;
  transition: fill 0.15s ease, stroke 0.15s ease;
}

.floor-tile-group.circulation .floor-tile-top {
  fill: rgba(30, 36, 44, 0.82);
  stroke: rgba(255, 255, 255, 0.16);
  stroke-dasharray: 4 3;
}

.floor-tile-group.outdoor .floor-tile-top,
.floor-tile-group.plaza .floor-tile-top,
.floor-tile-group.gate .floor-tile-top,
.floor-tile-group.bridge .floor-tile-top {
  fill: rgba(32, 58, 78, 0.88);
  stroke: rgba(103, 194, 255, 0.5);
}

.floor-tile-group.current .floor-tile-top,
.floor-tile-group.active .floor-tile-top {
  fill: rgba(40, 62, 92, 0.95);
  stroke: var(--color-primary);
  stroke-width: 1.5;
}

.floor-tile-group:hover .floor-tile-top {
  fill: rgba(48, 56, 66, 0.98);
  stroke: rgba(255, 255, 255, 0.38);
}

.floor-tile-label {
  fill: var(--text-secondary);
  font-size: 9px;
  pointer-events: none;
  user-select: none;
}

.floor-tile-group.current .floor-tile-label,
.floor-tile-group.active .floor-tile-label {
  fill: var(--color-primary);
  font-weight: 600;
}

.floor-stack-panel {
  position: absolute;
  top: calc(48px + var(--spacing-sm));
  left: calc(36px + var(--spacing-md));
  z-index: 3;
  min-width: 132px;
  max-width: 180px;
  max-height: calc(100% - 72px);
  padding: 8px 10px;
  border-radius: var(--radius-md);
  background: rgba(23, 26, 32, 0.92);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(6px);
  overflow-y: auto;
}

.floor-stack-title {
  margin: 0 0 6px;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
}

.floor-stack-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.floor-stack-item {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  border: 1px solid var(--border-color);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  padding: 5px 8px;
  cursor: pointer;
  text-align: left;
}

.floor-stack-item.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.floor-stack-item.current {
  border-color: rgba(230, 162, 60, 0.65);
}

.floor-stack-item:hover {
  border-color: rgba(255, 255, 255, 0.28);
  color: var(--text-primary);
}

.floor-stack-badge {
  font-size: 9px;
  color: rgba(230, 162, 60, 0.9);
}

.map-content {
  position: relative;
  background:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
  background-size: 28px 28px;
}

.path-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 2;
}

.edge {
  stroke: rgba(255, 255, 255, 0.22);
  stroke-width: 2;
}

.edge.recommended {
  stroke: var(--color-primary);
  stroke-width: 3;
}

.edge.edge-vertical {
  stroke-dasharray: 6 4;
  stroke: rgba(255, 196, 64, 0.75);
}

.edge.locked {
  stroke-dasharray: 4 4;
  stroke: rgba(255, 255, 255, 0.14);
  opacity: 0.55;
}

.edge.cross-building,
.edge.edge-cross-building {
  stroke-dasharray: 5 3;
  stroke: rgba(103, 194, 255, 0.85);
}

.edge.edge-campus-spine {
  stroke: rgba(103, 194, 255, 0.72);
  stroke-width: 2.5;
}

.edge.edge-campus-inter-building {
  stroke-dasharray: 6 4;
  stroke: rgba(230, 162, 60, 0.82);
  stroke-width: 2.5;
}

.edge.edge-campus-connector {
  stroke: rgba(103, 194, 58, 0.78);
  stroke-width: 2.5;
}

.map-canvas.layout-campus-grid .path-layer {
  z-index: 1;
}

.map-canvas.layout-campus-grid .space-node {
  z-index: 3;
}

.map-canvas.layout-campus-grid .map-content {
  background-size: 32px 32px;
}

.map-canvas.layout-campus-grid .space-node.building {
  z-index: 3;
  min-width: 92px;
  font-weight: 600;
  border-color: rgba(230, 162, 60, 0.65);
  background: rgba(29, 34, 41, 0.96);
}

.map-canvas.layout-campus-grid .space-node.room {
  z-index: 4;
  min-width: 84px;
  border-color: rgba(103, 194, 255, 0.6);
  background: rgba(26, 32, 40, 0.98);
  box-shadow: 0 0 0 1px rgba(103, 194, 255, 0.15);
}

.map-canvas.layout-campus-grid .edge-label {
  fill: rgba(255, 255, 255, 0.88);
  font-size: 9px;
  paint-order: stroke;
  stroke: rgba(17, 20, 24, 0.85);
  stroke-width: 2px;
}

.edge-label {
  fill: rgba(255, 255, 255, 0.78);
  font-size: 10px;
  pointer-events: none;
}

.logical-hub-ring {
  fill: rgba(64, 158, 255, 0.05);
  stroke: rgba(64, 158, 255, 0.2);
  stroke-width: 1.5;
}

.space-node.active {
  border-color: #e6a23c;
  box-shadow: 0 0 0 1px rgba(230, 162, 60, 0.45);
}

.map-canvas.layout-logical .space-node.cluster {
  min-width: 96px;
  justify-content: center;
  font-weight: var(--font-weight-semibold);
}

.map-canvas.layout-logical .space-node.cluster.occupant {
  border-color: rgba(230, 162, 60, 0.7);
}

.map-canvas.layout-logical .space-node.cluster.device {
  border-color: rgba(103, 194, 58, 0.65);
}

.map-canvas.layout-logical .space-node.cluster.item {
  border-color: rgba(144, 147, 153, 0.65);
}

.group-title {
  margin: 0;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--text-secondary);
  text-align: center;
}

.group-member-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  max-height: 120px;
  overflow-y: auto;
}

.group-member-item {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-secondary);
  font-size: 10px;
  line-height: 1.3;
  padding: 4px 6px;
  cursor: pointer;
}

.group-member-item.active {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.group-member-item:hover {
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.28);
}

.space-node.cluster {
  border-style: dashed;
}

.space-node.cross-building {
  border-color: rgba(103, 194, 255, 0.75);
  box-shadow: 0 0 0 1px rgba(103, 194, 255, 0.35);
}

.map-minimap {
  position: absolute;
  right: var(--spacing-sm);
  bottom: var(--spacing-sm);
  z-index: 3;
  padding: 4px;
  border-radius: var(--radius-md);
  background: rgba(23, 26, 32, 0.92);
  border: 1px solid var(--border-color);
  pointer-events: none;
}

.minimap-node {
  fill: rgba(255, 255, 255, 0.45);
}

.minimap-node.current,
.minimap-node.active {
  fill: var(--color-primary);
}

.minimap-node.cluster {
  fill: rgba(230, 162, 60, 0.8);
}

.minimap-viewport {
  fill: none;
  stroke: rgba(64, 158, 255, 0.85);
  stroke-width: 1.5;
}

.map-canvas.mode-agent .agent-node {
  border: 0;
  cursor: pointer;
  box-shadow: 0 0 0 2px rgba(103, 194, 58, 0.55);
}

.map-canvas.mode-route .edge.recommended {
  stroke-width: 4;
}

.space-node {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  max-width: 180px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 6px 8px;
  background: #1d2229;
  color: var(--text-primary);
  cursor: pointer;
  z-index: 1;
}

.space-node.current {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px rgba(64, 158, 255, 0.35);
}

.node-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  flex-shrink: 0;
}

.node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--font-size-xs);
}

.agent-node {
  border: 0;
  cursor: pointer;
  position: absolute;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-success);
  color: #0b120d;
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-xs);
  z-index: 2;
  transform: translate(-50%, -50%);
  border: 2px solid #14181d;
}

.agent-node--floating {
  transform: none;
}

.empty {
  padding: var(--spacing-xl);
  color: var(--text-tertiary);
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.empty.error {
  color: var(--color-danger);
}

.logical-zone-hint {
  margin: 0 0 var(--spacing-sm);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}

.map-canvas.layout-logical .space-node.room {
  border-color: rgba(64, 158, 255, 0.65);
  font-weight: 600;
}

.map-canvas.layout-logical .space-node.object {
  border-color: rgba(144, 147, 153, 0.55);
  background: rgba(38, 42, 48, 0.95);
}

.map-canvas.layout-logical .space-node.device {
  border-color: rgba(103, 194, 58, 0.55);
}

.map-canvas.layout-logical .space-node.agent {
  border-color: rgba(230, 162, 60, 0.65);
}

.map-canvas.layout-logical .space-node.world,
.map-canvas.layout-logical .space-node.hub {
  z-index: 3;
  min-width: 96px;
  padding: 10px 12px;
  border-color: rgba(64, 158, 255, 0.75);
  background: rgba(29, 34, 41, 0.96);
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.12);
}

.map-canvas.layout-logical .space-node.hub .node-dot {
  width: 10px;
  height: 10px;
  box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.18);
}

.map-canvas.layout-logical .space-node.exit {
  z-index: 2;
}

@media (max-width: 980px) {
  .map-canvas {
    min-height: 280px;
  }

  .map-toolbar {
    flex-wrap: wrap;
    max-width: calc(100% - 16px);
  }
}
</style>
