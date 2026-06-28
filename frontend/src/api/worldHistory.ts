import apiClient from './index'
import type { AicoThread, ConversationMessage, QueryMode } from '@/types/world'

export const MAX_ARCHIVE_THREADS = 20
export const MAX_ARCHIVE_MESSAGES = 50
export const MAX_ARCHIVE_TEXT = 8000

export interface WorldHistoryItem {
  id: string
  title?: string
  createdAt: string
  messageCount?: number
  preview?: string
  detail?: string
  sequence?: number
  /** @deprecated legacy summary string; prefer title/messageCount/preview/detail */
  summary?: string
}

export interface WorldHistoryGroup {
  id: string
  title: string
  items: WorldHistoryItem[]
}

export interface WorldHistorySummaryResponse {
  groups: WorldHistoryGroup[]
  collapsed: boolean
  pagination?: {
    limit: number
    offset: number
    total: number
  }
}

/** Backend archive contract: only fields accepted by ConversationArchiveRequest. */
export interface ArchivedConversationMessageDto {
  id: string
  role: 'user' | 'assistant' | 'system'
  mode: QueryMode
  query?: string
  answer: string
}

export interface ArchivedAicoThreadDto {
  id: string
  title: string
  messages: ArchivedConversationMessageDto[]
  updatedAt: string
}

export interface ConversationArchivePayload {
  aico_threads: ArchivedAicoThreadDto[]
  command_conversation: ArchivedConversationMessageDto[]
}

function truncateText(value: string | undefined, max = MAX_ARCHIVE_TEXT): string {
  const clean = (value ?? '').trim()
  if (clean.length <= max) return clean
  return clean.slice(0, max)
}

export function toArchivedMessage(message: ConversationMessage): ArchivedConversationMessageDto {
  const answer = truncateText(message.answer || message.query || '')
  const query = message.query?.trim() ? truncateText(message.query) : undefined
  return {
    id: message.id,
    role: message.role,
    mode: message.mode,
    ...(query ? { query } : {}),
    answer,
  }
}

export function buildArchivePayload(
  aicoThreads: AicoThread[],
  commandConversation: ConversationMessage[],
): ConversationArchivePayload {
  const threads = aicoThreads
    .filter(thread => thread.messages.length > 0)
    .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt))
    .slice(0, MAX_ARCHIVE_THREADS)
    .map(thread => ({
      id: thread.id,
      title: truncateText(thread.title || '', 256),
      messages: thread.messages
        .slice(-MAX_ARCHIVE_MESSAGES)
        .map(toArchivedMessage),
      updatedAt: thread.updatedAt,
    }))

  const commandMessages = commandConversation
    .filter(msg => msg.answer || msg.query)
    .slice(-MAX_ARCHIVE_MESSAGES)
    .map(toArchivedMessage)

  return {
    aico_threads: threads,
    command_conversation: commandMessages,
  }
}

export const worldHistoryApi = {
  getSummary: (params?: { limit?: number; offset?: number }) =>
    apiClient.get<WorldHistorySummaryResponse>('/world-history/summary', { params }),
  archiveConversations: (payload: ConversationArchivePayload, accessToken?: string | null) =>
    apiClient.post<{ ok: boolean; archived: boolean; archive_id: string | null }>(
      '/world-history/conversations/archive',
      payload,
      accessToken
        ? {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          }
        : undefined,
    ),
}
