import { computed } from 'vue'
import { defineStore } from 'pinia'
import { useWorldSessionStore } from './worldSession'
import type { FocusMap } from '@/types/world'

export const useWorldMapStore = defineStore('worldMap', () => {
  const worldSession = useWorldSessionStore()
  const map = computed(() => worldSession.focusMap)
  const mode = computed(() => map.value?.mode || 'focus')
  const nodes = computed(() => map.value?.nodes || [])
  const edges = computed(() => map.value?.edges || [])
  const agentPresences = computed(() => map.value?.agentPresences || [])

  function switchMapMode(nextMode: FocusMap['mode']) {
    if (worldSession.interactionState) {
      worldSession.interactionState.focus_map.mode = nextMode
    }
  }

  return {
    map,
    mode,
    nodes,
    edges,
    agentPresences,
    switchMapMode,
  }
})
