import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import WorldShell from '../WorldShell.vue'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { WorldInteractionState } from '@/types/world'

vi.mock('vue-i18n', async (importOriginal) => ({
  ...await importOriginal<typeof import('vue-i18n')>(),
  useI18n: () => ({ t: (key: string) => key }),
}))

const stubs = {
  WorldTopBar: true, FocusSemanticMap: { template: '<div class="test-map">Map</div>' },
  DecisionCenterFlow: { emits: ['mapLocate'], template: '<section><button @click="$emit(\'mapLocate\')">Locate</button></section>' },
  ContextSummaryPanel: true, BottomUtilityDrawer: true, AppIcon: true,
}

describe('WorldShell compact layers', () => {
  afterEach(() => { vi.unstubAllGlobals() })
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
  })

  it('keeps the map visible and opens only one local overlay without business mutations', async () => {
    const store = useWorldSessionStore()
    const mutate = vi.spyOn(store, 'executeQuestInteractionAction')
    const wrapper = mount(WorldShell, { global: { stubs } })
    await nextTick()
    expect(wrapper.find('.test-map').isVisible()).toBe(true)
    expect(wrapper.find('#world-quest-panel').isVisible()).toBe(false)
    const tabs = wrapper.findAll('.mobile-world-nav button')
    await tabs[1].trigger('click')
    expect(wrapper.find('#world-quest-panel').attributes('style')).not.toContain('display: none')
    await tabs[2].trigger('click')
    expect(wrapper.find('#world-quest-panel').isVisible()).toBe(false)
    expect(wrapper.find('#world-clues-panel').attributes('style')).not.toContain('display: none')
    await tabs[1].trigger('click')
    await wrapper.find('#world-quest-panel button').trigger('click')
    expect(wrapper.find('#world-quest-panel').isVisible()).toBe(false)
    expect(wrapper.find('.test-map').isVisible()).toBe(true)
    expect(mutate).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('derives the compact objective from the same foreground projection, not the first queue task', async () => {
    const store = useWorldSessionStore()
    store.interactionState = { quest_interaction: {
      contractVersion: 'quest-interaction.v1', capabilities: [], projectionRevision: '1', lastEventId: null,
      foregroundQuestId: '11', trackedQuests: [{ id: '11', title: 'Restore AHU', state: 'executing',
        focusedObjectiveId: '22', objectives: [{ id: '21', title: 'Other action', state: 'open' },
          { id: '22', title: 'Inspect bearing', state: 'in_progress' }] }], worldPulse: [],
    } } as unknown as WorldInteractionState
    const wrapper = mount(WorldShell, { global: { stubs } })
    await nextTick()
    expect(wrapper.find('.mobile-world-summary').text()).toContain('Restore AHU')
    expect(wrapper.find('.mobile-world-summary').text()).toContain('Inspect bearing')
    expect(wrapper.find('.mobile-world-summary').text()).not.toContain('Other action')
    wrapper.unmount()
  })

  it('removes viewport listeners on unmount and does not replace desktop layout', () => {
    const media = { matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }
    vi.stubGlobal('matchMedia', vi.fn(() => media))
    const wrapper = mount(WorldShell, { global: { stubs } })
    expect(wrapper.find('.mobile-world-hud').exists()).toBe(false)
    expect(wrapper.find('#world-quest-panel').isVisible()).toBe(true)
    wrapper.unmount()
    expect(media.removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
  })

  it('supports arrow and boundary keys for desktop pane resizing', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })))
    useWorldSessionStore().viewMode = 'Map'
    const wrapper = mount(WorldShell, { global: { stubs } })
    Object.defineProperty(wrapper.find('main').element, 'clientWidth', { value: 1200 })
    await nextTick()
    await nextTick()
    const separator = wrapper.find('[role="separator"]')
    const before = Number(separator.attributes('aria-valuenow'))
    await separator.trigger('keydown', { key: 'ArrowRight' })
    expect(Number(separator.attributes('aria-valuenow'))).toBe(before + 16)
    await separator.trigger('keydown', { key: 'Home' })
    expect(separator.attributes('aria-valuenow')).toBe(separator.attributes('aria-valuemin'))
    await separator.trigger('keydown', { key: 'End' })
    expect(separator.attributes('aria-valuenow')).toBe(separator.attributes('aria-valuemax'))
    wrapper.unmount()
  })
})
