import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useConnectionStore = defineStore('connection', () => {
  const status = ref<'connected' | 'connecting' | 'disconnected' | 'error'>('disconnected')
  const lastError = ref<string | null>(null)

  function setStatus(nextStatus: typeof status.value, error?: string | null) {
    status.value = nextStatus
    lastError.value = error || null
  }

  function reset() {
    status.value = 'disconnected'
    lastError.value = null
  }

  return {
    status,
    lastError,
    setStatus,
    reset,
  }
})
