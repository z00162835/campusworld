<template>
  <section
    v-if="mapStore.selectedInspect || mapStore.loadingInspect"
    ref="sheetRef"
    class="map-inspect-sheet"
    :class="{ collapsed: collapsed, loading: mapStore.loadingInspect && !mapStore.selectedInspect, dragging: isDragging }"
    :style="sheetStyle"
    data-testid="map-inspect-sheet"
    @mousedown.stop
  >
    <header class="inspect-header" @mousedown.stop="onDragStart">
      <button type="button" class="inspect-toggle" @click.stop="collapsed = !collapsed">
        <span class="inspect-title">{{ headerTitle }}</span>
        <span v-if="entityKindLabel" class="inspect-kind">{{ entityKindLabel }}</span>
      </button>
      <el-button size="small" text @mousedown.stop @click="mapStore.clearMapSelection()">
        {{ t('worldInteraction.map.inspect.close') }}
      </el-button>
    </header>

    <div v-show="!collapsed" class="inspect-body">
      <div v-if="mapStore.loadingInspect && !mapStore.selectedInspect" class="inspect-skeleton">
        {{ t('worldInteraction.map.inspect.loading') }}
      </div>

      <map-space-summary-card
        v-else-if="mapStore.selectedInspect?.entityKind === 'space'"
        :summary="mapStore.selectedInspect.inspect"
        embedded
      />

      <template v-else-if="entityInspect">
        <div v-if="entityInspect.appearance.lines.length" class="inspect-block">
          <h4>{{ t('worldInteraction.map.inspect.appearance') }}</h4>
          <p v-for="(line, index) in entityInspect.appearance.lines" :key="`line-${index}`">{{ line }}</p>
        </div>

        <div v-if="entityInspect.status?.length" class="inspect-block">
          <h4>{{ t('worldInteraction.map.inspect.status') }}</h4>
          <ul>
            <li v-for="(row, index) in entityInspect.status" :key="`status-${index}`">
              {{ row.label }}: {{ row.value }}
            </li>
          </ul>
        </div>
      </template>

      <div v-if="actions.length" class="inspect-actions">
        <el-button
          v-for="action in actions"
          :key="action.id"
          size="small"
          :type="action.style === 'primary' ? 'primary' : 'default'"
          :loading="runningActionId === action.id"
          @click="runAction(action)"
        >
          {{ action.label }}
        </el-button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, inject, onBeforeUnmount, ref, watch, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useNotification } from '@/composables/useNotification'
import { decisionCenterApi } from '@/api/decisionCenter'
import MapSpaceSummaryCard from '@/components/map/MapSpaceSummaryCard.vue'
import { useWorldMapStore } from '@/stores/worldMap'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { CSSProperties } from 'vue'
import type { DecisionOption, EntityInspectData, MapInspectSelection } from '@/types/world'

const SHEET_WIDTH = 440
const SHEET_MARGIN = 12
const MINIMAP_RESERVE = 88

const { t } = useI18n()
const mapStore = useWorldMapStore()
const worldSession = useWorldSessionStore()
const { confirm } = useNotification()
const mapStageRef = inject<Ref<HTMLElement | null>>('mapStageRef', ref(null))
const collapsed = ref(false)
const runningActionId = ref<string | null>(null)
const sheetRef = ref<HTMLElement | null>(null)
const panelLeft = ref<number | null>(null)
const panelTop = ref<number | null>(null)
const isDragging = ref(false)

let dragStartX = 0
let dragStartY = 0
let dragOriginLeft = 0
let dragOriginTop = 0

const entityInspect = computed<EntityInspectData | null>(() => {
  const sel = mapStore.selectedInspect
  if (!sel || sel.entityKind === 'space') return null
  return sel.inspect
})

function resolveInspectKind(selection: MapInspectSelection): MapInspectSelection['entityKind'] {
  if (selection.entityKind === 'space') return 'space'
  const inspect = selection.inspect
  const typeCode = String(inspect.entity.type_code || '').toLowerCase()
  const mapNodeType = String(inspect.entity.map_node_type || '').toLowerCase()

  if (typeCode === 'npc_agent') return 'agent'
  if (inspect.entity_kind === 'person') return 'person'
  if (typeCode === 'account' || typeCode === 'character' || typeCode === 'user') return 'person'
  if (mapNodeType === 'service') return 'person'
  if (inspect.entity_kind === 'device' || inspect.entity_kind === 'object') return inspect.entity_kind
  return selection.entityKind
}

const headerTitle = computed(() => {
  const sel = mapStore.selectedInspect
  if (!sel) return t('worldInteraction.map.inspect.loading')
  if (sel.entityKind === 'space') return sel.inspect.space_node.name
  return sel.inspect.entity.name
})

const entityKindLabel = computed(() => {
  const sel = mapStore.selectedInspect
  if (!sel || sel.entityKind === 'space') return ''
  const kind = resolveInspectKind(sel)
  return t(`worldInteraction.map.inspect.kind.${kind}`)
})

