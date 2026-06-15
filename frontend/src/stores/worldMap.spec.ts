import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { semanticMapApi } from '@/api/semanticMap'
import { useWorldMapStore } from './worldMap'
import { useWorldSessionStore } from './worldSession'
import type { AgentMapPresence, FocusMap, MapBreadcrumb, SemanticMapNode } from '@/types/world'

vi.mock('@/api/semanticMap', () => ({
  semanticMapApi: {
    query: vi.fn(),
    getFocus: vi.fn(),
    executeAction: vi.fn(),
    getSpaceSummary: vi.fn(),
  },
}))

/** Generic map fixtures — protocol behavior only, no world-package coupling. */
const IDS = {
  currentSpace: 'space-current',
  hub: 'node-hub',
  world: 'node-world',
  building: 'node-building',
  floor: 'node-floor',
  room: 'node-room',
  overflowRoom: 'node-overflow',
  outdoorSpot: 'node-outdoor',
  searchHit: 'node-search-hit',
  agentExisting: 'agent-existing',
  agentIncoming: 'agent-incoming',
  spacePeer: 'space-peer',
  spaceRemote: 'space-remote',
} as const

const LABELS = {
  hub: 'Hub Root',
  world: 'Campus World',
  building: 'Tower A',
  floor: 'Level 1',
  outdoorSpot: 'Outdoor Plaza',
  exitRoom: 'Remote Room',
  searchHit: 'Search Hit',
} as const

const AGENT_STATES = {
  initial: {
    status: 'waiting' as const,
    lastSeenAt: '2026-01-01T00:00:00.000Z',
  },
  updated: {
    status: 'moving' as const,
    lastSeenAt: '2026-01-02T00:00:00.000Z',
  },
  incoming: {
    status: 'working' as const,
    lastSeenAt: '2026-01-02T00:00:00.000Z',
  },
} as const

function agentPresence(
  agentId: string,
  overrides: Partial<AgentMapPresence> = {},
): AgentMapPresence {
  return {
    agentId,
    name: agentId,
    role: 'agent',
    currentSpaceId: IDS.currentSpace,
    status: AGENT_STATES.initial.status,
    lastSeenAt: AGENT_STATES.initial.lastSeenAt,
    visibility: 'visible',
    ...overrides,
  }
}

function agentById(presences: AgentMapPresence[], agentId: string): AgentMapPresence | undefined {
  return presences.find(entry => entry.agentId === agentId)
}

function mapNode(overrides: Partial<SemanticMapNode> & Pick<SemanticMapNode, 'id'>): SemanticMapNode {
  return {
    name: overrides.id,
    type: 'room',
    x: 50,
    y: 50,
    status: 'visible',
    semanticTags: [],
    activeAgentIds: [],
    activeEventIds: [],
    objectIds: [],
    ...overrides,
  }
}

function breadcrumb(
  layer: MapBreadcrumb['layer'],
  id: string,
  name: string,
  role: MapBreadcrumb['role'],
): MapBreadcrumb {
  return { layer, id, name, role }
}

function baseFocusMap(overrides: Partial<FocusMap> = {}): FocusMap {
  return {
    mode: 'focus',
    viewLayer: 'room',
    nodes: [mapNode({ id: IDS.currentSpace, name: 'Current Space', type: 'room', status: 'current' })],
    edges: [],
    agentPresences: [],
    highlightedPath: [],
    currentSpaceId: IDS.currentSpace,
    selectedEntityId: null,
    loading: false,
    ...overrides,
  }
}

