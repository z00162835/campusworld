import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAppTabByRoute, type AppTabDefinition } from './appTabs'

export interface Tab extends AppTabDefinition {
  id: string
  title: string
  route: string
  component: string
  closable: boolean
}

export const useTabsStore = defineStore('tabs', () => {
  const tabs = ref<Tab[]>([])
  const activeTabId = ref<string>('')

  const activeTab = computed(() => {
    return tabs.value.find(tab => tab.id === activeTabId.value)
  })

  const addTab = (tab: Tab) => {
    // 检查是否已存在相同的tab（基于route）
    const existingTab = tabs.value.find(t => t.route === tab.route)
    if (existingTab) {
      activeTabId.value = existingTab.id
      return existingTab
    }

    tabs.value.push(tab)
    activeTabId.value = tab.id
    return tab
  }

  const removeTab = (tabId: string): Tab | null => {
    const index = tabs.value.findIndex(t => t.id === tabId)
    if (index === -1) return activeTab.value || null

    tabs.value.splice(index, 1)

    // 如果关闭的是当前激活的tab，切换到其他tab
    if (activeTabId.value === tabId) {
      if (tabs.value.length > 0) {
        // 优先选择右侧的tab，否则选择左侧的tab
        const newIndex = index < tabs.value.length ? index : index - 1
        activeTabId.value = tabs.value[newIndex]?.id || ''
      } else {
        activeTabId.value = ''
      }
    }

    return activeTab.value || null
  }

  const setActiveTab = (tabId: string) => {
    if (tabs.value.find(t => t.id === tabId)) {
      activeTabId.value = tabId
    }
  }

  const openTabByRoute = (route: string): Tab | null => {
    const tab = getAppTabByRoute(route)
    if (!tab) return null
    return addTab(tab)
  }

  const activateTabByRoute = (route: string): Tab | null => {
    const existingTab = tabs.value.find(t => t.route === route)
    if (existingTab) {
      activeTabId.value = existingTab.id
      return existingTab
    }
    return openTabByRoute(route)
  }

  const closeTab = (tabId: string): Tab | null => {
    return removeTab(tabId)
  }

  const clearTabs = () => {
    tabs.value = []
    activeTabId.value = ''
  }

  return {
    tabs,
    activeTabId,
    activeTab,
    addTab,
    removeTab,
    setActiveTab,
    openTabByRoute,
    activateTabByRoute,
    closeTab,
    clearTabs
  }
})
