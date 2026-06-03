import apiClient from './index'
import type { AicoThread, ConversationMessage } from '@/types/world'

export interface WorldHistoryGroup {
  id: string
  title: string
  items: Array<{ id: string; summary: string; createdAt: string }>
}

export interface ConversationArchivePayload {
  aico_threads: Array<{
    id: string
    title: string
    messages: ConversationMessage[]
    updatedAt: string
  }>
  command_conversation: ConversationMessage[]
}

export const worldHistoryApi = {
  getSummary: () => apiClient.get<{ groups: WorldHistoryGroup[]; collapsed: boolean }>('/world-history/summary'),
  archiveConversations: (payload: ConversationArchivePayload) =>
    apiClient.post<{ ok: boolean; archived: boolean; archive_id: string | null }>(
      '/world-history/conversations/archive',
      payload,
    ),
}

export function buildArchivePayload(
  aicoThreads: AicoThread[],
  commandConversation: ConversationMessage[],
): ConversationArchivePayload {
  return {
    aico_threads: aicoThreads
      .filter(thread => thread.messages.length > 0)
      .map(thread => ({
        id: thread.id,
        title: thread.title,
        messages: thread.messages,
        updatedAt: thread.updatedAt,
      })),
    command_conversation: commandConversation.filter(msg => msg.answer || msg.query),
  }
}
