import { computed, onBeforeUnmount, ref, type ComputedRef, type Ref } from 'vue'

export type DecisionFoldMode = 'collapsed' | 'split' | 'maximized'

export const DEFAULT_TASK_SPLIT_RATIO = 0.35
export const DRAG_CLICK_THRESHOLD_PX = 4
export const SNAP_TO_MAXIMIZED_RATIO = 0.85
export const SNAP_TO_COLLAPSED_RATIO = 0.12
export const HINGE_HEIGHT_PX = 18

export function nextFoldMode(mode: DecisionFoldMode): DecisionFoldMode {
  if (mode === 'collapsed') return 'split'
  if (mode === 'split') return 'maximized'
  return 'collapsed'
}

export function resolveDragRatio(ratio: number): { mode: DecisionFoldMode; ratio: number } {
  if (ratio >= SNAP_TO_MAXIMIZED_RATIO) {
    return { mode: 'maximized', ratio: DEFAULT_TASK_SPLIT_RATIO }
  }
  if (ratio <= SNAP_TO_COLLAPSED_RATIO) {
    return { mode: 'collapsed', ratio: DEFAULT_TASK_SPLIT_RATIO }
  }
  return { mode: 'split', ratio }
}

export function useDecisionFoldLayout(foldRef: Ref<HTMLElement | null>) {
  const foldMode = ref<DecisionFoldMode>('collapsed')
  const taskSplitRatio = ref(DEFAULT_TASK_SPLIT_RATIO)
  const isDragging = ref(false)

  let dragStartY = 0
  let dragStartRatio = 0
  let pointerMoved = false
  let activePointerId: number | null = null
  let captureTarget: HTMLElement | null = null

  const showConversation = computed(() => foldMode.value !== 'maximized')
  const showTaskBody = computed(() => foldMode.value !== 'collapsed')
  const isResizable = computed(() => foldMode.value === 'split')

  const taskZoneStyle = computed(() => {
    if (foldMode.value === 'split') {
      return {
        flex: `0 0 ${Math.round(taskSplitRatio.value * 1000) / 10}%`,
        minHeight: '72px',
      }
    }
    if (foldMode.value === 'maximized') {
      return { flex: '1 1 0', minHeight: '0' }
    }
    return { flex: '0 0 auto' }
  })

  function cycleFoldMode() {
    const next = nextFoldMode(foldMode.value)
    if (next === 'split') {
      taskSplitRatio.value = DEFAULT_TASK_SPLIT_RATIO
    }
    foldMode.value = next
  }

  function collapseToHeader() {
    foldMode.value = 'collapsed'
  }

  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

  function onHingePointerDown(event: PointerEvent) {
    if (event.button !== 0) return
    dragStartY = event.clientY
    dragStartRatio = taskSplitRatio.value
    pointerMoved = false
    activePointerId = event.pointerId
    captureTarget = event.currentTarget as HTMLElement
    captureTarget?.setPointerCapture?.(event.pointerId)
    window.addEventListener('pointermove', onPointerMove)
    window.addEventListener('pointerup', onPointerUp)
    window.addEventListener('pointercancel', onPointerUp)
  }

  function onPointerMove(event: PointerEvent) {
    if (activePointerId !== event.pointerId) return
    if (Math.abs(event.clientY - dragStartY) <= DRAG_CLICK_THRESHOLD_PX) return

    pointerMoved = true
    if (foldMode.value === 'collapsed') {
      foldMode.value = 'split'
      taskSplitRatio.value = DEFAULT_TASK_SPLIT_RATIO
      dragStartRatio = DEFAULT_TASK_SPLIT_RATIO
      dragStartY = event.clientY
    }
    if (foldMode.value === 'maximized') return

    isDragging.value = true
    const foldHeight = foldRef.value?.clientHeight ?? 0
    const available = Math.max(foldHeight - HINGE_HEIGHT_PX, 1)
    const delta = event.clientY - dragStartY
    const nextRatio = clamp(dragStartRatio + delta / available, 0, 1)
    const resolved = resolveDragRatio(nextRatio)
    foldMode.value = resolved.mode
    taskSplitRatio.value = resolved.ratio
  }

  function onPointerUp(event: PointerEvent) {
    if (activePointerId !== event.pointerId) return
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
    window.removeEventListener('pointercancel', onPointerUp)
    try {
      captureTarget?.releasePointerCapture(event.pointerId)
    } catch {
      // pointer may already be released
    }
    captureTarget = null
    activePointerId = null
    isDragging.value = false
    if (!pointerMoved) {
      cycleFoldMode()
    }
  }

  onBeforeUnmount(() => {
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', onPointerUp)
    window.removeEventListener('pointercancel', onPointerUp)
  })

  return {
    foldMode,
    taskSplitRatio,
    taskZoneStyle,
    showConversation,
    showTaskBody,
    isDragging,
    isResizable,
    cycleFoldMode,
    collapseToHeader,
    onHingePointerDown,
  }
}

export type DecisionFoldLayout = {
  foldMode: Ref<DecisionFoldMode>
  taskSplitRatio: Ref<number>
  taskZoneStyle: ComputedRef<Record<string, string>>
  showConversation: ComputedRef<boolean>
  showTaskBody: ComputedRef<boolean>
  isDragging: Ref<boolean>
  isResizable: ComputedRef<boolean>
  cycleFoldMode: () => void
  collapseToHeader: () => void
  onHingePointerDown: (event: PointerEvent) => void
}
