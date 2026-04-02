/**
 * Loading state composable
 */
import { ref } from 'vue'

export function useLoading(initial = false) {
  const loading = ref(initial)

  const withLoading = async <T>(fn: () => Promise<T>): Promise<T | undefined> => {
    loading.value = true
    try {
      return await fn()
    } finally {
      loading.value = false
    }
  }

  return {
    loading,
    withLoading,
  }
}
