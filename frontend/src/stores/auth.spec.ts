import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
import { useCommandsStore } from './commands'
import { useConnectionStore } from './connection'
import { useSpacesStore } from './spaces'
import { useTabsStore } from './tabs'
import { useUserStore } from './user'
import { useWorldHistoryStore } from './worldHistory'
import { useWorldSessionStore } from './worldSession'
import { authApi } from '@/api/auth'
import { tokenApi } from '@/api/token'

vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
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
    vi.useRealTimers()
    vi.mocked(authApi.getProfile).mockResolvedValue({
      data: { id: 1, username: 'alice', email: 'alice@example.com' },
    } as any)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps the login token in memory after successful login', async () => {
    const accessToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(authApi.login).mockResolvedValue({
      data: { access_token: accessToken, token_type: 'bearer' },
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

  it('returns a mapped registration failure result without restoring session', async () => {
    vi.mocked(authApi.register).mockRejectedValue({ response: { status: 409 } })

    const authStore = useAuthStore()

    await expect(authStore.register({ username: 'alice', password: 'secret' })).resolves.toEqual({
      success: false,
      status: 409,
    })

    expect(authStore.token).toBeNull()
    expect(tokenApi.refreshWithCookie).not.toHaveBeenCalled()
  })

  it('restores an app session from the httpOnly refresh cookie', async () => {
    const accessToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(tokenApi.refreshWithCookie).mockResolvedValue({
      access_token: accessToken,
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

  it('refreshes access token before expiration', async () => {
    vi.useFakeTimers()
    const firstToken = createToken(Math.floor(Date.now() / 1000) + 61)
    const refreshedToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(authApi.login).mockResolvedValue({
      data: { access_token: firstToken, token_type: 'bearer' },
    } as any)
    vi.mocked(tokenApi.refreshWithCookie).mockResolvedValue({
      access_token: refreshedToken,
      token_type: 'bearer',
    })

    const authStore = useAuthStore()
    await authStore.login({ username: 'alice', password: 'secret' })
    await vi.advanceTimersByTimeAsync(1000)

    expect(tokenApi.refreshWithCookie).toHaveBeenCalledTimes(1)
    expect(authStore.token).toBe(refreshedToken)
  })

  it('does not let silent refresh reset the idle timeout', async () => {
    vi.useFakeTimers()
    const firstToken = createToken(Math.floor(Date.now() / 1000) + 61)
    const refreshedToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(authApi.login).mockResolvedValue({
      data: { access_token: firstToken, token_type: 'bearer' },
    } as any)
    vi.mocked(tokenApi.refreshWithCookie).mockResolvedValue({
      access_token: refreshedToken,
      token_type: 'bearer',
    })

    const authStore = useAuthStore()
    await authStore.login({ username: 'alice', password: 'secret' })
    await vi.advanceTimersByTimeAsync(1000)
    expect(authStore.token).toBe(refreshedToken)

    await vi.advanceTimersByTimeAsync((30 * 60 * 1000) - 1000)
    expect(authStore.token).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('expires the local session after idle timeout', async () => {
    vi.useFakeTimers()
    const accessToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(authApi.login).mockResolvedValue({
      data: { access_token: accessToken, token_type: 'bearer' },
    } as any)

    const authStore = useAuthStore()
    await authStore.login({ username: 'alice', password: 'secret' })
    await vi.advanceTimersByTimeAsync(30 * 60 * 1000)

    expect(authStore.token).toBeNull()
    expect(authStore.isAuthenticated).toBe(false)
  })

  it('clears user-scoped stores synchronously on logout', async () => {
    const accessToken = createToken(Math.floor(Date.now() / 1000) + 3600)
    vi.mocked(authApi.logout).mockResolvedValue({} as any)

    const authStore = useAuthStore()
    authStore.setTokenData({ access_token: accessToken, token_type: 'bearer' })

    const tabsStore = useTabsStore()
    tabsStore.addTab({
      id: 'tab-profile',
      title: 'Profile',
      route: '/profile',
      component: 'Profile',
      closable: true,
    })

    const spacesStore = useSpacesStore()
    spacesStore.searchKeyword = 'lab'
    spacesStore.nodes.world = [{ id: 1, name: 'World', type_code: 'world' } as any]

    const userStore = useUserStore()
    userStore.profile = { id: 1, username: 'alice' }

    const worldSessionStore = useWorldSessionStore()
    worldSessionStore.interactionState = {
      session: { id: 'sess1', currentSpaceId: 'space1' },
      decision_center: { focus: null, decisionEvents: [], activeTask: null },
      focus_map: { mode: 'focus', nodes: [], edges: [], agentPresences: [] },
      context_summary: null,
    } as any

    const worldHistoryStore = useWorldHistoryStore()
    worldHistoryStore.groups = [{ date: 'today', items: [] } as any]

    const connectionStore = useConnectionStore()
    connectionStore.setStatus('connected')

    const commandsStore = useCommandsStore()
    commandsStore.commands = [{ name: 'look', description: 'Look', aliases: [], command_type: 'GAME' }]

    const logoutResult = authStore.logout()

    expect(authStore.token).toBeNull()
    expect(tabsStore.tabs).toEqual([])
    expect(spacesStore.searchKeyword).toBe('')
    expect(spacesStore.nodes.world).toEqual([])
    expect(userStore.profile).toBeNull()
    expect(worldSessionStore.interactionState).toBeNull()
    expect(worldHistoryStore.groups).toEqual([])
    expect(connectionStore.status).toBe('disconnected')
    expect(commandsStore.commands).toEqual([])

    await expect(logoutResult).resolves.toEqual({ success: true })
  })
})
