import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useWorldSessionStore } from './worldSession'
import { decisionCenterApi, queryAicoStream } from '@/api/decisionCenter'

vi.mock('@/api/decisionCenter', () => ({
  decisionCenterApi: {
    query: vi.fn(),
    executeAction: vi.fn(),
    cancelStream: vi.fn().mockResolvedValue({ data: { ok: true, stream_id: 'old' } }),
  },
  queryAicoStream: vi.fn(),
}))

vi.mock('@/api/worldSessions', () => ({
  worldSessionsApi: {
    getCurrent: vi.fn(),
    enterWorld: vi.fn(),
    leaveWorld: vi.fn(),
  },
}))

vi.mock('@/api/worldHistory', () => ({
  worldHistoryApi: {
    archiveConversations: vi.fn(),
  },
  buildArchivePayload: vi.fn(() => ({ aico_threads: [], command_conversation: [] })),
}))

function seedSession(store: ReturnType<typeof useWorldSessionStore>) {
  store.interactionState = {
    session: { id: 'sess1', currentSpaceId: 'space1' },
    decision_center: { events: [] },
    focus_map: null,
    context_summary: null,
  } as any
  store.queryMode = 'aico'
  store.createAicoThread()
}

describe('worldSession stream handoff', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not let a superseded stream finally clear the replacement stream', async () => {
    const store = useWorldSessionStore()
    seedSession(store)

    let releaseFirst: (() => void) | undefined
    let releaseSecond: (() => void) | undefined
    const firstHold = new Promise<void>(resolve => {
      releaseFirst = resolve
    })
    const secondHold = new Promise<void>(resolve => {
      releaseSecond = resolve
    })

    vi.mocked(queryAicoStream).mockImplementationOnce(async (_sessionId, _query, options) => {
      options.onEvent({ kind: 'meta', stream_id: 'stream-old' })
      await firstHold
    })

    vi.mocked(queryAicoStream).mockImplementationOnce(async (_sessionId, _query, options) => {
      options.onEvent({ kind: 'meta', stream_id: 'stream-new' })
      await secondHold
      options.onEvent({ kind: 'end', full_text: 'done' })
    })

    const first = store.submitQuery('first question')
    await vi.waitFor(() => expect(store.streamInFlight).toBe(true))

    const second = store.submitQuery('second question')
    await vi.waitFor(() => expect(store.streamInFlight).toBe(true))

    releaseFirst?.()
    await vi.waitFor(() => expect(store.streamInFlight).toBe(true))

    releaseSecond?.()
    await Promise.all([first, second])

    expect(store.streamInFlight).toBe(false)
    const assistants = store.conversationMessages.filter(msg => msg.role === 'assistant')
    expect(assistants.some(msg => msg.answer === 'done')).toBe(true)
  })

  it('aborts and cancels an active stream during reset', async () => {
    const store = useWorldSessionStore()
    seedSession(store)

    let capturedSignal: AbortSignal | undefined
    vi.mocked(queryAicoStream).mockImplementationOnce(async (_sessionId, _query, options) => {
      capturedSignal = options.signal
      options.onEvent({ kind: 'meta', stream_id: 'stream-active' })
      await new Promise<void>((_resolve, reject) => {
        options.signal?.addEventListener('abort', () => {
          reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))
        }, { once: true })
      })
    })

    const request = store.submitQuery('question')
    await vi.waitFor(() => expect(store.streamInFlight).toBe(true))

    store.reset()
    await request

    expect(capturedSignal?.aborted).toBe(true)
    expect(decisionCenterApi.cancelStream).toHaveBeenCalledWith('stream-active')
    expect(store.streamInFlight).toBe(false)
  })
})
