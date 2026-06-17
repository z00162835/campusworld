import { describe, expect, it } from 'vitest'
import { resolveAuthNavigation, routes } from './index'

describe('router i18n metadata', () => {
  it('uses titleKey metadata for all routes instead of literal titles', () => {
    for (const route of routes) {
      expect(route.meta?.title).toBeUndefined()
      expect(route.meta?.titleKey).toEqual(expect.any(String))
    }
  })
})

describe('auth navigation guard decisions', () => {
  it('restores a cookie-backed session before showing the login page', async () => {
    const restoreSession = async () => true

    await expect(resolveAuthNavigation(
      {
        path: '/login',
        fullPath: '/login',
        meta: { requiresAuth: false },
        query: {},
      },
      {
        isAuthenticated: false,
        sessionRestoreChecked: false,
        restoreSession,
      },
    )).resolves.toBe('/works')
  })

  it('keeps a protected route when cookie-backed restore succeeds', async () => {
    await expect(resolveAuthNavigation(
      {
        path: '/works',
        fullPath: '/works',
        meta: { requiresAuth: true },
        query: {},
      },
      {
        isAuthenticated: false,
        sessionRestoreChecked: false,
        restoreSession: async () => true,
      },
    )).resolves.toBeNull()
  })

  it('preserves a safe redirect when restoring from the login page', async () => {
    await expect(resolveAuthNavigation(
      {
        path: '/login',
        fullPath: '/login?redirect=%2Fprofile',
        meta: { requiresAuth: false },
        query: { redirect: '/profile' },
      },
      {
        isAuthenticated: false,
        sessionRestoreChecked: false,
        restoreSession: async () => true,
      },
    )).resolves.toBe('/profile')
  })
})
