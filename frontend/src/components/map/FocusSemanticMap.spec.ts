import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import FocusSemanticMap from './FocusSemanticMap.vue'
import { useWorldSessionStore } from '@/stores/worldSession'
vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string) => key,
    }),
  }
})

vi.mock('@/api/semanticMap', () => ({
  semanticMapApi: {
    query: vi.fn(),
    getFocus: vi.fn(),
    executeAction: vi.fn(),
    getSpaceSummary: vi.fn(),
  },
}))

describe('FocusSemanticMap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const worldSession = useWorldSessionStore()
    worldSession.loading = false
    worldSession.error = null
    worldSession.interactionState = {
      session: { id: 'world_1', currentSpaceId: '1', currentWorldId: 'hicampus', updatedAt: '', currentSpaceKey: null },
      decision_center: { focus: null, decisionEvents: [], activeTask: null, nextBestAction: null },
      focus_map: {
        mode: 'focus',
        viewLayer: 'floor',
        layout: 'list',
        floorPlanReady: false,
        floorRoomList: [
          { id: '2', name: 'Lab A', status: 'visible' },
          { id: '1', name: 'Current', status: 'current' },
        ],
        nodes: [],
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

  it('renders floor room list and not-ready hint when floor plan is unavailable', () => {
    const wrapper = mount(FocusSemanticMap, {
      global: {
        stubs: {
          'el-button': true,
          'el-button-group': true,
          'el-dropdown': true,
          'el-dropdown-menu': true,
          'el-dropdown-item': true,
          'el-icon': true,
        },
      },
    })

    expect(wrapper.text()).toContain('worldInteraction.map.floorPlanNotReady')
    expect(wrapper.find('.floor-room-list').exists()).toBe(true)
    expect(wrapper.findAll('.floor-room-item')).toHaveLength(2)
    expect(wrapper.find('.map-canvas').exists()).toBe(false)
  })

  it('renders floor plan tiles when grid layout is ready', async () => {
    const worldSession = useWorldSessionStore()
    worldSession.interactionState!.focus_map = {
      mode: 'focus',
      viewLayer: 'floor',
      layout: 'grid',
      floorPlanReady: true,
      floorStack: [
        { id: '10', name: '1F', floorNumber: 1, status: 'active' },
        { id: '11', name: '2F', floorNumber: 2, status: 'current' },
      ],
      floorGridBounds: {
        minCol: 4,
        minRow: 2,
        maxCol: 5,
        maxRow: 3,
        cellPx: 4,
        originX: 10,
        originY: 10,
      },
      nodes: [
        {
          id: '2',
          name: 'Lab',
          type: 'room',
          x: 36,
          y: 30,
          status: 'visible',
          semanticTags: [],
          activeAgentIds: [],
          activeEventIds: [],
          objectIds: [],
          mapGridCol: 4,
          mapGridRow: 2,
          mapGridSpanW: 1,
          mapGridSpanH: 1,
          roomType: 'normal',
        },
        {
          id: '1',
          name: 'Current',
          type: 'room',
          x: 44,
          y: 30,
          status: 'current',
          semanticTags: [],
          activeAgentIds: [],
          activeEventIds: [],
          objectIds: [],
          mapGridCol: 5,
          mapGridRow: 2,
          mapGridSpanW: 1,
          mapGridSpanH: 1,
          roomType: 'circulation',
        },
      ],
      edges: [],
      agentPresences: [],
      highlightedPath: [],
      currentSpaceId: '1',
      selectedEntityId: null,
      loading: false,
    }

    const wrapper = mount(FocusSemanticMap, {
      global: {
        stubs: {
          'el-button': true,
          'el-button-group': true,
          'el-dropdown': true,
          'el-dropdown-menu': true,
          'el-dropdown-item': true,
          'el-icon': true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.find('.layout-grid').exists()).toBe(true)
    expect(wrapper.findAll('.floor-tile-top')).toHaveLength(2)
    expect(wrapper.find('.floor-stack-panel').exists()).toBe(true)
    expect(wrapper.find('.floor-room-list').exists()).toBe(false)
  })

  it('docks room device and item groups in side panels instead of map nodes', async () => {
    const worldSession = useWorldSessionStore()
    worldSession.interactionState!.focus_map = {
      mode: 'focus',
      viewLayer: 'room',
      layout: 'logical',
      nodes: [
        { id: '1', name: 'Hub', type: 'room', x: 50, y: 50, status: 'current', semanticTags: [], activeAgentIds: [], activeEventIds: [], objectIds: [], logicalZone: 'hub' },
        {
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
          groupMembers: [
            { id: '21', name: 'Light', type: 'device', status: 'visible' },
            { id: '22', name: 'AP', type: 'device', status: 'visible' },
          ],
        },
        {
          id: 'cluster:room:1:item',
          name: 'Items · 1',
          type: 'cluster',
          x: 36,
          y: 50,
          status: 'visible',
          semanticTags: ['item', 'group'],
          activeAgentIds: [],
          activeEventIds: [],
          objectIds: ['31'],
          logicalZone: 'item',
          groupMembers: [{ id: '31', name: 'Bench', type: 'object', status: 'visible' }],
        },
      ],
      edges: [],
      roomOccupants: [{ id: '11', name: 'admin', type: 'service', status: 'visible' }],
      agentPresences: [],
      highlightedPath: [],
      currentSpaceId: '1',
      selectedEntityId: null,
      loading: false,
    }

    const wrapper = mount(FocusSemanticMap, {
      global: {
        stubs: {
          'el-button': true,
          'el-button-group': true,
          'el-dropdown': true,
          'el-dropdown-menu': true,
          'el-dropdown-item': true,
          'el-icon': true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.find('.room-content-panels').exists()).toBe(true)
    expect(wrapper.findAll('.room-content-panel')).toHaveLength(2)
    expect(wrapper.find('.space-node-group').exists()).toBe(false)
    expect(wrapper.find('.room-occupants-panel').exists()).toBe(true)
  })

  it('renders edge direction labels on room layer map', async () => {
    const worldSession = useWorldSessionStore()
    worldSession.interactionState!.focus_map = {
      mode: 'focus',
      viewLayer: 'room',
      layout: 'compass',
      floorPlanReady: true,
      nodes: [
        { id: '1', name: 'Hub', type: 'room', x: 50, y: 50, status: 'current', semanticTags: [], activeAgentIds: [], activeEventIds: [], objectIds: [] },
        { id: '2', name: 'North', type: 'room', x: 50, y: 22, status: 'visible', semanticTags: [], activeAgentIds: [], activeEventIds: [], objectIds: [] },
      ],
      edges: [{ id: 'e1', from: '1', to: '2', direction: 'north', status: 'available' }],
      agentPresences: [],
      highlightedPath: [],
      currentSpaceId: '1',
      selectedEntityId: null,
      loading: false,
    }

    const wrapper = mount(FocusSemanticMap, {
      global: {
        stubs: {
          'el-button': true,
          'el-button-group': true,
          'el-dropdown': true,
          'el-dropdown-menu': true,
          'el-dropdown-item': true,
          'el-icon': true,
        },
      },
    })

    await wrapper.vm.$nextTick()
    expect(wrapper.find('.edge-label').text()).toBe('north')
  })
})
