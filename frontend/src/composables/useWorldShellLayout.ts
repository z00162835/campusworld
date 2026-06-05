import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch, type Ref } from 'vue'
import type { ViewMode } from '@/types/world'

export const MAP_MIN_WIDTH = 240
export const DECISION_MIN_WIDTH = 320
export const CONTEXT_MIN_WIDTH = 200
export const COLLAPSED_STRIP_WIDTH = 44
const RESIZER_WIDTH = 6

const MODE_RATIOS: Record<ViewMode, { map: number; context: number }> = {
  Focus: { map: 0.4, context: 0.1 },
  Map: { map: 0.7, context: 0.1 },
}

type ResizeTarget = 'map' | 'context'

export function useWorldShellLayout(mainRef: Ref<HTMLElement | null>, viewMode: Ref<ViewMode>) {
  const mapCollapsed = ref(true)
  const contextCollapsed = ref(true)
  const mapWidth = ref(360)
  const contextWidth = ref(240)
  const isResizing = ref(false)

  let resizeTarget: ResizeTarget | null = null
  let resizeStartX = 0
  let resizeStartMapWidth = 0
  let resizeStartContextWidth = 0

  const mapPaneWidth = computed(() => (mapCollapsed.value ? COLLAPSED_STRIP_WIDTH : mapWidth.value))
  const contextPaneWidth = computed(() => (contextCollapsed.value ? COLLAPSED_STRIP_WIDTH : contextWidth.value))

  const showMapResizer = computed(() => !mapCollapsed.value)
  const showContextResizer = computed(() => !contextCollapsed.value)

  const mapPaneStyle = computed(() => ({
    flex: `0 0 ${mapPaneWidth.value}px`,
    width: `${mapPaneWidth.value}px`,
    minWidth: `${mapPaneWidth.value}px`,
    maxWidth: `${mapPaneWidth.value}px`,
  }))

  const contextPaneStyle = computed(() => ({
    flex: `0 0 ${contextPaneWidth.value}px`,
    width: `${contextPaneWidth.value}px`,
    minWidth: `${contextPaneWidth.value}px`,
    maxWidth: `${contextPaneWidth.value}px`,
  }))

  const decisionPaneStyle = computed(() => ({
    flex: '1 1 auto',
    minWidth: `${DECISION_MIN_WIDTH}px`,
  }))

  const totalWidth = () => mainRef.value?.clientWidth ?? 0

  const resizerCount = () => (showMapResizer.value ? 1 : 0) + (showContextResizer.value ? 1 : 0)

  const maxMapWidth = () => {
    const total = totalWidth()
    const contextPart = contextPaneWidth.value
    const resizers = resizerCount() * RESIZER_WIDTH
    return Math.max(MAP_MIN_WIDTH, total - DECISION_MIN_WIDTH - contextPart - resizers)
  }

  const maxContextWidth = () => {
    const total = totalWidth()
    const mapPart = mapPaneWidth.value
    const resizers = resizerCount() * RESIZER_WIDTH
    return Math.max(CONTEXT_MIN_WIDTH, total - DECISION_MIN_WIDTH - mapPart - resizers)
  }

  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

  const applyModeWidths = () => {
    const total = totalWidth()
    if (total <= 0) return
    const ratios = MODE_RATIOS[viewMode.value]
    const resizers = 2 * RESIZER_WIDTH
    const usable = total - resizers - DECISION_MIN_WIDTH
    if (usable <= 0) return
    mapWidth.value = Math.round(clamp(usable * ratios.map, MAP_MIN_WIDTH, maxMapWidth()))
    contextWidth.value = Math.round(clamp(usable * ratios.context, CONTEXT_MIN_WIDTH, maxContextWidth()))
  }

  const startResize = (target: ResizeTarget, event: MouseEvent) => {
    if (event.button !== 0) return
    resizeTarget = target
    resizeStartX = event.clientX
    resizeStartMapWidth = mapWidth.value
    resizeStartContextWidth = contextWidth.value
    isResizing.value = true
    window.addEventListener('mousemove', onResizeMove)
    window.addEventListener('mouseup', stopResize)
  }

  const onResizeMove = (event: MouseEvent) => {
    if (!resizeTarget) return
    const delta = event.clientX - resizeStartX
    if (resizeTarget === 'map') {
      mapWidth.value = clamp(resizeStartMapWidth + delta, MAP_MIN_WIDTH, maxMapWidth())
      return
    }
    contextWidth.value = clamp(resizeStartContextWidth - delta, CONTEXT_MIN_WIDTH, maxContextWidth())
  }

  const stopResize = () => {
    resizeTarget = null
    isResizing.value = false
    window.removeEventListener('mousemove', onResizeMove)
    window.removeEventListener('mouseup', stopResize)
  }

  let resizeObserver: ResizeObserver | null = null

  onMounted(() => {
    nextTick(() => applyModeWidths())
    if (typeof ResizeObserver !== 'undefined' && mainRef.value) {
      resizeObserver = new ResizeObserver(() => {
        mapWidth.value = clamp(mapWidth.value, MAP_MIN_WIDTH, maxMapWidth())
        contextWidth.value = clamp(contextWidth.value, CONTEXT_MIN_WIDTH, maxContextWidth())
      })
      resizeObserver.observe(mainRef.value)
    }
  })

  onBeforeUnmount(() => {
    resizeObserver?.disconnect()
    stopResize()
  })

  watch(viewMode, () => applyModeWidths())

  watch(mapCollapsed, collapsed => {
    if (!collapsed) {
      mapWidth.value = clamp(mapWidth.value, MAP_MIN_WIDTH, maxMapWidth())
    }
  })

  watch(contextCollapsed, collapsed => {
    if (!collapsed) {
      contextWidth.value = clamp(contextWidth.value, CONTEXT_MIN_WIDTH, maxContextWidth())
    }
  })

  function applyMapCollapsedForViewMode() {
    mapCollapsed.value = viewMode.value === 'Focus'
  }

  return {
    mapCollapsed,
    contextCollapsed,
    mapWidth,
    contextWidth,
    isResizing,
    mapPaneStyle,
    contextPaneStyle,
    decisionPaneStyle,
    showMapResizer,
    showContextResizer,
    startResize,
    applyModeWidths,
    applyMapCollapsedForViewMode,
    MAP_MIN_WIDTH,
    DECISION_MIN_WIDTH,
    CONTEXT_MIN_WIDTH,
  }
}
