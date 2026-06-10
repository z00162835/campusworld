import { describe, expect, it } from 'vitest'
import { buildArchivePayload } from '../worldHistory'
import type { AicoThread } from '@/types/world'

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
})
