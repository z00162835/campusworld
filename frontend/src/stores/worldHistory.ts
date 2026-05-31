import { ref } from 'vue'
import { defineStore } from 'pinia'
import { worldHistoryApi, type WorldHistoryGroup } from '@/api/worldHistory'

export const useWorldHistoryStore = defineStore('worldHistory', () => {
  const groups = ref<WorldHistoryGroup[]>([])
  const loading = ref(false)

  async function loadSummary() {
    loading.value = true
    try {
      const { data } = await worldHistoryApi.getSummary()
      groups.value = data.groups
    } finally {
      loading.value = false
    }
  }

  function reset() {
    groups.value = []
    loading.value = false
  }

  return {
    groups,
    loading,
    loadSummary,
    reset,
  }
})
