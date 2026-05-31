export interface AppTabDefinition {
  id: string
  title: string
  route: string
  component: string
  closable: boolean
}

export const DEFAULT_APP_ROUTE = '/works'

export const APP_TAB_DEFINITIONS: AppTabDefinition[] = [
  {
    id: 'tab-works',
    title: 'Works',
    route: '/works',
    component: 'WorldInteractionView',
    closable: true,
  },
  {
    id: 'tab-spaces',
    title: 'Spaces',
    route: '/spaces',
    component: 'Spaces',
    closable: true,
  },
  {
    id: 'tab-agents',
    title: 'Agents',
    route: '/agents',
    component: 'Agents',
    closable: true,
  },
  {
    id: 'tab-discovery',
    title: 'Discovery',
    route: '/discovery',
    component: 'Discovery',
    closable: true,
  },
  {
    id: 'tab-history',
    title: 'History',
    route: '/history',
    component: 'History',
    closable: true,
  },
  {
    id: 'tab-profile',
    title: '账号设置',
    route: '/profile',
    component: 'Profile',
    closable: true,
  },
]

export const getAppTabByRoute = (route: string): AppTabDefinition | undefined => {
  return APP_TAB_DEFINITIONS.find(tab => tab.route === route)
}

export const isAppTabRoute = (route: string): boolean => {
  return Boolean(getAppTabByRoute(route))
}
