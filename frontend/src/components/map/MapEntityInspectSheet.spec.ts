import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import MapEntityInspectSheet from '@/components/map/MapEntityInspectSheet.vue'
import { useWorldMapStore } from '@/stores/worldMap'

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>()
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key }),
  }
})

vi.mock('@/api/decisionCenter', () => ({
  decisionCenterApi: { query: vi.fn() },
}))

vi.mock('@/composables/useNotification', () => ({
  useNotification: () => ({
    confirm: vi.fn().mockResolvedValue(undefined),
  }),
}))

describe('MapEntityInspectSheet', () => {
  it('renders entity inspect content', () => {
    setActivePinia(createPinia())
    const store = useWorldMapStore()
    store.selectedInspect = {
      entityId: '3',
      entityKind: 'device',
      inspect: {
        entity: { id: '3', name: 'Lamp', type_code: 'item', map_node_type: 'device' },
        entity_kind: 'device',
        appearance: { lines: ['A lamp'] },
        actions: [],
        source: 'look',
      },
    }
    const wrapper = mount(MapEntityInspectSheet, {
      global: { stubs: { ElButton: { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.text()).toContain('Lamp')
    expect(wrapper.text()).toContain('A lamp')
  })

  it('shows person kind for account nodes mislabeled as agent', () => {
    setActivePinia(createPinia())
    const store = useWorldMapStore()
    store.selectedInspect = {
      entityId: '11',
      entityKind: 'agent',
      inspect: {
        entity: { id: '11', name: 'admin', type_code: 'account', map_node_type: 'service' },
        entity_kind: 'person',
        appearance: { lines: ['admin is here.'] },
        actions: [],
        source: 'look',
      },
    }
    const wrapper = mount(MapEntityInspectSheet, {
      global: { stubs: { ElButton: { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.text()).toContain('worldInteraction.map.inspect.kind.person')
  })

  it('shows person kind for account when backend still sends agent', () => {
    setActivePinia(createPinia())
    const store = useWorldMapStore()
    store.selectedInspect = {
      entityId: '11',
      entityKind: 'agent',
      inspect: {
        entity: { id: '11', name: 'admin', type_code: 'account', map_node_type: 'service' },
        entity_kind: 'agent',
        appearance: { lines: [] },
        actions: [],
        source: 'look',
      },
    }
    const wrapper = mount(MapEntityInspectSheet, {
      global: { stubs: { ElButton: { template: '<button><slot /></button>' } } },
    })
    expect(wrapper.text()).toContain('worldInteraction.map.inspect.kind.person')
  })
})
