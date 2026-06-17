import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Allowed redirect destinations (whitelist)
const ALLOWED_REDIRECTS = ['/works', '/spaces', '/agents', '/discovery', '/history', '/profile']

/**
 * Validate redirect URL to prevent open redirect attacks
 * Only allows relative paths starting with / that don't contain protocols or domains
 */
const isValidRedirect = (redirect: string | undefined): string | null => {
  if (!redirect) return null

  // Must start with /
  if (!redirect.startsWith('/')) return null

  // Must not contain protocol (javascript:, data:, etc.)
  const lower = redirect.toLowerCase()
  if (lower.includes('javascript:') || lower.includes('data:') || lower.includes('vbscript:')) {
    return null
  }

  // Must not contain domain (//domain.com or domain.com after protocol)
  if (/\/\/[^/]+/.test(redirect)) return null

  // Normalize path (remove trailing slash, collapse multiple slashes)
  const normalized = redirect.replace(/\/+$/, '').replace(/\/+/g, '/')

  // Check if it's a known safe path or any /works/*, /spaces/*, etc. route
  if (ALLOWED_REDIRECTS.includes(normalized)) return normalized
  if (normalized.startsWith('/works') || normalized.startsWith('/spaces') ||
      normalized.startsWith('/agents') || normalized.startsWith('/discovery') ||
      normalized.startsWith('/history') || normalized.startsWith('/profile')) {
    return normalized
  }

  return null
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    redirect: '/works',
    meta: { titleKey: 'routes.home' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { titleKey: 'routes.login', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { titleKey: 'routes.register', requiresAuth: false }
  },
  {
    path: '/works',
    name: 'Works',
    component: () => import('@/views/WorldInteractionView.vue'),
    meta: { titleKey: 'routes.works', requiresAuth: true }
  },
  {
    path: '/spaces',
    name: 'Spaces',
    component: () => import('@/views/spaces/Spaces.vue'),
    meta: { titleKey: 'routes.spaces', requiresAuth: true }
  },
  {
    path: '/agents',
    name: 'Agents',
    component: () => import('@/views/agents/Agents.vue'),
    meta: { titleKey: 'routes.agents', requiresAuth: true }
  },
  {
    path: '/discovery',
    name: 'Discovery',
    component: () => import('@/views/discovery/Discovery.vue'),
    meta: { titleKey: 'routes.discovery', requiresAuth: true }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/history/History.vue'),
    meta: { titleKey: 'routes.history', requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/user/Profile.vue'),
    meta: { titleKey: 'routes.profile', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { titleKey: 'routes.notFound' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

type AuthNavigationStore = {
  isAuthenticated: boolean
  sessionRestoreChecked: boolean
  restoreSession: () => Promise<boolean>
}

type AuthNavigationTarget = {
  path: string
  fullPath: string
  meta: {
    requiresAuth?: boolean
  }
  query: {
    redirect?: unknown
  }
}

export async function resolveAuthNavigation(
  to: AuthNavigationTarget,
  authStore: AuthNavigationStore,
): Promise<string | null> {
  const requiresAuth = to.meta.requiresAuth !== false
  let hasSession = authStore.isAuthenticated

  if (!hasSession && (requiresAuth || to.path === '/login') && !authStore.sessionRestoreChecked) {
    hasSession = await authStore.restoreSession()
  }

  if (requiresAuth && !hasSession) {
    const fullPath = to.fullPath !== '/login' ? `?redirect=${encodeURIComponent(to.fullPath)}` : ''
    return `/login${fullPath}`
  }

  if (to.path === '/login' && hasSession) {
    const redirect = to.query.redirect as string | undefined
    const safeRedirect = isValidRedirect(redirect)
    return safeRedirect || '/works'
  }

  return null
}

// Navigation guard - check authentication
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()
  const redirect = await resolveAuthNavigation(to, authStore)

  if (redirect) {
    next(redirect)
  } else {
    next()
  }
})

export { isValidRedirect }
export default router
