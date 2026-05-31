import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useWorldSessionStore } from './worldSession'

export const useContextSummaryStore = defineStore('contextSummary', () => {
  const worldSession = useWorldSessionStore()
  const expandedSections = ref<string[]>([])
  const summary = computed(() => worldSession.contextSummary)

  function toggleSection(sectionId: string) {
    expandedSections.value = expandedSections.value.includes(sectionId)
      ? expandedSections.value.filter(id => id !== sectionId)
      : [...expandedSections.value, sectionId]
  }

  return {
    summary,
    expandedSections,
    toggleSection,
    runQuickQuery: worldSession.submitQuery,
  }
})