const actions = computed(() => {
  const sel = mapStore.selectedInspect
  if (!sel || sel.entityKind === 'space') return []
  return sel.inspect.actions.slice(0, 3)
})

const sheetStyle = computed<CSSProperties>(() => {
  if (panelLeft.value !== null && panelTop.value !== null) {
    return {
      left: `${panelLeft.value}px`,
      top: `${panelTop.value}px`,
      bottom: 'auto',
      transform: 'none',
      width: `min(${SHEET_WIDTH}px, calc(100% - ${SHEET_MARGIN * 2}px))`,
    }
  }
  return {
    left: '50%',
    bottom: `${SHEET_MARGIN}px`,
    transform: 'translateX(-50%)',
    width: `min(${SHEET_WIDTH}px, calc(100% - ${MINIMAP_RESERVE}px))`,
  }
})

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function boundaryElement(): HTMLElement | null {
  const stage = mapStageRef.value
  if (stage) return stage
  const parent = sheetRef.value?.offsetParent
  return parent instanceof HTMLElement ? parent : null
}

function resetPanelPosition() {
  panelLeft.value = null
  panelTop.value = null
}

function onDragStart(event: MouseEvent) {
  if (event.button !== 0) return
  const sheet = sheetRef.value
  const parent = boundaryElement()
  if (!sheet || !parent) return

  event.preventDefault()
  isDragging.value = true

  const parentRect = parent.getBoundingClientRect()
  const sheetRect = sheet.getBoundingClientRect()

  if (panelLeft.value === null || panelTop.value === null) {
    panelLeft.value = sheetRect.left - parentRect.left
    panelTop.value = sheetRect.top - parentRect.top
  }

  dragStartX = event.clientX
  dragStartY = event.clientY
  dragOriginLeft = panelLeft.value
  dragOriginTop = panelTop.value

  window.addEventListener('mousemove', onDragMove)
  window.addEventListener('mouseup', onDragEnd)
}

function onDragMove(event: MouseEvent) {
  const sheet = sheetRef.value
  const parent = boundaryElement()
  if (!sheet || !parent || panelLeft.value === null || panelTop.value === null) return

  const maxLeft = Math.max(0, parent.clientWidth - sheet.offsetWidth)
  const maxTop = Math.max(0, parent.clientHeight - sheet.offsetHeight)
  panelLeft.value = clamp(dragOriginLeft + (event.clientX - dragStartX), 0, maxLeft)
  panelTop.value = clamp(dragOriginTop + (event.clientY - dragStartY), 0, maxTop)
}

function onDragEnd() {
  isDragging.value = false
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
}

watch(
  () => mapStore.selectedInspect?.entityId,
  (next, prev) => {
    if (!next || next !== prev) {
      resetPanelPosition()
    }
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onDragMove)
  window.removeEventListener('mouseup', onDragEnd)
})

async function runAction(action: DecisionOption) {
  if (action.actionType !== 'execute_command' || !action.command) return
  const sessionId = worldSession.session?.id
  if (!sessionId) return
  if (action.requiresConfirmation) {
    try {
      await confirm(t('worldInteraction.map.inspect.confirmAction', { label: action.label }))
    } catch {
      return
    }
  }
  runningActionId.value = action.id
  try {
    await decisionCenterApi.query(sessionId, action.command, 'command')
    await mapStore.refreshSelectedInspect()
  } catch (err) {
    console.warn('[MapEntityInspectSheet] action failed:', err)
  } finally {
    runningActionId.value = null
  }
}
</script>

<style scoped>
.map-inspect-sheet {
  position: absolute;
  z-index: 20;
  max-height: min(36%, 320px);
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: rgba(20, 24, 30, 0.96);
  backdrop-filter: blur(8px);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
  touch-action: none;
}

.map-inspect-sheet.collapsed {
  max-height: none;
}

.map-inspect-sheet.dragging {
  user-select: none;
}

.inspect-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-bottom: 1px solid var(--border-color);
  cursor: grab;
}

.map-inspect-sheet.dragging .inspect-header {
  cursor: grabbing;
}

.inspect-toggle {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  border: 0;
  background: transparent;
  color: inherit;
  cursor: inherit;
  text-align: left;
  padding: 0;
  min-width: 0;
  flex: 1;
}

.inspect-title {
  font-weight: 600;
  font-size: var(--font-size-base);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.inspect-kind {
  flex-shrink: 0;
  font-size: var(--font-size-sm);
  opacity: 0.75;
}

.inspect-body {
  overflow: auto;
  padding: var(--spacing-sm);
}

.inspect-skeleton {
  opacity: 0.7;
  font-size: var(--font-size-sm);
}

.inspect-block {
  margin-top: var(--spacing-sm);
}

.inspect-block h4 {
  margin: 0 0 var(--spacing-xs);
  font-size: var(--font-size-sm);
}

.inspect-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-sm);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}
</style>
