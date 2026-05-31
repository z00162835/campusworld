import apiClient from './index'
import type { FocusMap } from '@/types/world'

export const semanticMapApi = {
  query: (sessionId: string, query: string, mode = 'auto') =>
    apiClient.post<{ mode: FocusMap['mode']; answer: string; map_patch: Record<string, unknown> }>('/semantic-map/query', {
      session_id: sessionId,
      query,
      mode,
    }),
}
