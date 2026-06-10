<template>
  <section class="map-panel">
    <div class="region-menu">
      <h2>{{ t('worldInteraction.map.title') }}</h2>
      <div class="region-actions">
        <el-button size="small" text @click="mapStore.drillTo('campus')">
          {{ t('worldInteraction.map.openFullMap') }}
        </el-button>
        <el-button size="small" text @click="mapStore.drillToCurrentRoom()">
          {{ t('worldInteraction.map.backToRoom') }}
        </el-button>
        <el-button size="small" text @click="mapStore.switchMapMode('route')">
          {{ t('worldInteraction.map.mode.route') }}
        </el-button>
        <el-button size="small" text @click="mapStore.switchMapMode('agent')">
          {{ t('worldInteraction.map.mode.agent') }}
        </el-button>
        <el-dropdown>
          <el-button size="small" text>
            <el-icon><More /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="mapStore.switchMapMode('focus')">
                {{ t('worldInteraction.map.mode.focus') }}
              </el-dropdown-item>
              <el-dropdown-item @click="mapStore.switchMapMode('event')">
                {{ t('worldInteraction.map.mode.event') }}
              </el-dropdown-item>
              <el-dropdown-item divided @click="resetView">{{ t('worldInteraction.map.resetView') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <nav v-if="mapStore.breadcrumb.length > 1" class="map-breadcrumb" :aria-label="t('worldInteraction.map.layersLabel')">
      <template v-for="(crumb, index) in mapStore.breadcrumb" :key="`${crumb.layer}-${crumb.id}`">
        <span v-if="index > 0" class="breadcrumb-sep">›</span>
        <button
          type="button"
          class="breadcrumb-item"
          :class="{ active: index === mapStore.breadcrumb.length - 1 }"
          @click="mapStore.drillTo(crumb.layer as MapViewLayer, crumb.id)"
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
            @click="mapStore.selectMapTarget(room.id)"
          >
            {{ room.name }}
          </button>
        </li>
      </ul>
      <div
        v-if="mapStore.nodes.length"
        ref="canvasRef"
        class="map-canvas"
      :class="{ 'is-panning': isPanning, [`mode-${mapStore.mode}`]: true }"
      @wheel.prevent="onWheel"
      @mousedown="onPanStart"
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
          <el-button :title="t('worldInteraction.map.resetView')" @click="resetView">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </el-button-group>
        <span class="zoom-label">{{ zoomPercent }}%</span>
      </div>

      <div class="map-viewport" :style="viewportStyle">
        <div class="map-content" :style="contentStyle">
          <svg class="path-layer" :viewBox="svgViewBox" preserveAspectRatio="none">
            <line
              v-for="edge in mapStore.edges"
              :key="edge.id"
              :x1="nodePx(edge.from).x"
              :y1="nodePx(edge.from).y"
              :x2="nodePx(edge.to).x"
              :y2="nodePx(edge.to).y"
              :class="['edge', edge.status, edgeClass(edge)]"
            />
            <text
              v-for="edge in mapStore.edges"
              :key="`label-${edge.id}`"
              :x="edgeLabelPx(edge).x"
              :y="edgeLabelPx(edge).y"
              class="edge-label"
              text-anchor="middle"
              dominant-baseline="middle"
            >
              {{ directionLabel(edge.direction || edge.label) }}
            </text>
          </svg>

          <button
            v-for="node in mapStore.nodes"
            :key="node.id"
            :class="['space-node', node.status, node.type]"
            :style="nodeStyle(node)"
            type="button"
            @click.stop="mapStore.handleNodeClick(node)"
          >
            <span class="node-dot"></span>
            <span class="node-name">{{ node.name }}</span>
          </button>

          <div
            v-for="agent in mapStore.agentPresences"
            :key="agent.agentId"
            :class="['agent-node', { 'agent-node--floating': !agentAnchor(agent) }]"
            :style="agentStyle(agent)"
            :title="agent.name"
          >
            {{ agent.name.slice(0, 1).toUpperCase() }}
          </div>
        </div>
      </div>

      <div class="map-minimap" :title="t('worldInteraction.map.minimap')" @mousedown.stop>
        <svg :width="MINIMAP_W" :height="MINIMAP_H" :viewBox="`0 0 ${MINIMAP_W} ${MINIMAP_H}`">
          <rect
            v-for="node in mapStore.nodes"
            :key="`mini-${node.id}`"
            :x="toMinimap(node.x, node.y).x - 2"
            :y="toMinimap(node.x, node.y).y - 2"
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  More,
  Refresh,
  ZoomIn,
  ZoomOut,
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useWorldMapStore } from '@/stores/worldMap'
import { useWorldSessionStore } from '@/stores/worldSession'
import { COMPASS_ROSE_SIZE, edgeMidpoint, formatDirectionLabel } from '@/utils/mapLayout'
import type { AgentMapPresence, MapViewLayer, SemanticMapEdge, SemanticMapNode } from '@/types/world'

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
const panX = ref(0)
const panY = ref(0)
const userZoom = ref(1)
const fitScale = ref(1)
const isPanning = ref(false)

let panStartX = 0
let panStartY = 0
let panOriginX = 0
let panOriginY = 0

const bounds = computed(() => {
  const nodes = mapStore.nodes
  if (!nodes.length) {
    return { minX: 0, minY: 0, width: 100, height: 100 }
  }
  const xs = nodes.map(node => node.x)
  const ys = nodes.map(node => node.y)
  const minX = Math.min(...xs) - BOUNDS_PAD
  const minY = Math.min(...ys) - BOUNDS_PAD
  const maxX = Math.max(...xs) + BOUNDS_PAD
  const maxY = Math.max(...ys) + BOUNDS_PAD
  return {
    minX,
    minY,
    width: Math.max(80, maxX - minX),
    height: Math.max(80, maxY - minY),
  }
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

const minimapScale = computed(() => {
  const bw = Math.max(1, bounds.value.width)
  const bh = Math.max(1, bounds.value.height)
  return Math.min((MINIMAP_W - MINIMAP_PAD * 2) / bw, (MINIMAP_H - MINIMAP_PAD * 2) / bh)
})

const toMinimap = (x: number, y: number) => ({
  x: MINIMAP_PAD + (x - bounds.value.minX) * minimapScale.value,
  y: MINIMAP_PAD + (y - bounds.value.minY) * minimapScale.value,
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

const toLocal = (x: number, y: number) => ({
  x: (x - bounds.value.minX) * COORD_UNIT_PX,
  y: (y - bounds.value.minY) * COORD_UNIT_PX,
})

const nodePx = (id: string) => {
  const node = mapStore.nodes.find(item => item.id === id)
  if (!node) return { x: 0, y: 0 }
  return toLocal(node.x, node.y)
}

const edgeLabelPx = (edge: SemanticMapEdge) => {
  const from = nodePx(edge.from)
  const to = nodePx(edge.to)
  return edgeMidpoint(from, to)
}

const directionLabel = (direction?: string) => formatDirectionLabel(direction, t)

const edgeClass = (edge: SemanticMapEdge) => {
  const dir = String(edge.direction || '').toLowerCase()
  return dir === 'up' || dir === 'down' ? 'edge-vertical' : ''
}

const nodeStyle = (node: SemanticMapNode) => {
  const point = toLocal(node.x, node.y)
  return {
    left: `${point.x}px`,
    top: `${point.y}px`,
  }
}

const agentAnchor = (agent: AgentMapPresence) =>
  mapStore.nodes.find(node => node.id === agent.currentSpaceId)

const agentStyle = (agent: AgentMapPresence) => {
  const anchor = agentAnchor(agent)
  if (!anchor) {
    return { right: '12px', bottom: '12px' }
  }
  const point = toLocal(anchor.x, anchor.y)
  return {
    left: `${point.x + 28}px`,
    top: `${point.y - 18}px`,
  }
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

const onPanStart = (event: MouseEvent) => {
  if (event.button !== 0) return
  isPanning.value = true
  panStartX = event.clientX
  panStartY = event.clientY
  panOriginX = panX.value
  panOriginY = panY.value
  window.addEventListener('mousemove', onPanMove)
  window.addEventListener('mouseup', onPanEnd)
}

const onPanMove = (event: MouseEvent) => {
  panX.value = panOriginX + (event.clientX - panStartX)
  panY.value = panOriginY + (event.clientY - panStartY)
}

const onPanEnd = () => {
  isPanning.value = false
  window.removeEventListener('mousemove', onPanMove)
  window.removeEventListener('mouseup', onPanEnd)
}

watch(
  () => [mapStore.nodes, mapStore.edges, worldSession.loading],
  () => {
    if (!worldSession.loading && mapStore.nodes.length) {
      nextTick(() => resetView())
    }
  },
  { deep: true },
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

.edge-label {
  fill: rgba(255, 255, 255, 0.78);
  font-size: 10px;
  pointer-events: none;
}

.space-node.active {
  border-color: #e6a23c;
  box-shadow: 0 0 0 1px rgba(230, 162, 60, 0.45);
}

.space-node.cluster {
  border-style: dashed;
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
