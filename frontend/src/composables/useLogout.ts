import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTabsStore } from '@/stores/tabs'
import { useSpacesStore } from '@/stores/spaces'
import { useUserStore } from '@/stores/user'

export function useLogout() {
  const router = useRouter()
  const authStore = useAuthStore()
  const tabsStore = useTabsStore()
  const spacesStore = useSpacesStore()
  const userStore = useUserStore()

  const logout = async () => {
    tabsStore.clearTabs()
    spacesStore.reset()
    userStore.reset()
    const logoutPromise = authStore.logout()
    await router.replace('/login')
    return logoutPromise
  }

  return {
    logout,
  }
}
