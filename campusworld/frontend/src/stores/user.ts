/**
 * User profile store
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { accountsApi } from '@/api/accounts'
import type { User } from '@/types/auth'

export const useUserStore = defineStore('user', () => {
  const profile = ref<User | null>(null)
  const loading = ref(false)

  const fetchProfile = async () => {
    loading.value = true
    try {
      const { data } = await accountsApi.getProfile()
      profile.value = data
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  const updateProfile = async (updates: Partial<User>) => {
    loading.value = true
    try {
      const { data } = await accountsApi.updateProfile(updates)
      profile.value = data
      return true
    } catch {
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    profile,
    loading,
    fetchProfile,
    updateProfile,
  }
})
