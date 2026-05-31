import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'
import { authApi } from '@/api/auth'
import { tokenApi, type TokenResponse } from '@/api/token'
import type { User, LoginRequest } from '@/types/auth'
import { useTabsStore } from './tabs'
import { useSpacesStore } from './spaces'
import { useUserStore } from './user'

const TOKEN_EXPIRE_BUFFER_SECONDS = 60 // Refresh 1 minute before actual expiration
const ACCESS_REFRESH_BUFFER_MS = TOKEN_EXPIRE_BUFFER_SECONDS * 1000
const IDLE_TIMEOUT_MS = 30 * 60 * 1000
const ACTIVITY_SYNC_INTERVAL_MS = 60 * 1000
const SESSION_BROADCAST_KEY = 'campusworld:auth-session-ended'

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

// Clears only readable fallback cookies. httpOnly auth cookies are cleared by the backend.
const clearTokenCookie = (name: string) => {
  document.cookie = `${name}=; Max-Age=0; path=/`
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const tokenExpiresAt = ref<number | null>(null)
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

  const isAuthenticated = computed(() => {
    if (!token.value) return false
    // Check if token is expired
    if (tokenExpiresAt.value) {
      const now = Math.floor(Date.now() / 1000)
      return tokenExpiresAt.value > now + TOKEN_EXPIRE_BUFFER_SECONDS
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

  const applyServerIdleRemaining = (idleExpiresIn?: number) => {
    if (typeof idleExpiresIn !== 'number') return
    const elapsedMs = Math.max(0, IDLE_TIMEOUT_MS - idleExpiresIn * 1000)
    lastActivityAt.value = Date.now() - elapsedMs
  }

  const setTokenData = (tokenData: TokenResponse, options: { recordActivity?: boolean } = {}) => {
    token.value = tokenData.access_token
    tokenExpiresAt.value = decodeTokenExp(tokenData.access_token)
    sessionRestoreChecked.value = true
    if (options.recordActivity !== false) {
      lastActivityAt.value = Date.now()
    } else {
      applyServerIdleRemaining(tokenData.idle_expires_in)
    }
    startSessionTimers()
  }

  const clearWorkspaceState = () => {
    useTabsStore().clearTabs()
    useSpacesStore().reset()
    useUserStore().reset()
    void import('./worldSession').then(({ useWorldSessionStore }) => {
      useWorldSessionStore().reset()
    })
    void import('./worldHistory').then(({ useWorldHistoryStore }) => {
      useWorldHistoryStore().reset()
    })
    void import('./connection').then(({ useConnectionStore }) => {
      useConnectionStore().reset()
    })
    void import('./commands').then(({ useCommandsStore }) => {
      useCommandsStore().reset()
    })
  }

  const clearClientState = () => {
    stopSessionTimers()
    token.value = null
    user.value = null
    tokenExpiresAt.value = null
    lastActivitySyncAt = 0
    sessionRestoreChecked.value = true
    clearTokenCookie('access_token')
    clearTokenCookie('refresh_token')
    clearTokenCookie('__Host-refresh_token')
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

  const logout = async (): Promise<{ success: boolean; error?: string }> => {
    expireSession('logout')

    // Wrap API call in timeout to prevent hanging
    const logoutPromise = authApi.logout()
    const timeoutPromise = new Promise<void>((resolve) => {
      setTimeout(() => resolve(), 3000)
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

    if (restorePromise) return restorePromise

    restorePromise = (async () => {
      sessionRestoreChecked.value = true
      try {
        const tokenData = await tokenApi.refreshWithCookie()
        setTokenData(tokenData, { recordActivity: false })
        await fetchUser()
        return isAuthenticated.value
      } catch {
        expireSession('restore_failed')
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
  }

  const isIdleExpired = () => {
    return Date.now() - lastActivityAt.value >= IDLE_TIMEOUT_MS
  }

  const refreshAccessToken = async (): Promise<string | null> => {
    if (isIdleExpired()) {
      expireSession('idle_timeout')
      return null
    }

    if (refreshPromise) return refreshPromise

    refreshPromise = (async () => {
      try {
        const tokenData = await tokenApi.refreshWithCookie()
        setTokenData(tokenData, { recordActivity: false })
        return tokenData.access_token
      } catch {
        expireSession('refresh_failed')
        return null
      } finally {
        refreshPromise = null
      }
    })()

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

    const refreshInMs = tokenExpiresAt.value * 1000 - Date.now() - ACCESS_REFRESH_BUFFER_MS
    accessRefreshTimer = setTimeout(() => {
      refreshAccessToken()
    }, Math.max(refreshInMs, 0))
  }

  const scheduleIdleTimeout = () => {
    clearIdleTimer()
    if (!token.value) return

    const expiresInMs = IDLE_TIMEOUT_MS - (Date.now() - lastActivityAt.value)
    idleTimer = setTimeout(() => {
      expireSession('idle_timeout')
    }, Math.max(expiresInMs, 0))
  }

  const recordActivity = () => {
    if (!token.value) return
    lastActivityAt.value = Date.now()
    scheduleIdleTimeout()
    syncActivityWithServer()
  }

  const syncActivityWithServer = () => {
    const now = Date.now()
    if (now - lastActivitySyncAt < ACTIVITY_SYNC_INTERVAL_MS) return
    lastActivitySyncAt = now
    authApi.recordActivity()
      .then(({ data }) => {
        applyServerIdleRemaining(data.idle_expires_in)
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
    loading,
    isAuthenticated,
    login,
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
