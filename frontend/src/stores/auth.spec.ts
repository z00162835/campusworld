import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { authApi } from '@/api/auth'
import { tokenApi } from '@/api/token'

vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    logout: vi.fn(),
    getProfile: vi.fn(),
  },
}))

vi.mock('@/api/token', () => ({
  tokenApi: {
    refreshWithCookie: vi.fn(),
  },
}))

const createToken = (exp: number) => {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({ exp })).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  return `${header}.${payload}.`
}

describe('auth store session handling', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(authApi.getProfile).mockResolvedValue({
      data: { id: 1, username: 'alice', email: 'alice@example.com' },
    } as any)
  })

  it('keeps the login token in memory after successful login', async () => {
    const accessToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(authApi.login).mockResolvedValue({
      data: { access_token: accessToken, refresh_token: 'refresh-token', token_type: 'bearer' },
    } as any)

    const authStore = useAuthStore()

    await expect(authStore.login({ username: 'alice', password: 'secret' })).resolves.toEqual({ success: true })

    expect(authStore.token).toBe(accessToken)
    expect(authStore.isAuthenticated).toBe(true)
  })

  it('returns a generic login failure result without restoring session', async () => {
    vi.mocked(authApi.login).mockRejectedValue({ response: { status: 401 } })

    const authStore = useAuthStore()

    await expect(authStore.login({ username: 'alice', password: 'wrong' })).resolves.toEqual({
      success: false,
      status: 401,
    })

    expect(authStore.token).toBeNull()
    expect(tokenApi.refreshWithCookie).not.toHaveBeenCalled()
  })

  it('restores an app session from the httpOnly refresh cookie', async () => {
    const accessToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(tokenApi.refreshWithCookie).mockResolvedValue({
      access_token: accessToken,
      refresh_token: 'rotated-refresh-token',
      token_type: 'bearer',
    })

    const authStore = useAuthStore()

    await expect(authStore.restoreSession()).resolves.toBe(true)

    expect(tokenApi.refreshWithCookie).toHaveBeenCalledTimes(1)
    expect(authStore.token).toBe(accessToken)
    expect(authStore.isAuthenticated).toBe(true)
  })

  it('does not repeatedly attempt session restore after a failed restore', async () => {
    vi.mocked(tokenApi.refreshWithCookie).mockRejectedValue(new Error('expired'))

    const authStore = useAuthStore()

    await expect(authStore.restoreSession()).resolves.toBe(false)
    await expect(authStore.restoreSession()).resolves.toBe(false)

    expect(tokenApi.refreshWithCookie).toHaveBeenCalledTimes(1)
  })
})
