import { describe, expect, it } from 'vitest'
import {
  aggregateCommandMessages,
  buildCommandEntries,
  buildConversationEntries,
  conversationPreview,
  resolveThreadTitle,
} from '../utilityHistory'
import type { AicoThread, ConversationMessage } from '@/types/world'

describe('utilityHistory', () => {
  it('aggregates command messages into one entry per interaction', () => {
    const messages: ConversationMessage[] = [
      { id: 'u1', role: 'user', mode: 'command', query: 'look', answer: 'look' },
      { id: 'a1', role: 'assistant', mode: 'command', query: 'look', answer: 'You see a room.' },
      { id: 'u2', role: 'user', mode: 'command', query: 'go north', answer: 'go north' },
      { id: 'a2', role: 'assistant', mode: 'command', query: 'go north', answer: 'You go north.' },
    ]

    expect(aggregateCommandMessages(messages)).toEqual([
      { id: 'u2', label: 'go north', detail: 'You go north.' },
      { id: 'u1', label: 'look', detail: 'You see a room.' },
    ])
  })

  it('builds one conversation entry per AICO thread', () => {
    const threads: AicoThread[] = [
      {
        id: 't1',
        title: 'Route to F3',
        messages: [
          { id: 'm1', role: 'user', mode: 'aico', query: 'How do I reach F3?', answer: 'How do I reach F3?' },
          { id: 'm2', role: 'assistant', mode: 'aico', query: 'How do I reach F3?', answer: 'Take the bridge.' },
        ],
        updatedAt: '2026-06-27T10:00:00.000Z',
      },
      {
        id: 't2',
        messages: [
          { id: 'm3', role: 'user', mode: 'aico', query: 'hello', answer: 'hello' },
        ],
        updatedAt: '2026-06-27T09:00:00.000Z',
      },
    ]

    const entries = buildConversationEntries(threads, [], 'New conversation')
    expect(entries).toHaveLength(2)
    expect(entries[0]?.id).toBe('t1')
    expect(entries[0]?.messageCount).toBe(2)
    expect(entries[0]?.preview).toBe('Take the bridge.')
    expect(resolveThreadTitle(threads[1]!, 'New conversation')).toBe('hello')
    expect(conversationPreview(threads[1]!.messages)).toBe('hello')
  })

  it('merges action history and archived command summaries', () => {
    const entries = buildCommandEntries(
      [],
      [{ id: 'cmd_1', summary: 'Moved north.', createdAt: '2026-06-27T08:00:00.000Z' }],
      [
        {
          id: 'command_conversations',
          title: 'Command sessions',
          items: [
            {
              id: 'archive_1',
              title: 'look',
              detail: 'You see a room.',
              messageCount: 1,
              createdAt: '2026-06-27T07:00:00.000Z',
            },
          ],
        },
      ],
    )

    expect(entries.map(entry => entry.id)).toEqual(['cmd_1', 'archive_1'])
    expect(entries[1]?.label).toBe('look')
    expect(entries[1]?.detail).toBe('You see a room.')
  })

  it('sorts archived command entries by sequence when createdAt matches', () => {
    const createdAt = '2026-06-27T07:00:00.000Z'
    const entries = buildCommandEntries(
      [],
      [],
      [
        {
          id: 'command_conversations',
          title: 'Command sessions',
          items: [
            {
              id: 'archive_old',
              title: 'look',
              detail: 'You see a room.',
              sequence: 0,
              createdAt,
            },
            {
              id: 'archive_new',
              title: 'inventory',
              detail: 'You are carrying nothing.',
              sequence: 1,
              createdAt,
            },
          ],
        },
      ],
    )

    expect(entries.map(entry => entry.id)).toEqual(['archive_new', 'archive_old'])
  })

  it('builds archived conversation entries from structured fields', () => {
    const entries = buildConversationEntries(
      [],
      [
        {
          id: 'aico_conversations',
          title: 'AICO conversations',
          items: [
            {
              id: 'archive_t1',
              title: 'Route to F3',
              messageCount: 3,
              preview: 'Take the bridge.',
              createdAt: '2026-06-27T06:00:00.000Z',
            },
          ],
        },
      ],
      'New conversation',
    )

    expect(entries).toEqual([
      {
        id: 'archive_t1',
        title: 'Route to F3',
        messageCount: 3,
        preview: 'Take the bridge.',
        updatedAt: '2026-06-27T06:00:00.000Z',
      },
    ])
  })
})
