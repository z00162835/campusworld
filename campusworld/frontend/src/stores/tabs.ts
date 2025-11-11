import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Tab {
  id: string
  title: string
  route: string
  component: string
  closable?: boolean
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

  const removeTab = (tabId: string) => {
    const index = tabs.value.findIndex(t => t.id === tabId)
    if (index === -1) return

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
  }

  const setActiveTab = (tabId: string) => {
    if (tabs.value.find(t => t.id === tabId)) {
      activeTabId.value = tabId
    }
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
    clearTabs
  }
})

