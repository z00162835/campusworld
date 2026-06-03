import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

export function useLogout() {
  const router = useRouter()
  const authStore = useAuthStore()

  const logout = async () => {
    const { useWorldSessionStore } = await import('@/stores/worldSession')
    await useWorldSessionStore().archiveConversations()
    const logoutPromise = authStore.logout()
    await router.replace('/login')
    return logoutPromise
  }

  return {
    logout,
  }
}
