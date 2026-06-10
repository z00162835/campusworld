import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { semanticMapApi } from '@/api/semanticMap'
import { useWorldMapStore } from './worldMap'
import { useWorldSessionStore } from './worldSession'

vi.mock('@/api/semanticMap', () => ({
  semanticMapApi: {
    query: vi.fn(),
    getFocus: vi.fn(),
    executeAction: vi.fn(),
    getSpaceSummary: vi.fn(),
  },
}))

describe('worldMap store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const session = useWorldSessionStore()
    session.interactionState = {
      session: { id: 'world_1', currentSpaceId: '1', currentWorldId: 'hicampus', updatedAt: '', currentSpaceKey: null },
      decision_center: { focus: null, decisionEvents: [], activeTask: null, nextBestAction: null },
      focus_map: {
        mode: 'focus',
        viewLayer: 'room',
        nodes: [{ id: '1', name: 'Hub', type: 'room', x: 50, y: 50, status: 'current', semanticTags: [], activeAgentIds: [], activeEventIds: [], objectIds: [] }],
        edges: [],
        agentPresences: [],
        highlightedPath: [],
        currentSpaceId: '1',
        selectedEntityId: null,
        loading: false,
      },
      context_summary: {},
      quick_queries: [],
      display_policy: {},
    } as any
  })

  it('searchMap applies focus_map from query response', async () => {
    vi.mocked(semanticMapApi.query).mockResolvedValue({
      data: {
        mode: 'focus',
        answer: 'Found F3',
        map_patch: {
          viewLayer: 'campus',
          highlightedNodeIds: ['20'],
          focus_map: {
            mode: 'focus',
            viewLayer: 'campus',
            nodes: [{ id: '20', name: 'F3', type: 'building', x: 10, y: 10, status: 'active', semanticTags: [], activeAgentIds: [], activeEventIds: [], objectIds: [] }],
            edges: [],
            agentPresences: [],
            highlightedPath: [],
            currentSpaceId: '1',
            selectedEntityId: '20',
            loading: false,
          },
        },
      },
    } as any)

    const store = useWorldMapStore()
    await store.searchMap('F3')

    expect(store.viewLayer).toBe('campus')
    expect(store.nodes[0].id).toBe('20')
    expect(store.nodes[0].status).toBe('active')
  })

  it('applyMapPatch merges agentPresences by agentId', async () => {
    const store = useWorldMapStore()
    const focus = store.map!
    focus.agentPresences = [
      {
        agentId: '7',
        name: 'Guide',
        role: 'guide',
        currentSpaceId: '1',
        status: 'waiting',
        lastSeenAt: '2026-01-01',
        visibility: 'visible',
      },
    ]

    await store.applyMapPatch({
      agentPresences: [
        {
          agentId: '7',
          name: 'Guide',
          role: 'guide',
          currentSpaceId: '2',
          status: 'moving',
          lastSeenAt: '2026-01-02',
          visibility: 'visible',
        },
        {
          agentId: '9',
          name: 'Worker',
          role: 'service',
          currentSpaceId: '3',
          status: 'working',
          lastSeenAt: '2026-01-02',
          visibility: 'visible',
        },
      ],
    })

    expect(store.agentPresences).toHaveLength(2)
    expect(store.agentPresences.find(agent => agent.agentId === '7')?.currentSpaceId).toBe('2')
    expect(store.agentPresences.find(agent => agent.agentId === '7')?.status).toBe('moving')
  })

  it('floor cluster click selects overflow room instead of building drill', async () => {
    const store = useWorldMapStore()
    vi.mocked(semanticMapApi.executeAction).mockResolvedValue({
      data: { focus_map: store.map, space_summary: null },
    } as any)
    vi.mocked(semanticMapApi.getSpaceSummary).mockResolvedValue({
      data: { ok: true, summary: { space_node: { id: 99, type_code: 'room', name: 'Overflow', parent_id: null } } },
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
      drillAnchorId: '99',
    })

    expect(semanticMapApi.executeAction).toHaveBeenCalledWith(
      expect.objectContaining({ action_type: 'select', selected_entity_id: '99' }),
    )
  })
})
