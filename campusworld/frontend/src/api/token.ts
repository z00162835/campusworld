/**
 * Token management API - separate to avoid circular dependencies
 */
import axios from 'axios'

const tokenApiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1',
  timeout: 10000,
  withCredentials: true, // Required for cookies
})

// OAuth2 requires form-urlencoded format
const toFormUrlEncoded = (data: Record<string, string>) => {
  return Object.entries(data)
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
    .join('&')
}

export interface TokenResponse {
  access_token: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
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
        },
      }
    ).then(res => res.data),

  /**
   * Refresh access token with explicit refresh token (for non-cookie clients like CLI)
   */
  refresh: (refreshToken: string): Promise<TokenResponse> =>
    tokenApiClient.post<TokenResponse>(
      '/auth/refresh',
      toFormUrlEncoded({ refresh_token: refreshToken }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    ).then(res => res.data),
}
