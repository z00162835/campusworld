/**
 * Authentication API endpoints
 */
import apiClient from './index'
import type { ActivityResponse, Token, LoginRequest, RegisterRequest, RegisterResponse, User } from '@/types/auth'

// OAuth2 requires form-urlencoded format
const toFormUrlEncoded = (data: Record<string, string>) => {
  return Object.entries(data)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
}

export const authApi = {
  /**
   * Login with username and password (OAuth2 password flow)
   */
  login: (data: LoginRequest) =>
    apiClient.post<Token>(
      '/auth/login',
      toFormUrlEncoded({ username: data.username, password: data.password }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    ),

  /**
   * Register a new account
   */
  register: (data: RegisterRequest) =>
    apiClient.post<RegisterResponse>('/auth/register', data),

  /**
   * Logout current user
   */
  logout: () =>
    apiClient.post('/auth/logout', {}, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    }),

  recordActivity: () =>
    apiClient.post<ActivityResponse>('/auth/activity', {}, {
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
      },
    }),

  /**
   * Get current user profile
   */
  getProfile: () =>
    apiClient.get<User>('/accounts/me'),
}
