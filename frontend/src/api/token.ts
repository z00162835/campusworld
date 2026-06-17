/**
 * Token management API - separate to avoid circular dependencies
 */
import axios from 'axios'
import { csrfHeaders } from './csrf'

const tokenApiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  withCredentials: true, // Required for cookies
})

export interface TokenResponse {
  access_token: string
  token_type?: string
  expires_in?: number
  idle_expires_in?: number
}

export function isRefreshAuthInvalidationError(error: unknown): boolean {
  const status = (error as { response?: { status?: number } })?.response?.status
  return status === 401 || status === 403
}

export const tokenApi = {
  /**
   * Refresh access token using cookie-based authentication
   */
  refreshWithCookie: (): Promise<TokenResponse> =>
    tokenApiClient.post<TokenResponse>(
      '/auth/refresh',
      {},
      {
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...csrfHeaders(),
        },
      }
    ).then(res => res.data),

}
