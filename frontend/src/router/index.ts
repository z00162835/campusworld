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

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'Home',
    redirect: '/works',
    meta: { title: '首页' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '登录', requiresAuth: false }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { title: '注册', requiresAuth: false }
  },
  {
    path: '/works',
    name: 'Works',
    component: () => import('@/views/Home.vue'),
    meta: { title: 'Works', requiresAuth: true }
  },
  {
    path: '/spaces',
    name: 'Spaces',
    component: () => import('@/views/spaces/Spaces.vue'),
    meta: { title: 'Spaces', requiresAuth: true }
  },
  {
    path: '/agents',
    name: 'Agents',
    component: () => import('@/views/agents/Agents.vue'),
    meta: { title: 'Agents', requiresAuth: true }
  },
  {
    path: '/discovery',
    name: 'Discovery',
    component: () => import('@/views/discovery/Discovery.vue'),
    meta: { title: 'Discovery', requiresAuth: true }
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('@/views/history/History.vue'),
    meta: { title: 'History', requiresAuth: true }
  },
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('@/views/user/Profile.vue'),
    meta: { title: '个人资料', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guard - check authentication
router.beforeEach((to, _from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !authStore.isAuthenticated) {
    // Store the attempted URL for redirecting after login
    const fullPath = to.fullPath !== '/login' ? `?redirect=${encodeURIComponent(to.fullPath)}` : ''
    next(`/login${fullPath}`)
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    // Already logged in, redirect to safe destination only
    const redirect = to.query.redirect as string | undefined
    const safeRedirect = isValidRedirect(redirect)
    next(safeRedirect || '/works')
  } else {
    next()
  }
})

export { isValidRedirect }
export default router
