/**
 * User accounts API endpoints
 */
import apiClient from './index'
import type { User } from '@/types/auth'

export const accountsApi = {
  /**
   * Get current user profile
   */
  getProfile: () =>
    apiClient.get<User>('/accounts/me'),

  /**
   * Update current user profile
   */
  updateProfile: (data: Partial<User>) =>
    apiClient.put<User>('/accounts/me', data),
}
