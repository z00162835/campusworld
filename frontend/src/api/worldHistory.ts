import apiClient from './index'
import type { AicoThread, ConversationMessage, QueryMode } from '@/types/world'

export const MAX_ARCHIVE_THREADS = 20
export const MAX_ARCHIVE_MESSAGES = 50
export const MAX_ARCHIVE_TEXT = 8000
// Backend rejects payloads whose serialized batch exceeds MAX_ARCHIVE_BATCH_BYTES
// (512_000). The server also stores a derived history_summary, so the client must
// reserve headroom for that overhead before serializing the request body.
export const ARCHIVE_PAYLOAD_BYTE_BUDGET = 464_000

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

function utf8ByteLength(text: string): number {
  // TextEncoder is available in all supported browsers (and vitest jsdom).
  if (typeof TextEncoder !== 'undefined') {
    return new TextEncoder().encode(text).length
  }
  return Buffer.byteLength(text, 'utf-8')
}

function payloadByteSize(payload: ConversationArchivePayload): number {
  return utf8ByteLength(JSON.stringify(payload))
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

function buildThreadDto(thread: AicoThread): ArchivedAicoThreadDto {
  return {
    id: thread.id,
    title: truncateText(thread.title || '', 256),
    messages: thread.messages.slice(-MAX_ARCHIVE_MESSAGES).map(toArchivedMessage),
    updatedAt: thread.updatedAt,
  }
}

function buildCommandDtos(messages: ConversationMessage[]): ArchivedConversationMessageDto[] {
  return messages
    .filter(msg => msg.answer || msg.query)
    .slice(-MAX_ARCHIVE_MESSAGES)
    .map(toArchivedMessage)
}

/**
 * Trim a payload until its UTF-8 serialized size fits the byte budget.
 *
 * Eviction order (oldest first):
 *   1. drop aico threads (sorted oldest updatedAt first)
 *   2. drop oldest messages from each remaining aico thread
 *   3. drop oldest command_conversation entries
 *
 * Threads are pre-sorted newest-first to match the existing contract; we evict
 * from the tail (oldest) so the most recent conversations survive.
 */
function trimPayloadToByteBudget(payload: ConversationArchivePayload): ConversationArchivePayload {
  let threads = payload.aico_threads.slice()
  let commandMessages = payload.command_conversation.slice()
  let current: ConversationArchivePayload = { aico_threads: threads, command_conversation: commandMessages }

  if (payloadByteSize(current) <= ARCHIVE_PAYLOAD_BYTE_BUDGET) {
    return current
  }

  // 1. Drop oldest aico threads one at a time.
  while (threads.length > 0 && payloadByteSize({ aico_threads: threads, command_conversation: commandMessages }) > ARCHIVE_PAYLOAD_BYTE_BUDGET) {
    threads = threads.slice(0, -1)
  }
  current = { aico_threads: threads, command_conversation: commandMessages }
  if (payloadByteSize(current) <= ARCHIVE_PAYLOAD_BYTE_BUDGET) return current

  // 2. Trim oldest messages from each remaining thread (front of the message list).
  while (threads.some(thread => thread.messages.length > 1)) {
    threads = threads.map(thread => {
      if (thread.messages.length <= 1) return thread
      // Drop the oldest message (front), keep the most recent.
      return { ...thread, messages: thread.messages.slice(1) }
    })
    current = { aico_threads: threads, command_conversation: commandMessages }
    if (payloadByteSize(current) <= ARCHIVE_PAYLOAD_BYTE_BUDGET) return current
  }

  // 3. Drop oldest command_conversation entries from the front.
  while (commandMessages.length > 0 && payloadByteSize({ aico_threads: threads, command_conversation: commandMessages }) > ARCHIVE_PAYLOAD_BYTE_BUDGET) {
    commandMessages = commandMessages.slice(1)
  }
  return { aico_threads: threads, command_conversation: commandMessages }
}

export function buildArchivePayload(
  aicoThreads: AicoThread[],
  commandConversation: ConversationMessage[],
): ConversationArchivePayload {
  const threads = aicoThreads
    .filter(thread => thread.messages.length > 0)
    .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt))
    .slice(0, MAX_ARCHIVE_THREADS)
    .map(buildThreadDto)

  const commandMessages = buildCommandDtos(commandConversation)

  return trimPayloadToByteBudget({ aico_threads: threads, command_conversation: commandMessages })
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
