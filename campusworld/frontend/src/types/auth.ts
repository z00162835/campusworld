/**
 * Authentication types matching backend Pydantic models
 */

export interface Token {
  access_token: string
  token_type?: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface RegisterRequest {
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
  token_type?: string
  user?: User
}
