import apiClient from './index'
import type { FocusMap, MapPatch, SpaceSummaryData } from '@/types/world'

export const semanticMapApi = {
  getFocus: (params?: {
    view_layer?: string
    anchor_id?: string
    mode?: FocusMap['mode']
    selected_entity_id?: string
  }) =>
    apiClient.get<{ focus_map: FocusMap }>('/semantic-map/focus', { params }),

  getSpaceSummary: (nodeId: string | number) =>
    apiClient.get<{ ok: boolean; summary?: SpaceSummaryData; error?: string }>(
      '/semantic-map/space-summary',
      { params: { node_id: nodeId } },
    ),

  executeAction: (body: {
    action_type: 'drill' | 'select'
    view_layer?: string
    anchor_id?: string
    mode?: FocusMap['mode']
    selected_entity_id?: string
  }) =>
    apiClient.post<{
      focus_map?: FocusMap
      space_summary?: SpaceSummaryData | null
      ok?: boolean
      error?: string
    }>('/semantic-map/actions', body),

  query: (query: string, mode = 'auto') =>
    apiClient.post<{ mode: FocusMap['mode']; answer: string; map_patch: MapPatch }>(
      '/semantic-map/query',
      { query, mode },
    ),
}
