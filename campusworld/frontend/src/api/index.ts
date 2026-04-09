/**
 * Axios API client with interceptors
 */
import axios from 'axios'
import router from '@/router'
import { tokenApi } from './token'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // Required for cookies
})

// Track if we're already handling a 401 to prevent infinite loops
let isRefreshing = false
let refreshSubscribers: Array<(token: string) => void> = []

const subscribeTokenRefresh = (callback: (token: string) => void) => {
  refreshSubscribers.push(callback)
}

const onTokenRefreshed = (token: string) => {
  refreshSubscribers.forEach(callback => callback(token))
  refreshSubscribers = []
}

// Helper to get access token from cookie
const getAccessTokenFromCookie = (): string | null => {
  const match = document.cookie.match(/access_token=([^;]+)/)
  return match ? match[1] : null
}

// Request interceptor: attach JWT token from cookie
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessTokenFromCookie()
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
      if (isRefreshing) {
        // Already refreshing, queue the request
        return new Promise((resolve) => {
          subscribeTokenRefresh((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            resolve(apiClient(originalRequest))
          })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        // Try to refresh using cookie-based refresh endpoint
        const data = await tokenApi.refreshWithCookie()

        if (data.access_token) {
          // Sync auth store with new tokens
          const { useAuthStore } = await import('@/stores/auth')
          const authStore = useAuthStore()
          authStore.syncFromStorage()

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${data.access_token}`
          onTokenRefreshed(data.access_token)
          isRefreshing = false
          return apiClient(originalRequest)
        }
      } catch (refreshError) {
        // Refresh failed, clear cookies and redirect to login
        isRefreshing = false
        // Clear cookies via document.cookie
        document.cookie = 'access_token=; Max-Age=0; path=/'
        document.cookie = 'refresh_token=; Max-Age=0; path=/'
        router.push('/login')
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

export default apiClient
