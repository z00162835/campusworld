import apiClient, { authorizedFetch, getAccessTokenForRequest } from './index'
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

export interface StreamEvent {
  kind: string
  text?: string
  full_text?: string
  stream_id?: string
  scope?: string
  phase?: string
  activity?: string
  detail?: string
  client_hint?: string
  code?: string
  message?: string
  state_patch?: StatePatch
  command_result?: DecisionQueryResponse['command_result']
}

/** Parse one SSE ``data:`` JSON payload (for tests and stream readers). */
export function parseStreamEventPayload(payload: string): StreamEvent | null {
  const clean = payload.trim()
  if (!clean) return null
  try {
    return JSON.parse(clean) as StreamEvent
  } catch {
    return null
  }
}

export function parseStreamEventChunks(buffer: string): { events: StreamEvent[]; remainder: string } {
  const events: StreamEvent[] = []
  const parts = buffer.split('\n\n')
  const remainder = parts.pop() || ''
  for (const part of parts) {
    const line = part.trim()
    if (!line.startsWith('data:')) continue
    const event = parseStreamEventPayload(line.slice(5))
    if (event) events.push(event)
  }
  return { events, remainder }
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
  cancelStream: (streamId: string) =>
    apiClient.post<{ ok: boolean; stream_id: string }>('/decision-center/query/stream/cancel', {
      stream_id: streamId,
    }),
}

export async function queryAicoStream(
  sessionId: string,
  query: string,
  options: { signal?: AbortSignal; onEvent: (event: StreamEvent) => void },
): Promise<void> {
  const baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  await getAccessTokenForRequest()

  const response = await authorizedFetch(`${baseURL}/decision-center/query/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: options.signal,
    body: JSON.stringify({ session_id: sessionId, query, mode: 'aico' }),
  })

  if (!response.ok) {
    const detail = await response.text()
    throw new Error(detail || `Stream request failed (${response.status})`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('Streaming body unavailable')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const parsed = parseStreamEventChunks(buffer)
    buffer = parsed.remainder
    for (const event of parsed.events) {
      options.onEvent(event)
    }
  }
}
