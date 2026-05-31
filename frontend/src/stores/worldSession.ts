import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ElMessage } from 'element-plus'
import { worldSessionsApi, type ActionResponse } from '@/api/worldSessions'
import { decisionCenterApi } from '@/api/decisionCenter'
import type { DisplayPolicy, QueryMode, StatePatch, ViewMode, WorldInteractionState, WorldSummary } from '@/types/world'

export const useWorldSessionStore = defineStore('worldSession', () => {
  const interactionState = ref<WorldInteractionState | null>(null)
  const displayPolicy = ref<DisplayPolicy | null>(null)
  const availableWorlds = ref<WorldSummary[]>([])
  const loading = ref(false)
  const actionLoading = ref(false)
  const error = ref<string | null>(null)
  const viewMode = ref<ViewMode>('Focus')
  const queryMode = ref<QueryMode>('command')
  const historyItems = ref<Array<{ id: string; summary: string; createdAt: string }>>([])
  const queryCards = ref<Array<{ id: string; title: string; answer: string; mode: QueryMode }>>([])

  const session = computed(() => interactionState.value?.session || null)
  const decisionCenter = computed(() => interactionState.value?.decision_center || null)
  const focusMap = computed(() => interactionState.value?.focus_map || null)
  const contextSummary = computed(() => interactionState.value?.context_summary || null)
  const currentWorld = computed(() => availableWorlds.value.find(world => world.is_current) || null)

  async function loadCurrent() {
    loading.value = true
    error.value = null
    try {
      const { data } = await worldSessionsApi.getCurrent()
      interactionState.value = data.interaction_state
      displayPolicy.value = data.display_policy
      availableWorlds.value = data.available_worlds
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      if (typeof detail === 'string') {
        error.value = detail
      } else if (Array.isArray(detail)) {
        error.value = detail.map((item: { msg?: string }) => item.msg).filter(Boolean).join('; ') || 'Failed to load CampusWorld'
      } else {
        error.value = err?.message || 'Failed to load CampusWorld'
      }
    } finally {
      loading.value = false
    }
  }

  async function refreshInteractionState() {
    if (!session.value?.id) {
      await loadCurrent()
      return
    }
    const { data } = await worldSessionsApi.getInteractionState(session.value.id)
    interactionState.value = data
  }

  async function enterWorld(worldId: string) {
    const { data } = await runAction(() => worldSessionsApi.enterWorld(worldId))
    applyActionResponse(data)
    await loadCurrent()
  }

  async function leaveWorld() {
    const { data } = await runAction(() => worldSessionsApi.leaveWorld())
    applyActionResponse(data)
    await loadCurrent()
  }

  async function executeDecisionAction(decisionEventId: string, optionId: string) {
    if (!session.value?.id) return
    const { data } = await runAction(() => decisionCenterApi.executeAction(session.value!.id, decisionEventId, optionId))
    applyActionResponse(data)
    await loadCurrent()
  }

  async function submitQuery(query: string) {
    if (!session.value?.id) return
    actionLoading.value = true
    try {
      const { data } = await decisionCenterApi.query(session.value.id, query, queryMode.value)
      queryCards.value.unshift({
        id: `${Date.now()}`,
        title: query,
        answer: data.answer,
        mode: data.mode,
      })
      if (queryCards.value.length > 3) queryCards.value = queryCards.value.slice(0, 3)
    } catch (err: any) {
      ElMessage.error(err?.response?.data?.detail || 'Query failed')
    } finally {
      actionLoading.value = false
    }
  }

  function setViewMode(mode: ViewMode) {
    viewMode.value = mode
  }

  function setQueryMode(mode: QueryMode) {
    queryMode.value = mode
  }

  function applyActionResponse(response: ActionResponse) {
    if (!response.success) {
      ElMessage.warning(response.result.summary)
    } else if (response.result.summary) {
      ElMessage.success(response.result.summary)
    }
    applyStatePatch(response.state_patch)
  }

  function applyStatePatch(patch?: StatePatch) {
    if (!patch || !interactionState.value) return
    if (patch.focusSummary) interactionState.value.decision_center.focus = patch.focusSummary
    if (patch.activeTask !== undefined) interactionState.value.decision_center.activeTask = patch.activeTask
    if (patch.newDecisionEvents) interactionState.value.decision_center.decisionEvents = patch.newDecisionEvents
    if (patch.resolvedDecisionEventIds?.length) {
      const resolved = new Set(patch.resolvedDecisionEventIds)
      interactionState.value.decision_center.decisionEvents =
        interactionState.value.decision_center.decisionEvents.filter(event => !resolved.has(event.id))
    }
    if (patch.contextSummary) interactionState.value.context_summary = patch.contextSummary
    if (patch.mapPatch?.mode) interactionState.value.focus_map.mode = patch.mapPatch.mode
    if (patch.mapPatch?.highlightedPath) interactionState.value.focus_map.highlightedPath = patch.mapPatch.highlightedPath
    if (patch.mapPatch?.visibleNodeIds?.length && interactionState.value.focus_map.nodes.length) {
      const visible = new Set(patch.mapPatch.visibleNodeIds)
      interactionState.value.focus_map.nodes = interactionState.value.focus_map.nodes.map(node => ({
        ...node,
        status: visible.has(node.id) ? node.status : 'visible',
      }))
    }
    if (patch.historyAppend) historyItems.value = [...patch.historyAppend, ...historyItems.value].slice(0, 20)
    if (patch.currentSpaceId) interactionState.value.session.currentSpaceId = patch.currentSpaceId
  }

  async function runAction<T>(fn: () => Promise<T>): Promise<T> {
    actionLoading.value = true
    try {
      return await fn()
    } finally {
      actionLoading.value = false
    }
  }

  function reset() {
    interactionState.value = null
    displayPolicy.value = null
    availableWorlds.value = []
    loading.value = false
    actionLoading.value = false
    error.value = null
    viewMode.value = 'Focus'
    queryMode.value = 'command'
    historyItems.value = []
    queryCards.value = []
  }

  return {
    interactionState,
    displayPolicy,
    availableWorlds,
    loading,
    actionLoading,
    error,
    viewMode,
    queryMode,
    historyItems,
    queryCards,
    session,
    decisionCenter,
    focusMap,
    contextSummary,
    currentWorld,
    loadCurrent,
    refreshInteractionState,
    enterWorld,
    leaveWorld,
    executeDecisionAction,
    submitQuery,
    setViewMode,
    setQueryMode,
    applyStatePatch,
    reset,
  }
})
