import type { IconName } from '@/icons'

export interface AppTabDefinition {
  id: string
  title?: string
  titleKey?: string
  route: string
  component: string
  closable: boolean
  iconKey: IconName
}

export const DEFAULT_APP_ROUTE = '/works'

export const APP_TAB_DEFINITIONS: AppTabDefinition[] = [
  {
    id: 'tab-works',
    titleKey: 'routes.works',
    route: '/works',
    component: 'WorldInteractionView',
    closable: true,
    iconKey: 'works',
  },
  {
    id: 'tab-spaces',
    titleKey: 'routes.spaces',
    route: '/spaces',
    component: 'Spaces',
    closable: true,
    iconKey: 'spaces',
  },
  {
    id: 'tab-agents',
    titleKey: 'routes.agents',
    route: '/agents',
    component: 'Agents',
    closable: true,
    iconKey: 'agents',
  },
  {
    id: 'tab-discovery',
    titleKey: 'routes.discovery',
    route: '/discovery',
    component: 'Discovery',
    closable: true,
    iconKey: 'discovery',
  },
  {
    id: 'tab-history',
    titleKey: 'routes.history',
    route: '/history',
    component: 'History',
    closable: true,
    iconKey: 'history',
  },
  {
    id: 'tab-profile',
    titleKey: 'routes.profile',
    route: '/profile',
    component: 'Profile',
    closable: true,
    iconKey: 'profile',
  },
]

export const getAppTabByRoute = (route: string): AppTabDefinition | undefined => {
  return APP_TAB_DEFINITIONS.find(tab => tab.route === route)
}

export const isAppTabRoute = (route: string): boolean => {
  return Boolean(getAppTabByRoute(route))
}
