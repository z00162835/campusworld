/**
 * Authentication API endpoints
 */
import apiClient from './index'
import type { Token, LoginRequest, RegisterRequest } from '@/types/auth'

export const authApi = {
  /**
   * Login with username and password
   */
  login: (data: LoginRequest) =>
    apiClient.post<Token>('/auth/login', data),

  /**
   * Register a new account
   */
  register: (data: RegisterRequest) =>
    apiClient.post<Token>('/auth/register', data),

  /**
   * Logout current user
   */
  logout: () =>
    apiClient.post('/auth/logout'),
}