describe('worldMap store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const session = useWorldSessionStore()
    session.interactionState = {
      session: {
        id: 'session-1',
        currentSpaceId: IDS.currentSpace,
        currentWorldId: 'world-alpha',
        updatedAt: '',
        currentSpaceKey: null,
      },
      decision_center: { focus: null, decisionEvents: [], activeTask: null, nextBestAction: null },
      focus_map: baseFocusMap(),
      context_summary: {},
      quick_queries: [],
      display_policy: {},
    } as any
  })

  it('searchMap applies focus_map from query response', async () => {
    vi.mocked(semanticMapApi.query).mockResolvedValue({
      data: {
        mode: 'focus',
        answer: 'Found target',
        map_patch: {
          viewLayer: 'campus',
          highlightedNodeIds: [IDS.searchHit],
          focus_map: baseFocusMap({
            viewLayer: 'campus',
            nodes: [
              mapNode({
                id: IDS.searchHit,
                name: LABELS.searchHit,
                type: 'building',
                x: 10,
                y: 10,
                status: 'active',
              }),
            ],
            selectedEntityId: IDS.searchHit,
          }),
        },
      },
    } as any)

    const store = useWorldMapStore()
    await store.searchMap('tower')

    expect(store.viewLayer).toBe('campus')
    expect(store.nodes[0].id).toBe(IDS.searchHit)
    expect(store.nodes[0].status).toBe('active')
  })

  it('applyMapPatch merges agentPresences by agentId', async () => {
    const store = useWorldMapStore()
    const focus = store.map!
    const existing = agentPresence(IDS.agentExisting)
    focus.agentPresences = [existing]

    const patchPrimary = agentPresence(IDS.agentExisting, {
      currentSpaceId: IDS.spacePeer,
      status: AGENT_STATES.updated.status,
      lastSeenAt: AGENT_STATES.updated.lastSeenAt,
    })
    const patchIncoming = agentPresence(IDS.agentIncoming, {
      role: 'service',
      currentSpaceId: IDS.spaceRemote,
      status: AGENT_STATES.incoming.status,
      lastSeenAt: AGENT_STATES.incoming.lastSeenAt,
    })

    await store.applyMapPatch({
      agentPresences: [patchPrimary, patchIncoming],
    })

    expect(store.agentPresences).toHaveLength(2)
    const mergedExisting = agentById(store.agentPresences, IDS.agentExisting)
    const mergedIncoming = agentById(store.agentPresences, IDS.agentIncoming)
    expect(mergedExisting?.currentSpaceId).toBe(IDS.spacePeer)
    expect(mergedExisting?.status).toBe(AGENT_STATES.updated.status)
    expect(mergedExisting?.lastSeenAt).toBe(AGENT_STATES.updated.lastSeenAt)
    expect(mergedIncoming?.currentSpaceId).toBe(IDS.spaceRemote)
    expect(mergedIncoming?.status).toBe(AGENT_STATES.incoming.status)
  })

  it('floor cluster click selects overflow room instead of building drill', async () => {
    const store = useWorldMapStore()
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map, space_summary: null },
    } as any)
    vi.mocked(semanticMapApi.getSpaceSummary).mockResolvedValue({
      data: {
        ok: true,
        summary: {
          space_node: { id: 99, type_code: 'room', name: 'Overflow', parent_id: null },
        },
      },
    } as any)
    await store.handleNodeClick({
      id: 'cluster:floor:10',
      name: '+3 rooms',
      type: 'cluster',
      x: 80,
      y: 50,
      status: 'visible',
      semanticTags: [],
      activeAgentIds: [],
      activeEventIds: [],
      objectIds: [],
      drillAnchorId: IDS.overflowRoom,
    })

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'room',
        anchor_id: IDS.overflowRoom,
      }),
    )
  })

  it('navigateBreadcrumb hub drills to world layer', async () => {
    const store = useWorldMapStore()
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map },
    } as any)

    await store.navigateBreadcrumb(breadcrumb('world', IDS.hub, LABELS.hub, 'hub'))

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({ action_type: 'drill', view_layer: 'world' }),
    )
  })

  it('navigateBreadcrumb building drills to building layer', async () => {
    const store = useWorldMapStore()
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map },
    } as any)

    await store.navigateBreadcrumb(
      breadcrumb('building', IDS.building, LABELS.building, 'building'),
    )

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'building',
        anchor_id: IDS.building,
      }),
    )
  })

  it('navigateBreadcrumb floor drills to floor layer', async () => {
    const store = useWorldMapStore()
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map },
    } as any)

    await store.navigateBreadcrumb(breadcrumb('floor', IDS.floor, LABELS.floor, 'floor'))

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'floor',
        anchor_id: IDS.floor,
      }),
    )
  })

  it('room content group cluster selects first member on click', async () => {
    const store = useWorldMapStore()
    const session = useWorldSessionStore()
    session.interactionState!.focus_map!.viewLayer = 'room'
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map, space_summary: null },
    } as any)
    vi.mocked(semanticMapApi.getSpaceSummary).mockResolvedValue({
      data: { ok: true, summary: { space_node: { id: 21, type_code: 'device', name: 'Light', parent_id: 1 } } },
    } as any)

    await store.handleNodeClick({
      id: 'cluster:room:1:device',
      name: 'Devices · 2',
      type: 'cluster',
      x: 64,
      y: 50,
      status: 'visible',
      semanticTags: ['device', 'group'],
      activeAgentIds: [],
      activeEventIds: [],
      objectIds: ['21', '22'],
      logicalZone: 'device',
    })

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'select',
        selected_entity_id: '21',
        view_layer: 'room',
      }),
    )
  })

  it('cross-building exit building node drills to building layer', async () => {
    const store = useWorldMapStore()
    const session = useWorldSessionStore()
    session.interactionState!.focus_map!.viewLayer = 'room'
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map, space_summary: null },
    } as any)

    await store.handleNodeClick({
      id: IDS.building,
      name: LABELS.building,
      type: 'building',
      x: 50,
      y: 22,
      status: 'visible',
      semanticTags: [],
      activeAgentIds: [],
      activeEventIds: [],
      objectIds: [],
      logicalZone: 'exit',
      crossBuilding: true,
      drillAnchorId: IDS.room,
    })

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'building',
        anchor_id: IDS.building,
      }),
    )
  })

  it('room exit click drills to target room', async () => {
    const store = useWorldMapStore()
    const session = useWorldSessionStore()
    session.interactionState!.focus_map!.viewLayer = 'room'
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map, space_summary: null },
    } as any)

    await store.handleNodeClick({
      id: IDS.room,
      name: LABELS.exitRoom,
      type: 'room',
      x: 50,
      y: 78,
      status: 'visible',
      semanticTags: [],
      activeAgentIds: [],
      activeEventIds: [],
      objectIds: [],
      logicalZone: 'exit',
      crossBuilding: true,
    })

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'room',
        anchor_id: IDS.room,
      }),
    )
  })

  it('navigateBreadcrumb world drills to campus with world anchor', async () => {
    const store = useWorldMapStore()
    const session = useWorldSessionStore()
    session.interactionState!.focus_map!.breadcrumb = [
      breadcrumb('world', IDS.hub, LABELS.hub, 'hub'),
      breadcrumb('campus', IDS.world, LABELS.world, 'world'),
    ]
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map },
    } as any)

    await store.navigateBreadcrumb(breadcrumb('campus', IDS.world, LABELS.world, 'world'))

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'campus',
        anchor_id: IDS.world,
      }),
    )
  })

  it('floor plaza tile click drills to room layer and loads space summary', async () => {
    const store = useWorldMapStore()
    const session = useWorldSessionStore()
    session.interactionState!.focus_map!.viewLayer = 'floor'
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map, space_summary: null },
    } as any)
    vi.mocked(semanticMapApi.getSpaceSummary).mockResolvedValue({
      data: { ok: true, summary: { space_node: { id: 50, type_code: 'room', name: LABELS.outdoorSpot, parent_id: null } } },
    } as any)

    await store.handleNodeClick({
      id: IDS.outdoorSpot,
      name: LABELS.outdoorSpot,
      type: 'plaza',
      x: 50,
      y: 50,
      status: 'visible',
      semanticTags: ['environment:outdoor'],
      activeAgentIds: [],
      activeEventIds: [],
      objectIds: [],
      roomType: 'plaza',
    })

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'room',
        anchor_id: IDS.outdoorSpot,
      }),
    )
    expect(semanticMapApi.getSpaceSummary).toHaveBeenCalledWith(IDS.outdoorSpot)
  })

  it('campus outdoor spot click drills to room layer and loads space summary', async () => {
    const store = useWorldMapStore()
    const session = useWorldSessionStore()
    session.interactionState!.focus_map!.viewLayer = 'campus'
    session.interactionState!.focus_map!.breadcrumb = [
      breadcrumb('world', IDS.hub, LABELS.hub, 'hub'),
      breadcrumb('campus', IDS.world, LABELS.world, 'world'),
    ]
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: {
        focus_map: {
          ...session.interactionState!.focus_map!,
          viewLayer: 'room',
          layout: 'logical',
          nodes: [{ id: IDS.outdoorSpot, name: LABELS.outdoorSpot, type: 'plaza', x: 50, y: 50, status: 'current' }],
          edges: [],
        },
      },
    } as any)
    vi.mocked(semanticMapApi.getSpaceSummary).mockResolvedValue({
      data: {
        ok: true,
        summary: {
          space_node: { id: 50, type_code: 'room', name: LABELS.outdoorSpot, parent_id: null },
        },
      },
    } as any)

    await store.handleNodeClick(
      mapNode({
        id: IDS.outdoorSpot,
        name: LABELS.outdoorSpot,
        type: 'plaza',
      }),
    )

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({
        action_type: 'drill',
        view_layer: 'room',
        anchor_id: IDS.outdoorSpot,
      }),
    )
    expect(semanticMapApi.getSpaceSummary).toHaveBeenCalledWith(IDS.outdoorSpot)
    expect(store.selectedSpaceSummary).not.toBeNull()
  })
})
