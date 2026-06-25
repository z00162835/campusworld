import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { semanticMapApi } from '@/api/semanticMap'
import { useWorldSessionStore } from './worldSession'
import type {
  EntityInspectData,
  FocusMap,
  MapBreadcrumb,
  MapInspectSelection,
  MapPatch,
  MapViewLayer,
  SemanticMapNode,
  SpaceSummaryData,
} from '@/types/world'

const OUTDOOR_SPOT_NODE_TYPES = new Set<SemanticMapNode['type']>(['gate', 'bridge', 'plaza'])

function isFloorDrillableRoom(node: SemanticMapNode): boolean {
  return (
    node.type === 'room'
    || node.type === 'outdoor'
    || OUTDOOR_SPOT_NODE_TYPES.has(node.type)
  )
}

function spaceSelection(entityId: string, inspect: SpaceSummaryData): MapInspectSelection {
  return { entityId, entityKind: 'space', inspect }
}

function entitySelection(entityId: string, inspect: EntityInspectData): MapInspectSelection {
  return { entityId, entityKind: inspect.entity_kind, inspect }
}

export const useWorldMapStore = defineStore('worldMap', () => {
  const worldSession = useWorldSessionStore()
  const selectedInspect = ref<MapInspectSelection | null>(null)
  const loadingInspect = ref(false)
  const mapLoading = ref(false)
  let mapRequestSeq = 0

  function beginMapRequest(): number {
    mapRequestSeq += 1
    mapLoading.value = true
    return mapRequestSeq
  }

  function endMapRequest(seq: number) {
    if (seq === mapRequestSeq) {
      mapLoading.value = false
    }
  }

  function isCurrentMapRequest(seq: number): boolean {
    return seq === mapRequestSeq
  }

  const map = computed(() => worldSession.focusMap)
  const mode = computed(() => map.value?.mode || 'focus')
  const viewLayer = computed(() => map.value?.viewLayer || 'room')
  const breadcrumb = computed(() => map.value?.breadcrumb || [])
  const floorPlanReady = computed(() => map.value?.floorPlanReady !== false)
  const floorRoomList = computed(() => map.value?.floorRoomList || [])
  const floorStack = computed(() => map.value?.floorStack || [])
  const floorGridBounds = computed(() => map.value?.floorGridBounds ?? null)
  const roomOccupants = computed(() => map.value?.roomOccupants || [])
  const nodes = computed(() => map.value?.nodes || [])
  const edges = computed(() => map.value?.edges || [])
  const agentPresences = computed(() => map.value?.agentPresences || [])
  const neighborLinks = computed(() => map.value?.neighborLinks || [])
  const selectedEntityId = computed(() => map.value?.selectedEntityId || null)

  /** @deprecated use selectedInspect */
  const selectedSpaceSummary = computed(() =>
    selectedInspect.value?.entityKind === 'space' ? selectedInspect.value.inspect : null,
  )

  function applyFocusMap(focusMap: FocusMap) {
    if (worldSession.interactionState) {
      worldSession.interactionState.focus_map = focusMap
    }
  }

  function applySelectResponse(
    entityId: string,
    data: {
      space_summary?: SpaceSummaryData | null
      entity_inspect?: EntityInspectData | null
    },
  ) {
    if (data.space_summary) {
      selectedInspect.value = spaceSelection(entityId, data.space_summary)
      return
    }
    if (data.entity_inspect) {
      selectedInspect.value = entitySelection(entityId, data.entity_inspect)
      return
    }
    selectedInspect.value = null
  }

  async function fetchFocus(options?: {
    viewLayer?: string
    anchorId?: string
    mode?: FocusMap['mode']
    selectedEntityId?: string
  }) {
    const seq = beginMapRequest()
    try {
      const { data } = await semanticMapApi.getFocus({
        view_layer: options?.viewLayer,
        anchor_id: options?.anchorId,
        mode: options?.mode ?? mode.value,
        selected_entity_id: options?.selectedEntityId,
      })
      if (!isCurrentMapRequest(seq)) return
      applyFocusMap(data.focus_map)
    } finally {
      endMapRequest(seq)
    }
  }

  async function drillTo(layer: MapViewLayer, anchorId?: string) {
    const seq = beginMapRequest()
    selectedInspect.value = null
    loadingInspect.value = false
    try {
      const { data } = await semanticMapApi.executeAction({
        action_type: 'drill',
        view_layer: layer,
        anchor_id: anchorId,
        mode: mode.value,
      })
      if (!isCurrentMapRequest(seq)) return
      if (data.focus_map) {
        applyFocusMap(data.focus_map)
      }
    } finally {
      endMapRequest(seq)
    }
  }

  async function drillUp() {
    const crumbs = breadcrumb.value
    if (crumbs.length <= 1) return
    const parent = crumbs[crumbs.length - 2]
    await navigateBreadcrumb(parent)
  }

  async function navigateBreadcrumb(crumb: MapBreadcrumb) {
    const role = crumb.role ?? crumb.layer
    switch (role) {
      case 'hub':
        await drillTo('world')
        return
      case 'world':
        await drillTo('campus', crumb.id)
        return
      case 'campus_spot':
        await drillToOutdoorSpot(crumb.id)
        return
      case 'building':
        await drillTo('building', crumb.id)
        return
      case 'floor':
        await drillTo('floor', crumb.id)
        return
      case 'room':
        await drillTo('room', crumb.id)
        return
      default:
        await drillTo(crumb.layer as MapViewLayer, crumb.id)
    }
  }

  async function drillToCurrentRoom() {
    const roomCrumb = breadcrumb.value.find(item => item.layer === 'room')
    if (roomCrumb) {
      await drillTo('room', roomCrumb.id)
      return
    }
    await drillTo('room')
  }

  async function refreshSelectedInspect() {
    const current = selectedInspect.value
    if (!current) return
    loadingInspect.value = true
    try {
      const res = await semanticMapApi.getEntityInspect({ node_id: current.entityId })
      if (res.data.ok && res.data.inspect) {
        selectedInspect.value = entitySelection(current.entityId, res.data.inspect)
        return
      }
      const summaryRes = await semanticMapApi.getSpaceSummary(current.entityId)
      if (summaryRes.data.ok && summaryRes.data.summary) {
        selectedInspect.value = spaceSelection(current.entityId, summaryRes.data.summary)
      }
    } catch (err) {
      console.warn('[worldMap] refreshSelectedInspect failed:', err)
    } finally {
      loadingInspect.value = false
    }
  }

  async function drillToOutdoorSpot(nodeId: string) {
    selectedInspect.value = null
    await drillTo('room', nodeId)
    loadingInspect.value = true
    try {
      const summaryRes = await semanticMapApi.getSpaceSummary(nodeId)
      if (summaryRes.data.ok && summaryRes.data.summary) {
        selectedInspect.value = spaceSelection(nodeId, summaryRes.data.summary)
      }
    } catch (err) {
      console.warn('[worldMap] drillToOutdoorSpot summary failed:', err)
    } finally {
      loadingInspect.value = false
    }
  }

  async function switchMapMode(nextMode: FocusMap['mode']) {
    await fetchFocus({ viewLayer: viewLayer.value, mode: nextMode })
  }

  async function selectEntity(
    nodeId: string,
    options?: { viewLayer?: MapViewLayer; anchorId?: string; agentId?: string },
  ) {
    const seq = beginMapRequest()
    loadingInspect.value = true
    selectedInspect.value = null
    const layer = options?.viewLayer ?? viewLayer.value
    let anchorId = options?.anchorId
    if (!anchorId && layer === 'room') {
      anchorId = nodeId
    }
    if (!anchorId && layer === 'campus') {
      anchorId = breadcrumb.value.find(item => item.role === 'world')?.id
    }
    try {
      const { data } = await semanticMapApi.executeAction({
        action_type: 'select',
        view_layer: layer,
        anchor_id: anchorId,
        mode: mode.value,
        selected_entity_id: nodeId,
      })
      if (!isCurrentMapRequest(seq)) return
      if (data.focus_map) {
        applyFocusMap(data.focus_map)
      }
      applySelectResponse(nodeId, data)
      if (!selectedInspect.value && !data.space_summary && !data.entity_inspect) {
        if (options?.agentId) {
          const agentRes = await semanticMapApi.getEntityInspect({ agent_id: options.agentId })
          if (!isCurrentMapRequest(seq)) return
          if (agentRes?.data?.ok && agentRes.data.inspect) {
            selectedInspect.value = entitySelection(nodeId, agentRes.data.inspect)
          }
        } else {
          const summaryRes = await semanticMapApi.getSpaceSummary(nodeId)
          if (!isCurrentMapRequest(seq)) return
          if (summaryRes?.data?.ok && summaryRes.data.summary) {
            selectedInspect.value = spaceSelection(nodeId, summaryRes.data.summary)
            return
          }
          const inspectRes = await semanticMapApi.getEntityInspect({ node_id: nodeId })
          if (!isCurrentMapRequest(seq)) return
          if (inspectRes?.data?.ok && inspectRes.data.inspect) {
            selectedInspect.value = entitySelection(nodeId, inspectRes.data.inspect)
          }
        }
      }
    } finally {
      loadingInspect.value = false
      endMapRequest(seq)
    }
  }

  async function selectMapTarget(nodeId: string, options?: { viewLayer?: MapViewLayer; anchorId?: string }) {
    await selectEntity(nodeId, options)
  }

  async function handleNodeClick(node: SemanticMapNode) {
    if (node.type === 'cluster') {
      if (node.id.startsWith('cluster:room:')) {
        const memberId = node.objectIds?.[0] ?? node.activeAgentIds?.[0]
        if (memberId) {
          await selectEntity(memberId, { viewLayer: 'room' })
        }
        return
      }
      if (node.id.startsWith('cluster:floor:')) {
        if (node.drillAnchorId) {
          await drillTo('room', node.drillAnchorId)
        }
        return
      }
      if (node.drillAnchorId) {
        await drillTo('building', node.drillAnchorId)
      }
      return
    }
    if (node.type === 'world') {
      await drillTo('campus', node.id)
      return
    }
    if (
      (node.type === 'gate' || node.type === 'bridge' || node.type === 'plaza') &&
      viewLayer.value === 'world'
    ) {
      if (node.drillAnchorId) {
        await drillTo('campus', node.drillAnchorId)
      }
      return
    }
    if (node.type === 'hub') {
      return
    }
    if (node.type === 'building') {
      await selectEntity(node.id, { viewLayer: 'building', anchorId: node.id })
      return
    }
    if (node.type === 'floor') {
      await selectEntity(node.id, { viewLayer: 'floor', anchorId: node.id })
      return
    }
    if (
      (node.type === 'gate' || node.type === 'bridge' || node.type === 'plaza') &&
      viewLayer.value === 'campus'
    ) {
      await drillToOutdoorSpot(node.id)
      return
    }
    if (viewLayer.value === 'floor' && isFloorDrillableRoom(node)) {
      if (OUTDOOR_SPOT_NODE_TYPES.has(node.type)) {
        await drillToOutdoorSpot(node.id)
      } else {
        await drillTo('room', node.id)
      }
      return
    }
    if (node.type === 'object' || node.type === 'device' || node.type === 'agent') {
      await selectEntity(node.id, { viewLayer: 'room' })
      return
    }
    if (viewLayer.value === 'room' && node.logicalZone === 'exit') {
      await drillTo('room', node.id)
      return
    }
    if (node.type === 'room' || node.type === 'outdoor' || node.type === 'gate' || node.type === 'bridge' || node.type === 'plaza') {
      await selectEntity(node.id)
      return
    }
    await selectEntity(node.id)
  }

  async function selectAgent(agentId: string) {
    await selectEntity(agentId, { viewLayer: 'room', agentId })
  }

  async function applyMapPatch(patch?: MapPatch) {
    if (!patch) return
    if (patch.focus_map) {
      applyFocusMap(patch.focus_map)
      const highlightId = patch.highlightedNodeIds?.[0]
      if (highlightId) {
        await selectEntity(highlightId)
      }
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
      await selectEntity(patch.highlightedNodeIds[0])
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
    const seq = beginMapRequest()
    try {
      const { data } = await semanticMapApi.query(query.trim())
      if (!isCurrentMapRequest(seq)) return data
      await applyMapPatch(data.map_patch)
      return data
    } catch (err) {
      console.warn('[worldMap] searchMap failed:', err)
      throw err
    } finally {
      endMapRequest(seq)
    }
  }

  function clearMapSelection() {
    selectedInspect.value = null
    loadingInspect.value = false
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
    selectedInspect.value = null
    loadingInspect.value = false
    mapRequestSeq += 1
    mapLoading.value = false
  }

  return {
    map,
    mode,
    viewLayer,
    breadcrumb,
    floorPlanReady,
    floorRoomList,
    floorStack,
    floorGridBounds,
    roomOccupants,
    nodes,
    edges,
    agentPresences,
    neighborLinks,
    selectedEntityId,
    selectedInspect,
    loadingInspect,
    selectedSpaceSummary,
    mapLoading,
    applyFocusMap,
    fetchFocus,
    drillTo,
    drillUp,
    navigateBreadcrumb,
    drillToCurrentRoom,
    drillToOutdoorSpot,
    refreshSelectedInspect,
    switchMapMode,
    selectEntity,
    selectMapTarget,
    selectAgent,
    handleNodeClick,
    applyMapPatch,
    searchMap,
    clearMapSelection,
    reset,
  }
})
