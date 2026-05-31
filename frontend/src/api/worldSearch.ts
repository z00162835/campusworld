import apiClient from './index'
import type { DecisionOption } from '@/types/world'

export interface WorldSearchResult {
  entity_id: string
  entity_type: string
  title: string
  summary: string
  actions: DecisionOption[]
}

export const worldSearchApi = {
  search: (query: string, sessionId?: string, worldId?: string) =>
    apiClient.post<{ summary: string; results: WorldSearchResult[]; suggested_actions: DecisionOption[] }>('/world-search', {
      session_id: sessionId,
      world_id: worldId,
      query,
    }),
}
