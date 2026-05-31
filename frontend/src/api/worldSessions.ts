import apiClient from './index'
import type { StatePatch, WorldInteractionState, WorldSummary, DisplayPolicy } from '@/types/world'

export interface WorldSessionCurrentResponse {
  session: WorldInteractionState['session']
  interaction_state: WorldInteractionState
  display_policy: DisplayPolicy
  available_worlds: WorldSummary[]
}

export interface ActionResponse {
  success: boolean
  result: {
    summary: string
    status: 'completed' | 'failed'
    error?: string | null
  }
  state_patch: StatePatch
  command_result?: {
    success: boolean
    message: string
    data?: Record<string, unknown> | null
    error?: string | null
    should_exit?: boolean
  }
}

export const worldSessionsApi = {
  getCurrent: () => apiClient.get<WorldSessionCurrentResponse>('/world-sessions/current'),
  getInteractionState: (sessionId: string) => apiClient.get<WorldInteractionState>(`/world-sessions/${sessionId}/interaction-state`),
  enterWorld: (worldId: string) => apiClient.post<ActionResponse>('/world-sessions/enter-world', { world_id: worldId }),
  leaveWorld: () => apiClient.post<ActionResponse>('/world-sessions/leave-world'),
}
