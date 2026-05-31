import apiClient from './index'
import type { DecisionOption, StatePatch } from '@/types/world'
import type { ActionResponse } from './worldSessions'

export interface DecisionQueryResponse {
  answer: string
  mode: 'command' | 'aico'
  results?: Array<{
    entity_id: string
    entity_type: string
    title: string
    summary: string
    actions: DecisionOption[]
  }>
  suggested_actions: DecisionOption[]
  command_result?: {
    success: boolean
    message: string
    data?: Record<string, unknown> | null
    error?: string | null
  }
  state_patch?: StatePatch
}

export const decisionCenterApi = {
  executeAction: (sessionId: string, decisionEventId: string, optionId: string) =>
    apiClient.post<ActionResponse>('/decision-center/actions', {
      session_id: sessionId,
      decision_event_id: decisionEventId,
      option_id: optionId,
    }),
  query: (sessionId: string, query: string, mode: 'command' | 'aico') =>
    apiClient.post<DecisionQueryResponse>('/decision-center/query', {
      session_id: sessionId,
      query,
      mode,
    }),
}
