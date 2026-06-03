/**
 * Axios API client with interceptors
 */
import axios from 'axios'
import router from '@/router'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Required for cookies
})

// Track if we're already handling a 401 to prevent infinite loops
let isRefreshing = false
let refreshPromise: Promise<string> | null = null

const AUTH_ENDPOINTS = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout']

const shouldSkipRefresh = (url?: string): boolean => {
  if (!url) return false
  return AUTH_ENDPOINTS.some(endpoint => url.includes(endpoint))
}

// Helper to get access token from authStore (memory)
const getAccessToken = async (): Promise<string | null> => {
  try {
    // Dynamic import to avoid circular dependency and timing issues
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    if (!authStore.token) return null
    const now = Math.floor(Date.now() / 1000)
    if (authStore.tokenExpiresAt && authStore.tokenExpiresAt <= now + 60) {
      return authStore.refreshAccessToken()
    }
    return authStore.token
  } catch {
    return null
  }
}

// Request interceptor: attach JWT token from authStore (memory)
apiClient.interceptors.request.use(
  async (config) => {
    const token = shouldSkipRefresh(config.url) ? null : await getAccessToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 unauthorized
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Handle 401 - attempt token refresh or redirect to login
    if (error.response?.status === 401 && !originalRequest._retry && !shouldSkipRefresh(originalRequest.url)) {
      if (isRefreshing && refreshPromise) {
        // Already refreshing, wait for the refresh to complete
        return refreshPromise.then((token: string) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return apiClient(originalRequest)
        }).catch(() => {
          // If refresh fails, reject
          return Promise.reject(error)
        })
      }

      originalRequest._retry = true

      return refreshAccessTokenOnce().then((token: string) => {
        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${token}`
        return apiClient(originalRequest)
      }).catch(() => {
        return Promise.reject(error)
      })
    }

    return Promise.reject(error)
  }
)

async function refreshAccessTokenOnce(): Promise<string> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }
  isRefreshing = true
  refreshPromise = (async () => {
    try {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      const refreshedToken = await authStore.refreshAccessToken()
      if (refreshedToken) return refreshedToken
      throw new Error('No access token in refresh response')
    } catch (refreshError) {
      const { useAuthStore } = await import('@/stores/auth')
      const authStore = useAuthStore()
      authStore.expireSession('refresh_failed')
      router.push('/login')
      throw refreshError
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()
  return refreshPromise
}

/** Same token resolution as axios (proactive refresh + shared refresh lock). */
export async function getAccessTokenForRequest(): Promise<string | null> {
  return getAccessToken()
}

/** ``fetch`` with Bearer token and one 401 refresh retry (for SSE streams). */
export async function authorizedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && init.body != null) {
    headers.set('Content-Type', 'application/json')
  }
  let token = await getAccessToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  let response = await fetch(input, { ...init, headers, credentials: 'include' })
  if (response.status !== 401 || shouldSkipRefresh(input)) {
    return response
  }

  token = await refreshAccessTokenOnce()
  headers.set('Authorization', `Bearer ${token}`)
  return fetch(input, { ...init, headers, credentials: 'include' })
}

export default apiClient
