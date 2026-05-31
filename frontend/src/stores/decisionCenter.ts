import { computed } from 'vue'
import { defineStore } from 'pinia'
import { useWorldSessionStore } from './worldSession'

export const useDecisionCenterStore = defineStore('decisionCenter', () => {
  const worldSession = useWorldSessionStore()
  const focus = computed(() => worldSession.decisionCenter?.focus || null)
  const decisionEvents = computed(() => worldSession.decisionCenter?.decisionEvents || [])
  const activeTask = computed(() => worldSession.decisionCenter?.activeTask || null)
  const nextBestAction = computed(() => worldSession.decisionCenter?.nextBestAction || null)
  const quickQueries = computed(() => worldSession.decisionCenter?.quickQueries || [])

  return {
    focus,
    decisionEvents,
    activeTask,
    nextBestAction,
    quickQueries,
    executeDecisionOption: worldSession.executeDecisionAction,
    queryDecisionCenter: worldSession.submitQuery,
  }
})
