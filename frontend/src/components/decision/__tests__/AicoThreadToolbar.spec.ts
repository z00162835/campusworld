import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { useWorldSessionStore } from '@/stores/worldSession'
import type { WorldInteractionState } from '@/types/world'
import AicoThreadToolbar from '../AicoThreadToolbar.vue'

vi.mock('vue-i18n', async (original) => ({
  ...await original<typeof import('vue-i18n')>(),
  useI18n: () => ({ t: (key: string) => key }),
}))

describe('AicoThreadToolbar', () => {
  it('hides generic thread controls for a foreground Quest with no task', () => {
    setActivePinia(createPinia())
    const session = useWorldSessionStore()
    session.interactionState = { quest_interaction: {
      foregroundQuestId: '11', trackedQuests: [{ id: '11', title: 'Investigate', objectives: [] }],
    } } as unknown as WorldInteractionState
    const wrapper = mount(AicoThreadToolbar, { global: { stubs: {
      ElButton: true, ElDropdown: true, ElDropdownItem: true, ElDropdownMenu: true, AppIcon: true,
    } } })
    expect(wrapper.find('.quest-guide-label').exists()).toBe(true)
    expect(wrapper.find('el-button-stub').exists()).toBe(false)
    expect(wrapper.find('el-dropdown-stub').exists()).toBe(false)
    wrapper.unmount()
  })
})
