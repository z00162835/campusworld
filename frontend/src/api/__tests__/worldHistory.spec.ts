import { describe, expect, it } from 'vitest'
import {
  buildArchivePayload,
  MAX_ARCHIVE_MESSAGES,
  MAX_ARCHIVE_TEXT,
  MAX_ARCHIVE_THREADS,
  toArchivedMessage,
} from '../worldHistory'
import type { AicoThread, ConversationMessage } from '@/types/world'

describe('buildArchivePayload', () => {
  it('does not leak frontend title keys into the API payload', () => {
    const threads: AicoThread[] = [
      {
        id: 'thread-1',
        titleKey: 'worldInteraction.decision.newConversation',
        messages: [
          {
            id: 'message-1',
            role: 'assistant',
            mode: 'aico',
            answer: 'Hello',
          },
        ],
        updatedAt: '2026-06-10T00:00:00.000Z',
      },
    ]

    expect(buildArchivePayload(threads, []).aico_threads[0].title).toBe('')
  })

  it('strips unsupported message fields from the archive DTO', () => {
    const message: ConversationMessage = {
      id: 'message-1',
      role: 'assistant',
      mode: 'aico',
      answer: 'Hello',
      streaming: true,
      commandResult: { success: true, message: 'ignored', data: null, error: null },
      expanded: true,
    }

    expect(toArchivedMessage(message)).toEqual({
      id: 'message-1',
      role: 'assistant',
      mode: 'aico',
      answer: 'Hello',
    })
  })

  it('truncates long text and caps thread and message counts', () => {
    const longText = 'x'.repeat(MAX_ARCHIVE_TEXT + 10)
    const threads: AicoThread[] = Array.from({ length: MAX_ARCHIVE_THREADS + 5 }, (_, index) => ({
      id: `thread-${index}`,
      title: `Thread ${index}`,
      messages: Array.from({ length: MAX_ARCHIVE_MESSAGES + 5 }, (_, msgIndex) => ({
        id: `m-${index}-${msgIndex}`,
        role: 'user' as const,
        mode: 'aico' as const,
        answer: longText,
      })),
      updatedAt: new Date(Date.UTC(2026, 5, index + 1)).toISOString(),
    }))

    const payload = buildArchivePayload(threads, [])
    expect(payload.aico_threads).toHaveLength(MAX_ARCHIVE_THREADS)
    expect(payload.aico_threads[0]?.messages).toHaveLength(MAX_ARCHIVE_MESSAGES)
    expect(payload.aico_threads[0]?.messages[0]?.answer).toHaveLength(MAX_ARCHIVE_TEXT)
  })
})
