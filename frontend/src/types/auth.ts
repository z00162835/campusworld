/**
 * Authentication types matching backend Pydantic models
 */

export interface Token {
  access_token: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
  email?: string
  username: string
  password: string
}

export interface User {
  id: number
  username: string
  email?: string
  created_at?: string
  updated_at?: string
}

export interface AuthResponse {
  access_token: string
  refresh_token?: string
  token_type?: string
  expires_in?: number
  user?: User
}
