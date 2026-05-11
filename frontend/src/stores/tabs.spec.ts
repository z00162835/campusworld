import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useTabsStore } from './tabs'

describe('tabs store app route handling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('opens account settings by route after the tab was closed', () => {
    const tabsStore = useTabsStore()

    tabsStore.openTabByRoute('/profile')
    expect(tabsStore.activeTab?.id).toBe('tab-profile')

    tabsStore.closeTab('tab-profile')
    expect(tabsStore.activeTab).toBeUndefined()

    tabsStore.openTabByRoute('/profile')
    expect(tabsStore.activeTab?.id).toBe('tab-profile')
    expect(tabsStore.tabs).toHaveLength(1)
  })

  it('keeps one tab per app route and activates existing tabs', () => {
    const tabsStore = useTabsStore()

    tabsStore.openTabByRoute('/works')
    tabsStore.openTabByRoute('/profile')
    tabsStore.openTabByRoute('/works')

    expect(tabsStore.tabs.map(tab => tab.id)).toEqual(['tab-works', 'tab-profile'])
    expect(tabsStore.activeTab?.id).toBe('tab-works')
  })

  it('returns the right-side tab after closing the active tab', () => {
    const tabsStore = useTabsStore()

    tabsStore.openTabByRoute('/works')
    tabsStore.openTabByRoute('/spaces')
    tabsStore.openTabByRoute('/profile')
    tabsStore.activateTabByRoute('/spaces')

    const nextTab = tabsStore.closeTab('tab-spaces')

    expect(nextTab?.id).toBe('tab-profile')
    expect(tabsStore.activeTab?.id).toBe('tab-profile')
  })
})
