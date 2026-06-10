export interface AppTabDefinition {
  id: string
  title?: string
  titleKey?: string
  route: string
  component: string
  closable: boolean
}

export const DEFAULT_APP_ROUTE = '/works'

export const APP_TAB_DEFINITIONS: AppTabDefinition[] = [
  {
    id: 'tab-works',
    titleKey: 'routes.works',
    route: '/works',
    component: 'WorldInteractionView',
    closable: true,
  },
  {
    id: 'tab-spaces',
    titleKey: 'routes.spaces',
    route: '/spaces',
    component: 'Spaces',
    closable: true,
  },
  {
    id: 'tab-agents',
    titleKey: 'routes.agents',
    route: '/agents',
    component: 'Agents',
    closable: true,
  },
  {
    id: 'tab-discovery',
    titleKey: 'routes.discovery',
    route: '/discovery',
    component: 'Discovery',
    closable: true,
  },
  {
    id: 'tab-history',
    titleKey: 'routes.history',
    route: '/history',
    component: 'History',
    closable: true,
  },
  {
    id: 'tab-profile',
    titleKey: 'routes.profile',
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
