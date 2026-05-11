import { useRouter } from 'vue-router'
import { DEFAULT_APP_ROUTE, getAppTabByRoute } from '@/stores/appTabs'
import { useTabsStore, type Tab } from '@/stores/tabs'

export function useAppTabs() {
  const router = useRouter()
  const tabsStore = useTabsStore()

  const openAppTab = async (route: string): Promise<Tab | null> => {
    const tab = tabsStore.openTabByRoute(route)
    if (!tab) return null
    await router.push(tab.route)
    return tab
  }

  const activateAppTab = async (tabId: string): Promise<Tab | null> => {
    const targetTab = tabsStore.tabs.find(tab => tab.id === tabId)
    if (!targetTab) return null
    tabsStore.setActiveTab(tabId)
    await router.push(targetTab.route)
    return targetTab
  }

  const closeAppTab = async (tabId: string): Promise<Tab | null> => {
    const wasActive = tabsStore.activeTabId === tabId
    const nextTab = tabsStore.closeTab(tabId)

    if (wasActive) {
      if (nextTab) {
        await router.push(nextTab.route)
      } else {
        const fallbackTab = tabsStore.openTabByRoute(DEFAULT_APP_ROUTE)
        await router.push(fallbackTab?.route || DEFAULT_APP_ROUTE)
      }
    }

    return tabsStore.activeTab || null
  }

  const syncRouteToTab = (route: string): Tab | null => {
    if (!getAppTabByRoute(route)) return null
    return tabsStore.activateTabByRoute(route)
  }

  return {
    openAppTab,
    activateAppTab,
    closeAppTab,
    syncRouteToTab,
  }
}
