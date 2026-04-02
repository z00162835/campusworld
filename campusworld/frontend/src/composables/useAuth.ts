/**
 * Authentication composable
 */
import { storeToRefs } from 'pinia'
import { useAuthStore } from '@/stores/auth'

export function useAuth() {
  const authStore = useAuthStore()
  const { isAuthenticated, user, loading, token } = storeToRefs(authStore)

  return {
    isAuthenticated,
    user,
    loading,
    token,
    login: authStore.login,
    logout: authStore.logout,
  }
}
