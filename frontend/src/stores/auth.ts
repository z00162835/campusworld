import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'
import { authApi } from '@/api/auth'
import { isRefreshAuthInvalidationError, tokenApi, type TokenResponse } from '@/api/token'
import { readCsrfToken } from '@/api/csrf'
import { authSessionConfig } from '@/config/authSession'
import type { User, LoginRequest, RegisterRequest } from '@/types/auth'
import { useTabsStore } from './tabs'
import { useSpacesStore } from './spaces'
import { useUserStore } from './user'
import { useWorldSessionStore } from './worldSession'
import { useWorldMapStore } from './worldMap'
import { useWorldHistoryStore } from './worldHistory'
import { useConnectionStore } from './connection'
import { useCommandsStore } from './commands'

const SESSION_BROADCAST_KEY = 'campusworld:auth-session-ended'
const REFRESH_LOCK_KEY = 'campusworld:auth-refresh-lock'
const REFRESH_CHANNEL_NAME = 'campusworld-auth-refresh'
const TAB_ID = `${Date.now()}_${Math.random().toString(36).slice(2)}`

type RefreshLock = {
  owner: string
  expiresAt: number
}

type RefreshBroadcastMessage =
  | { type: 'success'; tokenData: TokenResponse }
  | { type: 'failure'; reason: string }
  | { type: 'transient_failure' }

type RefreshFailureOptions = {
  expireOnFailure?: boolean
}

// Error message mapping for login failures
export const AUTH_ERROR_MESSAGES: Record<number, string> = {
  401: 'auth.errors.invalidCredentials',
  403: 'auth.errors.accountDisabled',
  423: 'auth.errors.accountLocked',
  429: 'auth.errors.rateLimited',
}

// Error message mapping for registration failures
export const REGISTER_ERROR_MESSAGES: Record<number, string> = {
  400: 'auth.errors.invalidRegistration',
  409: 'auth.errors.usernameExists',
  429: 'auth.errors.rateLimited',
}

export function getAuthErrorMessage(status: number): string {
  return AUTH_ERROR_MESSAGES[status] || 'auth.errors.loginFailed'
}

export function getRegisterErrorMessage(status: number): string {
  return REGISTER_ERROR_MESSAGES[status] || 'auth.errors.registerFailed'
}

export function parseRefreshLock(raw: string | null): RefreshLock | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as Partial<RefreshLock>
    if (typeof parsed.owner !== 'string' || typeof parsed.expiresAt !== 'number') return null
    return { owner: parsed.owner, expiresAt: parsed.expiresAt }
  } catch {
    return null
  }
}

export function canAcquireRefreshLock(raw: string | null, now = Date.now(), owner = TAB_ID): boolean {
  const lock = parseRefreshLock(raw)
  return !lock || lock.owner === owner || lock.expiresAt <= now
}

export function buildRefreshLock(owner = TAB_ID, now = Date.now()): string {
  return JSON.stringify({ owner, expiresAt: now + authSessionConfig.refreshLockTtlMs })
}

