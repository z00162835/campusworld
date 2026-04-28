/**
 * Authentication API endpoints
 */
import apiClient from './index'
import type { Token, LoginRequest, RegisterRequest, User } from '@/types/auth'

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
    apiClient.post<Token>('/auth/register', data),

  /**
   * Refresh access token
   */
  refresh: (refreshToken: string) =>
    apiClient.post<Token>(
      '/auth/refresh',
      toFormUrlEncoded({ refresh_token: refreshToken }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    ),

  /**
   * Logout current user
   */
  logout: () =>
    apiClient.post('/auth/logout'),

  /**
   * Get current user profile
   */
  getProfile: () =>
    apiClient.get<User>('/accounts/me'),
}
