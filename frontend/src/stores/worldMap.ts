import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { semanticMapApi } from '@/api/semanticMap'
import { useWorldSessionStore } from './worldSession'
import type { FocusMap, MapPatch, MapViewLayer, SemanticMapNode, SpaceSummaryData } from '@/types/world'

export const useWorldMapStore = defineStore('worldMap', () => {
  const worldSession = useWorldSessionStore()
  const selectedSpaceSummary = ref<SpaceSummaryData | null>(null)
  const mapLoading = ref(false)

  const map = computed(() => worldSession.focusMap)
  const mode = computed(() => map.value?.mode || 'focus')
  const viewLayer = computed(() => map.value?.viewLayer || 'room')
  const breadcrumb = computed(() => map.value?.breadcrumb || [])
  const floorPlanReady = computed(() => map.value?.floorPlanReady !== false)
  const floorRoomList = computed(() => map.value?.floorRoomList || [])
  const nodes = computed(() => map.value?.nodes || [])
  const edges = computed(() => map.value?.edges || [])
  const agentPresences = computed(() => map.value?.agentPresences || [])
  const neighborLinks = computed(() => map.value?.neighborLinks || [])
  const selectedEntityId = computed(() => map.value?.selectedEntityId || null)

  function applyFocusMap(focusMap: FocusMap) {
    if (worldSession.interactionState) {
      worldSession.interactionState.focus_map = focusMap
    }
  }

  async function fetchFocus(options?: {
    viewLayer?: string
    anchorId?: string
    mode?: FocusMap['mode']
    selectedEntityId?: string
  }) {
    mapLoading.value = true
    try {
      const { data } = await semanticMapApi.getFocus({
        view_layer: options?.viewLayer,
        anchor_id: options?.anchorId,
        mode: options?.mode ?? mode.value,
        selected_entity_id: options?.selectedEntityId,
      })
      applyFocusMap(data.focus_map)
    } finally {
      mapLoading.value = false
    }
  }

  async function drillTo(layer: MapViewLayer, anchorId?: string) {
    mapLoading.value = true
    selectedSpaceSummary.value = null
    try {
      const { data } = await semanticMapApi.executeAction({
        action_type: 'drill',
        view_layer: layer,
        anchor_id: anchorId,
        mode: mode.value,
      })
      if (data.focus_map) {
        applyFocusMap(data.focus_map)
      }
    } finally {
      mapLoading.value = false
    }
  }

  async function drillUp() {
    const crumbs = breadcrumb.value
    if (crumbs.length <= 1) return
    const parent = crumbs[crumbs.length - 2]
    await drillTo(parent.layer as MapViewLayer, parent.id)
  }

  async function drillToCurrentRoom() {
    const roomCrumb = breadcrumb.value.find(item => item.layer === 'room')
    if (roomCrumb) {
      await drillTo('room', roomCrumb.id)
      return
    }
    await drillTo('room')
  }

  async function switchMapMode(nextMode: FocusMap['mode']) {
    await fetchFocus({ viewLayer: viewLayer.value, mode: nextMode })
  }

  async function selectMapTarget(nodeId: string) {
    mapLoading.value = true
    try {
      const { data } = await semanticMapApi.executeAction({
        action_type: 'select',
        view_layer: viewLayer.value,
        mode: mode.value,
        selected_entity_id: nodeId,
      })
      if (data.focus_map) {
        applyFocusMap(data.focus_map)
      }
      selectedSpaceSummary.value = data.space_summary ?? null
      if (!data.space_summary) {
        const summaryRes = await semanticMapApi.getSpaceSummary(nodeId)
        if (summaryRes.data.ok && summaryRes.data.summary) {
          selectedSpaceSummary.value = summaryRes.data.summary
        }
      }
    } finally {
      mapLoading.value = false
    }
  }

  async function handleNodeClick(node: SemanticMapNode) {
    if (node.type === 'cluster') {
      if (node.id.startsWith('cluster:floor:')) {
        if (node.drillAnchorId) {
          await selectMapTarget(node.drillAnchorId)
        }
        return
      }
      if (node.drillAnchorId) {
        await drillTo('building', node.drillAnchorId)
      }
      return
    }
    if (node.type === 'building') {
      await drillTo('building', node.id)
      return
    }
    if (node.type === 'floor') {
      await drillTo('floor', node.id)
      return
    }
    await selectMapTarget(node.id)
  }

  async function applyMapPatch(patch?: MapPatch) {
    if (!patch) return
    if (patch.focus_map) {
      applyFocusMap(patch.focus_map)
      return
    }
    if (patch.viewLayer) {
      await drillTo(patch.viewLayer, patch.anchorId)
    } else if (patch.mode) {
      await fetchFocus({ viewLayer: viewLayer.value, mode: patch.mode })
    }
    const focus = worldSession.interactionState?.focus_map
    if (!focus) return
    if (patch.highlightedNodeIds?.length) {
      const ids = new Set(patch.highlightedNodeIds)
      focus.nodes = focus.nodes.map(node => ({
        ...node,
        status: ids.has(node.id)
          ? (node.id === focus.currentSpaceId ? 'current' : 'active')
          : (node.id === focus.currentSpaceId ? 'current' : 'visible'),
      }))
      focus.selectedEntityId = patch.highlightedNodeIds[0] ?? null
    }
    if (patch.highlightedPath) {
      focus.highlightedPath = patch.highlightedPath
    }
    if (patch.mode) {
      focus.mode = patch.mode
    }
    if (patch.agentPresences?.length) {
      const byId = new Map(focus.agentPresences.map(agent => [agent.agentId, agent]))
      for (const agent of patch.agentPresences) {
        byId.set(agent.agentId, agent)
      }
      focus.agentPresences = Array.from(byId.values())
    }
  }

  async function searchMap(query: string) {
    const { data } = await semanticMapApi.query(query.trim())
    await applyMapPatch(data.map_patch)
    return data
  }

  function clearMapSelection() {
    selectedSpaceSummary.value = null
    if (worldSession.interactionState?.focus_map) {
      worldSession.interactionState.focus_map.selectedEntityId = null
      for (const node of worldSession.interactionState.focus_map.nodes) {
        if (node.status === 'active' && node.id !== worldSession.interactionState.focus_map.currentSpaceId) {
          node.status = 'visible'
        }
      }
    }
  }

  function reset() {
    selectedSpaceSummary.value = null
    mapLoading.value = false
  }

  return {
    map,
    mode,
    viewLayer,
    breadcrumb,
    floorPlanReady,
    floorRoomList,
    nodes,
    edges,
    agentPresences,
    neighborLinks,
    selectedEntityId,
    selectedSpaceSummary,
    mapLoading,
    applyFocusMap,
    fetchFocus,
    drillTo,
    drillUp,
    drillToCurrentRoom,
    switchMapMode,
    selectMapTarget,
    handleNodeClick,
    applyMapPatch,
    searchMap,
    clearMapSelection,
    reset,
  }
})
