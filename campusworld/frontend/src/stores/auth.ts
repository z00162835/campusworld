/**
 * Authentication store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User, LoginRequest } from '@/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const loading = ref(false)

  const isAuthenticated = computed(() => !!token.value)

  const login = async (credentials: LoginRequest) => {
    loading.value = true
    try {
      const { data } = await authApi.login(credentials)
      token.value = data.access_token
      localStorage.setItem('access_token', data.access_token)
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = () => {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
  }

  return {
    user,
    token,
    loading,
    isAuthenticated,
    login,
    logout,
  }
})
