<template>
  <section class="map-panel">
    <div class="region-menu">
      <h2>{{ t('worldInteraction.map.title') }}</h2>
      <div class="region-actions">
        <el-button size="small" text @click="mapStore.switchMapMode('route')">Route</el-button>
        <el-button size="small" text @click="mapStore.switchMapMode('agent')">Agent</el-button>
        <el-dropdown>
          <el-button size="small" text>
            <el-icon><More /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="mapStore.switchMapMode('focus')">Current focus</el-dropdown-item>
              <el-dropdown-item @click="mapStore.switchMapMode('event')">Events</el-dropdown-item>
              <el-dropdown-item divided @click="resetView">{{ t('worldInteraction.map.resetView') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <div v-if="worldSession.loading" class="empty">{{ t('worldInteraction.map.loading') }}</div>
    <div v-else-if="worldSession.error" class="empty error">
      <p>{{ worldSession.error }}</p>
      <el-button size="small" @click="worldSession.loadCurrent">{{ t('common.retry') }}</el-button>
    </div>
    <div v-else-if="!mapStore.map" class="empty">{{ t('worldInteraction.map.noData') }}</div>
    <div v-else-if="!mapStore.nodes.length" class="empty">{{ t('worldInteraction.map.empty') }}</div>
    <div
      v-else
      ref="canvasRef"
      class="map-canvas"
      :class="{ 'is-panning': isPanning }"
      @wheel.prevent="onWheel"
      @mousedown="onPanStart"
    >
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
              :class="['edge', edge.status]"
            />
          </svg>

          <button
            v-for="node in mapStore.nodes"
            :key="node.id"
            :class="['space-node', node.status, node.type]"
            :style="nodeStyle(node)"
            type="button"
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
import type { AgentMapPresence, SemanticMapNode } from '@/types/world'

const COORD_UNIT_PX = 10
const BOUNDS_PAD = 14

const { t } = useI18n()
const mapStore = useWorldMapStore()
const worldSession = useWorldSessionStore()

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

const toLocal = (x: number, y: number) => ({
  x: (x - bounds.value.minX) * COORD_UNIT_PX,
  y: (y - bounds.value.minY) * COORD_UNIT_PX,
})

const nodePx = (id: string) => {
  const node = mapStore.nodes.find(item => item.id === id)
  if (!node) return { x: 0, y: 0 }
  return toLocal(node.x, node.y)
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
