/**
 * Axios API client with interceptors
 */
import axios from 'axios'
import router from '@/router'
import { tokenApi } from './token'

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

// Helper to get access token from authStore (memory)
const getAccessToken = async (): Promise<string | null> => {
  try {
    // Dynamic import to avoid circular dependency and timing issues
    const { useAuthStore } = await import('@/stores/auth')
    const authStore = useAuthStore()
    return authStore.token
  } catch {
    return null
  }
}

// Request interceptor: attach JWT token from authStore (memory)
apiClient.interceptors.request.use(
  async (config) => {
    const token = await getAccessToken()
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
    if (error.response?.status === 401 && !originalRequest._retry) {
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
      isRefreshing = true

      // Create a refresh promise that all queued requests will wait for
      refreshPromise = (async () => {
        try {
          // Try to refresh using cookie-based refresh endpoint
          const data = await tokenApi.refreshWithCookie()

          if (data.access_token) {
            // Sync auth store with new tokens
            const { useAuthStore } = await import('@/stores/auth')
            const authStore = useAuthStore()
            authStore.syncFromStorage()

            return data.access_token
          }
          throw new Error('No access token in refresh response')
        } catch (refreshError) {
          // Refresh failed, clear cookies and redirect to login
          document.cookie = 'access_token=; Max-Age=0; path=/'
          document.cookie = 'refresh_token=; Max-Age=0; path=/'
          router.push('/login')
          throw refreshError
        } finally {
          isRefreshing = false
          refreshPromise = null
        }
      })()

      return refreshPromise.then((token: string) => {
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

export default apiClient
