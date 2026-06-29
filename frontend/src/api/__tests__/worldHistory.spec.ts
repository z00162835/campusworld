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
    // Use small message bodies so the count caps are the binding constraint
    // (the byte budget only evicts when the serialized payload is oversized).
    const threads: AicoThread[] = Array.from({ length: MAX_ARCHIVE_THREADS + 5 }, (_, index) => ({
      id: `thread-${index}`,
      title: `Thread ${index}`,
      messages: Array.from({ length: MAX_ARCHIVE_MESSAGES + 5 }, (_, msgIndex) => ({
        id: `m-${index}-${msgIndex}`,
        role: 'user' as const,
        mode: 'aico' as const,
        answer: `msg ${msgIndex}`,
      })),
      updatedAt: new Date(Date.UTC(2026, 5, index + 1)).toISOString(),
    }))

    const payload = buildArchivePayload(threads, [])
    expect(payload.aico_threads).toHaveLength(MAX_ARCHIVE_THREADS)
    expect(payload.aico_threads[0]?.messages).toHaveLength(MAX_ARCHIVE_MESSAGES)
  })

  it('truncates long answer text to MAX_ARCHIVE_TEXT', () => {
    const longText = 'x'.repeat(MAX_ARCHIVE_TEXT + 10)
    const threads: AicoThread[] = [
      {
        id: 'thread-1',
        title: 'Thread 1',
        messages: [
          { id: 'm-1', role: 'user', mode: 'aico', answer: longText },
        ],
        updatedAt: '2026-06-01T00:00:00.000Z',
      },
    ]

    const payload = buildArchivePayload(threads, [])
    expect(payload.aico_threads[0]?.messages[0]?.answer).toHaveLength(MAX_ARCHIVE_TEXT)
  })

  it('evicts oldest threads until the UTF-8 byte budget is satisfied', () => {
    // Each message body is large enough that 20 full threads would blow the
    // 512KB server batch limit. The trimmer must drop the oldest threads
    // (sorted newest-first) until the serialized payload fits the budget.
    const bigAnswer = 'x'.repeat(MAX_ARCHIVE_TEXT) // 8000 chars
    const threads: AicoThread[] = Array.from({ length: MAX_ARCHIVE_THREADS }, (_, index) => ({
      id: `thread-${index}`,
      title: `Thread ${index}`,
      messages: Array.from({ length: MAX_ARCHIVE_MESSAGES }, (_, msgIndex) => ({
        id: `m-${index}-${msgIndex}`,
        role: 'user' as const,
        mode: 'aico' as const,
        answer: bigAnswer,
      })),
      // Newer threads have later updatedAt so they survive eviction.
      updatedAt: new Date(Date.UTC(2026, 5, index + 1)).toISOString(),
    }))

    const payload = buildArchivePayload(threads, [])
    expect(payload.aico_threads.length).toBeLessThan(MAX_ARCHIVE_THREADS)
    // Newest thread (last index) must survive.
    const survivingIds = payload.aico_threads.map(thread => thread.id)
    expect(survivingIds).toContain(`thread-${MAX_ARCHIVE_THREADS - 1}`)
    const serialized = JSON.stringify(payload)
    expect(new TextEncoder().encode(serialized).length).toBeLessThanOrEqual(464_000)
  })

  it('preserves command_conversation when threads are absent and payload fits the budget', () => {
    // Command-only payloads are bounded by MAX_ARCHIVE_MESSAGES * MAX_ARCHIVE_TEXT,
    // which is below the byte budget; no eviction should occur.
    const bigAnswer = 'x'.repeat(MAX_ARCHIVE_TEXT)
    const commandConversation: ConversationMessage[] = Array.from({ length: MAX_ARCHIVE_MESSAGES }, (_, index) => ({
      id: `cmd-${index}`,
      role: 'user' as const,
      mode: 'command' as const,
      answer: bigAnswer,
    }))

    const payload = buildArchivePayload([], commandConversation)
    expect(payload.command_conversation).toHaveLength(MAX_ARCHIVE_MESSAGES)
    const survivingIds = payload.command_conversation.map(msg => msg.id)
    expect(survivingIds).toContain(`cmd-${MAX_ARCHIVE_MESSAGES - 1}`)
  })
})
