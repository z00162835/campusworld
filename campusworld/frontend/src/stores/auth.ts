import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { jwtDecode } from 'jwt-decode'
import { authApi } from '@/api/auth'
import type { User, LoginRequest } from '@/types/auth'

const TOKEN_EXPIRE_BUFFER_SECONDS = 60 // Refresh 1 minute before actual expiration

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

// Helper to get token from cookie
const getTokenFromCookie = (name: string): string | null => {
  const match = document.cookie.match(new RegExp(`(${name})=([^;]+)`))
  return match ? match[2] : null
}

// Helper to clear token cookie
const clearTokenCookie = (name: string) => {
  document.cookie = `${name}=; Max-Age=0; path=/`
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  const tokenExpiresAt = ref<number | null>(null)
  const loading = ref(false)

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

  // Sync store state from cookies (called after external token updates like refresh)
  const syncFromStorage = () => {
    const storedToken = getTokenFromCookie('access_token')
    const storedRefreshToken = getTokenFromCookie('refresh_token')

    token.value = storedToken
    refreshToken.value = storedRefreshToken
    tokenExpiresAt.value = storedToken ? decodeTokenExp(storedToken) : null
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

  const login = async (credentials: LoginRequest) => {
    loading.value = true
    try {
      await authApi.login(credentials)
      // Tokens are set via httpOnly cookies on the backend
      syncFromStorage()
      // Fetch user profile after successful login
      await fetchUser()
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = async (): Promise<{ success: boolean; error?: string }> => {
    try {
      await authApi.logout()
    } catch (error: any) {
      // Log but don't block logout - client state should be cleared regardless
      console.warn('Logout API failed:', error?.message)
    } finally {
      token.value = null
      user.value = null
      refreshToken.value = null
      tokenExpiresAt.value = null
      clearTokenCookie('access_token')
      clearTokenCookie('refresh_token')
    }
    return { success: true }
  }

  // Initialize token from cookie on store creation
  const initTokenExpiration = () => {
    syncFromStorage()
  }

  // Call on store creation
  initTokenExpiration()

  return {
    user,
    token,
    refreshToken,
    loading,
    isAuthenticated,
    login,
    logout,
    syncFromStorage,
    fetchUser,
    initTokenExpiration,
  }
})
