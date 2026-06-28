import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import TabBar from './TabBar.vue'
import { useTabsStore } from '@/stores/tabs'
import zh from '@/locales/zh'

const push = vi.fn().mockResolvedValue(undefined)

vi.mock('vue-router', () => ({
  useRouter: () => ({ push }),
}))

const i18n = createI18n({
  legacy: false,
  locale: 'zh',
  messages: { zh },
})

describe('TabBar', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    push.mockClear()
  })

  it('activates the next tab on ArrowRight', async () => {
    const tabsStore = useTabsStore()
    tabsStore.openTabByRoute('/works')
    tabsStore.openTabByRoute('/spaces')

    const wrapper = mount(TabBar, {
      global: {
        plugins: [i18n],
        stubs: { AppIcon: true },
      },
    })

    const tabs = wrapper.findAll('[role="tab"]')
    await tabs[0]!.trigger('keydown', { key: 'ArrowRight' })

    expect(tabsStore.activeTabId).toBe('tab-spaces')
  })

  it('restores focus to a remaining tab after closing the active tab', async () => {
    const tabsStore = useTabsStore()
    tabsStore.openTabByRoute('/works')
    tabsStore.openTabByRoute('/spaces')
    tabsStore.openTabByRoute('/profile')
    tabsStore.activateTabByRoute('/profile')

    const focusMock = vi.spyOn(HTMLElement.prototype, 'focus')

    const wrapper = mount(TabBar, {
      attachTo: document.body,
      global: {
        plugins: [i18n],
        stubs: { AppIcon: true },
      },
    })

    const profileTab = wrapper.find('#app-tab-tab-profile')
    await profileTab.trigger('keydown', { key: 'Delete' })
    await wrapper.vm.$nextTick()
    await wrapper.vm.$nextTick()

    expect(tabsStore.activeTabId).toBe('tab-spaces')
    expect(focusMock).toHaveBeenCalled()
    focusMock.mockRestore()
    wrapper.unmount()
  })
})
