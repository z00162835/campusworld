import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useWorldSessionStore } from '@/stores/worldSession'

export function useLogout() {
  const router = useRouter()
  const authStore = useAuthStore()

  const logout = async () => {
    void useWorldSessionStore().archiveConversations()
    const logoutPromise = authStore.logout()
    await router.replace('/login')
    return logoutPromise
  }

  return {
    logout,
  }
}