// Clears only readable client-side session hints. httpOnly auth cookies are backend-owned.
const clearTokenCookie = (name: string) => {
  document.cookie = `${name}=; Max-Age=0; path=/`
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const tokenExpiresAt = ref<number | null>(null)
  const idleExpiresAt = ref<number | null>(null)
  const loading = ref(false)
  const sessionRestoreChecked = ref(false)
  const lastActivityAt = ref(Date.now())
  let restorePromise: Promise<boolean> | null = null
  let refreshPromise: Promise<string | null> | null = null
  let accessRefreshTimer: ReturnType<typeof setTimeout> | null = null
  let idleTimer: ReturnType<typeof setTimeout> | null = null
  let activityListenersAttached = false
  let sessionSyncInitialized = false
  let lastActivitySyncAt = 0
  let broadcastChannel: BroadcastChannel | null = null

  const canUseRefreshCoordination = () => (
    typeof window !== 'undefined'
    && typeof localStorage !== 'undefined'
    && 'BroadcastChannel' in window
  )

  const isAuthenticated = computed(() => {
    if (!token.value) return false
    // Check if token is expired
    if (tokenExpiresAt.value) {
      const now = Math.floor(Date.now() / 1000)
      return tokenExpiresAt.value > now + authSessionConfig.accessRefreshBufferSeconds
    }
    return true
  })

  // Decode JWT to get expiration time (without verification - server will verify)
  const decodeTokenExp = (tokenStr: string): number | null => {
    try {
      const payload = jwtDecode(tokenStr) as { exp?: number }
      return payload.exp || null
    } catch {
      return null
    }
  }

  const applyIdleDeadline = (idleExpiresIn?: number) => {
    if (typeof idleExpiresIn === 'number') {
      idleExpiresAt.value = Date.now() + Math.max(0, idleExpiresIn * 1000)
      return
    }
    if (!idleExpiresAt.value) {
      idleExpiresAt.value = Date.now() + authSessionConfig.idleFallbackMs
    }
  }

  const setTokenData = (tokenData: TokenResponse, options: { recordActivity?: boolean } = {}) => {
    token.value = tokenData.access_token
    tokenExpiresAt.value = decodeTokenExp(tokenData.access_token)
    sessionRestoreChecked.value = true
    if (options.recordActivity !== false) {
      lastActivityAt.value = Date.now()
    }
    applyIdleDeadline(tokenData.idle_expires_in)
    startSessionTimers()
  }

  const clearWorkspaceState = () => {
    useTabsStore().clearTabs()
    useSpacesStore().reset()
    useUserStore().reset()
    useWorldSessionStore().reset({ cancelServerStream: false })
    useWorldMapStore().reset()
    useWorldHistoryStore().reset()
    useConnectionStore().reset()
    useCommandsStore().reset()
  }

  const clearClientState = (options: { clearSessionHintCookies?: boolean } = {}) => {
    stopSessionTimers()
    token.value = null
    user.value = null
    tokenExpiresAt.value = null
    idleExpiresAt.value = null
    lastActivitySyncAt = 0
    sessionRestoreChecked.value = true
    if (options.clearSessionHintCookies !== false) {
      clearTokenCookie('access_token')
      clearTokenCookie('csrf_token')
    }
    clearWorkspaceState()
  }

  const notifySessionEnded = (reason: string) => {
    if (typeof window === 'undefined') return
    window.dispatchEvent(new CustomEvent('auth-session-ended', { detail: { reason } }))
  }

  const broadcastSessionEnded = (reason: string) => {
    if (typeof window === 'undefined') return
    const payload = { reason, at: Date.now() }
    try {
      broadcastChannel?.postMessage(payload)
    } catch {
      // Ignore broadcast failures; local state is already cleared.
    }
    try {
      localStorage.setItem(SESSION_BROADCAST_KEY, JSON.stringify(payload))
      localStorage.removeItem(SESSION_BROADCAST_KEY)
    } catch {
      // Storage may be unavailable in private mode.
    }
  }

  const expireSession = (reason = 'expired', options: { broadcast?: boolean } = {}) => {
    clearClientState()
    notifySessionEnded(reason)
    if (options.broadcast !== false) {
      broadcastSessionEnded(reason)
    }
  }

  const tryAcquireRefreshLock = () => {
    if (!canUseRefreshCoordination()) return true
    try {
      if (!canAcquireRefreshLock(localStorage.getItem(REFRESH_LOCK_KEY), Date.now(), TAB_ID)) return false
      localStorage.setItem(REFRESH_LOCK_KEY, buildRefreshLock(TAB_ID))
      return parseRefreshLock(localStorage.getItem(REFRESH_LOCK_KEY))?.owner === TAB_ID
    } catch {
      return true
    }
  }

  const releaseRefreshLock = () => {
    if (!canUseRefreshCoordination()) return
    try {
      if (parseRefreshLock(localStorage.getItem(REFRESH_LOCK_KEY))?.owner === TAB_ID) {
        localStorage.removeItem(REFRESH_LOCK_KEY)
      }
    } catch {
      // Storage may be unavailable in private mode.
    }
  }

  const publishRefreshResult = (message: RefreshBroadcastMessage) => {
    if (!canUseRefreshCoordination()) return
    try {
      const channel = new BroadcastChannel(REFRESH_CHANNEL_NAME)
      channel.postMessage(message)
      channel.close()
    } catch {
      // Waiting tabs will time out and handle the session locally.
    }
  }

  const waitForRefreshResult = () => new Promise<TokenResponse | null | undefined>((resolve) => {
    if (!canUseRefreshCoordination()) {
      resolve(undefined)
      return
    }

    let settled = false
    let timeoutId: ReturnType<typeof setTimeout> | null = null
    let channel: BroadcastChannel | null = null

    const settle = (tokenData: TokenResponse | null | undefined) => {
      if (settled) return
      settled = true
      if (timeoutId) clearTimeout(timeoutId)
      channel?.close()
      resolve(tokenData)
    }

    try {
      channel = new BroadcastChannel(REFRESH_CHANNEL_NAME)
      channel.onmessage = (event) => {
        const message = event.data as RefreshBroadcastMessage
        if (message?.type === 'success') settle(message.tokenData)
        if (message?.type === 'failure') settle(null)
        if (message?.type === 'transient_failure') settle(undefined)
      }
      timeoutId = setTimeout(() => settle(undefined), authSessionConfig.refreshWaitTimeoutMs)
    } catch {
      settle(undefined)
    }
  })

  const handleRefreshFailure = (expireReason: string, options: RefreshFailureOptions = {}) => {
    if (options.expireOnFailure === false) {
      clearClientState()
      return
    }
    expireSession(expireReason)
  }

  const refreshWithCookieAndBroadcast = async (
    expireReason: string,
    options: RefreshFailureOptions = {},
  ) => {
    try {
      const tokenData = await tokenApi.refreshWithCookie()
      publishRefreshResult({ type: 'success', tokenData })
      return tokenData
    } catch (error) {
      if (!isRefreshAuthInvalidationError(error)) {
        publishRefreshResult({ type: 'transient_failure' })
        throw error
      }
      publishRefreshResult({ type: 'failure', reason: expireReason })
      handleRefreshFailure(expireReason, options)
      return null
    } finally {
      releaseRefreshLock()
    }
  }

  const refreshTokenDataWithCoordination = async (
    expireReason = 'refresh_failed',
    options: RefreshFailureOptions = {},
  ) => {
    if (!tryAcquireRefreshLock()) {
      const tokenData = await waitForRefreshResult()
      if (tokenData !== undefined) return tokenData
      if (!tryAcquireRefreshLock()) {
        throw new Error('Refresh coordination unavailable')
      }
    }

    return refreshWithCookieAndBroadcast(expireReason, options)
  }

  // Fetch user profile from API
  const fetchUser = async (): Promise<User | null> => {
    if (!token.value) return null

    try {
      const { data } = await authApi.getProfile()
      user.value = data
      return data
    } catch {
      return null
    }
  }

  const login = async (credentials: LoginRequest): Promise<{ success: boolean; status?: number }> => {
    loading.value = true
    try {
      const response = await authApi.login(credentials)
      setTokenData(response.data, { recordActivity: true })
      // Fetch user profile after successful login
      await fetchUser()
      return { success: true }
    } catch (error: any) {
      return { success: false, status: error.response?.status || 0 }
    } finally {
      loading.value = false
    }
  }

  const register = async (credentials: RegisterRequest): Promise<{ success: boolean; status?: number }> => {
    loading.value = true
    try {
      await authApi.register(credentials)
      return { success: true }
    } catch (error: any) {
      return { success: false, status: error.response?.status || 0 }
    } finally {
      loading.value = false
    }
  }

  const logout = async (): Promise<{ success: boolean; error?: string }> => {
    const csrfToken = readCsrfToken()
    expireSession('logout')

    // Wrap API call in timeout to prevent hanging
    const logoutPromise = authApi.logout(csrfToken)
    const timeoutPromise = new Promise<void>((resolve) => {
      setTimeout(() => resolve(), authSessionConfig.logoutTimeoutMs)
    })

    try {
      await Promise.race([logoutPromise, timeoutPromise])
    } catch (error: any) {
      // Log but don't block logout - client state should be cleared regardless
      console.warn('Logout API failed:', error?.message)
    }
    return { success: true }
  }

  const restoreSession = async (): Promise<boolean> => {
    if (isAuthenticated.value) return true
    if (sessionRestoreChecked.value) return false
    if (!readCsrfToken()) {
      sessionRestoreChecked.value = true
      return false
    }

    if (restorePromise) return restorePromise

    restorePromise = (async () => {
      sessionRestoreChecked.value = true
      try {
        const tokenData = await refreshTokenDataWithCoordination('restore_failed', { expireOnFailure: false })
        if (!tokenData) return false
        setTokenData(tokenData, { recordActivity: false })
        await fetchUser()
        return isAuthenticated.value
      } catch {
        clearClientState({ clearSessionHintCookies: false })
        return false
      } finally {
        restorePromise = null
      }
    })()

    return restorePromise
  }

  // Initialize token from cookie on store creation
  const initTokenExpiration = () => {
    token.value = null
    tokenExpiresAt.value = null
    idleExpiresAt.value = null
  }

  const isIdleExpired = () => {
    return Boolean(idleExpiresAt.value && Date.now() >= idleExpiresAt.value)
  }

  const refreshAccessToken = async (): Promise<string | null> => {
    if (isIdleExpired()) {
      expireSession('idle_timeout')
      return null
    }

    if (refreshPromise) return refreshPromise

    refreshPromise = (async () => {
      const tokenData = await refreshTokenDataWithCoordination()
      if (!tokenData) return null
      setTokenData(tokenData, { recordActivity: false })
      return tokenData.access_token
    })().finally(() => {
      refreshPromise = null
    })

    return refreshPromise
  }

  const clearAccessRefreshTimer = () => {
    if (accessRefreshTimer) {
      clearTimeout(accessRefreshTimer)
      accessRefreshTimer = null
    }
  }

  const clearIdleTimer = () => {
    if (idleTimer) {
      clearTimeout(idleTimer)
      idleTimer = null
    }
  }

  const scheduleAccessRefresh = () => {
    clearAccessRefreshTimer()
    if (!token.value || !tokenExpiresAt.value) return

    const refreshInMs = tokenExpiresAt.value * 1000 - Date.now() - authSessionConfig.accessRefreshBufferMs
    accessRefreshTimer = setTimeout(() => {
      refreshAccessToken().catch(() => {
        // Keep the current in-memory token on transient refresh failures.
      })
    }, Math.max(refreshInMs, 0))
  }

  const scheduleIdleTimeout = () => {
    clearIdleTimer()
    if (!token.value || !idleExpiresAt.value) return

    const expiresInMs = idleExpiresAt.value - Date.now()
    idleTimer = setTimeout(() => {
      expireSession('idle_timeout')
    }, Math.max(expiresInMs, 0))
  }

  const recordActivity = () => {
    if (!token.value) return
    lastActivityAt.value = Date.now()
    syncActivityWithServer()
    scheduleIdleTimeout()
  }

  const syncActivityWithServer = () => {
    const now = Date.now()
    if (now - lastActivitySyncAt < authSessionConfig.activitySyncIntervalMs) return
    lastActivitySyncAt = now
    authApi.recordActivity()
      .then(({ data }) => {
        applyIdleDeadline(data.idle_expires_in)
        scheduleIdleTimeout()
      })
      .catch(() => {
        // API interceptors handle expired sessions; activity sync is best effort.
      })
  }

  const recordVisibilityActivity = () => {
    if (document.visibilityState === 'visible') recordActivity()
  }

  const attachActivityListeners = () => {
    if (activityListenersAttached || typeof window === 'undefined') return
    ;['click', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach(eventName => {
      window.addEventListener(eventName, recordActivity, { passive: true })
    })
    document.addEventListener('visibilitychange', recordVisibilityActivity)
    activityListenersAttached = true
  }

  const detachActivityListeners = () => {
    if (!activityListenersAttached || typeof window === 'undefined') return
    ;['click', 'keydown', 'mousemove', 'scroll', 'touchstart'].forEach(eventName => {
      window.removeEventListener(eventName, recordActivity)
    })
    document.removeEventListener('visibilitychange', recordVisibilityActivity)
    activityListenersAttached = false
  }

  const initializeSessionSync = () => {
    if (sessionSyncInitialized || typeof window === 'undefined') return
    if ('BroadcastChannel' in window) {
      broadcastChannel = new BroadcastChannel('campusworld-auth')
      broadcastChannel.onmessage = (event) => {
        expireSession(event.data?.reason || 'remote_session_ended', { broadcast: false })
      }
    }
    window.addEventListener('storage', (event) => {
      if (event.key !== SESSION_BROADCAST_KEY || !event.newValue) return
      try {
        const payload = JSON.parse(event.newValue)
        expireSession(payload.reason || 'remote_session_ended', { broadcast: false })
      } catch {
        expireSession('remote_session_ended', { broadcast: false })
      }
    })
    sessionSyncInitialized = true
  }

  function startSessionTimers() {
    initializeSessionSync()
    attachActivityListeners()
    scheduleAccessRefresh()
    scheduleIdleTimeout()
  }

  function stopSessionTimers() {
    clearAccessRefreshTimer()
    clearIdleTimer()
    detachActivityListeners()
  }

  // Call on store creation
  initTokenExpiration()

  return {
    user,
    token,
    tokenExpiresAt,
    idleExpiresAt,
    loading,
    sessionRestoreChecked,
    isAuthenticated,
    login,
    register,
    logout,
    setTokenData,
    clearClientState,
    expireSession,
    restoreSession,
    fetchUser,
    refreshAccessToken,
    startSessionTimers,
    stopSessionTimers,
    recordActivity,
    initTokenExpiration,
  }
})
