import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { decisionCenterApi, queryAicoStream } from '@/api/decisionCenter'
import { useWorldSessionStore } from './worldSession'
import { worldSessionsApi } from '@/api/worldSessions'

vi.mock('@/api/worldSessions', () => ({
  worldSessionsApi: {
    getCurrent: vi.fn(),
    getInteractionState: vi.fn(),
    enterWorld: vi.fn(),
    leaveWorld: vi.fn(),
  },
}))

vi.mock('@/api/decisionCenter', () => ({
  decisionCenterApi: {
    query: vi.fn(),
    executeAction: vi.fn(),
    cancelStream: vi.fn(),
  },
  queryAicoStream: vi.fn(),
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
}

describe('worldSession auth failures', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('does not surface 401 as a world-session load error', async () => {
    vi.mocked(worldSessionsApi.getCurrent).mockRejectedValue({
      response: {
        status: 401,
        data: { detail: 'Invalid or expired token' },
      },
    })

    const store = useWorldSessionStore()
    await store.loadCurrent()

    expect(store.error).toBeNull()
    expect(store.errorKey).toBeNull()
    expect(store.loading).toBe(false)
    expect(store.interactionState).toBeNull()
  })
})

describe('executeCommandQuery', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('records command messages without polluting the active AICO thread', async () => {
    const store = useWorldSessionStore()
    seedSession(store)
    store.queryMode = 'aico'
    store.createAicoThread()
    store.aicoThreads[0]!.messages.push({
      id: 'aico-user',
      role: 'user',
      mode: 'aico',
      query: 'hello',
      answer: 'hello',
    })

    vi.mocked(decisionCenterApi.query).mockResolvedValue({
      data: {
        answer: 'You see a room.',
        command_result: { message: 'You see a room.' },
      },
    } as any)

    await store.executeCommandQuery('look')

    expect(store.commandConversation).toHaveLength(2)
    expect(store.aicoThreads[0]!.messages).toHaveLength(1)
    expect(store.aicoThreads[0]!.messages[0]?.mode).toBe('aico')
  })

  it('does not clear an active AICO stream loading state', async () => {
    const store = useWorldSessionStore()
    seedSession(store)
    store.queryMode = 'aico'
    store.createAicoThread()

    let releaseStream: (() => void) | undefined
    vi.mocked(queryAicoStream).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => {
        releaseStream = resolve
      })
    })
    vi.mocked(decisionCenterApi.query).mockResolvedValue({
      data: { answer: 'done', command_result: { message: 'done' } },
    } as any)

    const streamPromise = store.submitQuery('question')
    await vi.waitFor(() => expect(store.streamInFlight).toBe(true))

    await store.executeCommandQuery('look')

    expect(store.streamInFlight).toBe(true)

    releaseStream?.()
    const submission = await streamPromise
    if (submission.accepted) {
      await submission.completion
    }

    expect(store.streamInFlight).toBe(false)
  })

  it('returns accepted before AICO stream completes', async () => {
    const store = useWorldSessionStore()
    seedSession(store)
    store.queryMode = 'aico'
    store.createAicoThread()

    let releaseStream: (() => void) | undefined
    vi.mocked(queryAicoStream).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => {
        releaseStream = resolve
      })
    })

    const pending = store.submitQuery('question')
    const submission = await pending

    expect(submission.accepted).toBe(true)
    expect(store.streamInFlight).toBe(true)

    releaseStream?.()
    if (submission.accepted) {
      await submission.completion
    }

    expect(store.streamInFlight).toBe(false)
  })

  it('returns null on failure without throwing by default', async () => {
    const store = useWorldSessionStore()
    seedSession(store)

    vi.mocked(decisionCenterApi.query).mockRejectedValue(new Error('network'))

    await expect(store.executeCommandQuery('look')).resolves.toBeNull()
  })

  it('rejects concurrent command execution at the store level', async () => {
    const store = useWorldSessionStore()
    seedSession(store)

    let releaseFirst: (() => void) | undefined
    vi.mocked(decisionCenterApi.query).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => {
        releaseFirst = resolve
      })
      return {
        data: { answer: 'First done.', command_result: { message: 'First done.' } },
      } as any
    })

    const first = store.executeCommandQuery('look')
    await vi.waitFor(() => expect(store.commandLoading).toBe(true))

    const second = await store.executeCommandQuery('inventory')

    expect(second).toBeNull()
    expect(store.commandConversation).toHaveLength(1)

    releaseFirst?.()
    await first

    expect(store.commandConversation).toHaveLength(2)
  })

  it('blocks AICO submitQuery while a command is in flight', async () => {
    const store = useWorldSessionStore()
    seedSession(store)
    store.queryMode = 'aico'
    store.createAicoThread()
    store.commandLoading = true

    await store.submitQuery('hello while command busy')

    expect(store.aicoThreads[0]!.messages).toHaveLength(0)
    await expect(store.submitQuery('again')).resolves.toEqual({ accepted: false })
  })
})

describe('session action gate', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('ignores duplicate executeDecisionAction while the first is in flight', async () => {
    const store = useWorldSessionStore()
    seedSession(store)

    let releaseFirst: (() => void) | undefined
    vi.mocked(decisionCenterApi.executeAction).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => {
        releaseFirst = resolve
      })
      return {
        data: { success: true, result: { summary: 'ok' }, state_patch: {} },
      } as any
    })

    const first = store.executeDecisionAction('evt_1', 'opt_1')
    await vi.waitFor(() => expect(store.sessionActionLoading).toBe(true))

    await store.executeDecisionAction('evt_1', 'opt_1')

    expect(decisionCenterApi.executeAction).toHaveBeenCalledTimes(1)

    releaseFirst?.()
    await first
  })

  it('does not enterWorld while a command is in flight', async () => {
    const store = useWorldSessionStore()
    seedSession(store)
    store.commandLoading = true

    await store.enterWorld('hicampus')

    expect(worldSessionsApi.enterWorld).not.toHaveBeenCalled()
  })

  it('stops an in-flight AICO stream before enterWorld', async () => {
    const store = useWorldSessionStore()
    seedSession(store)
    store.queryMode = 'aico'
    store.createAicoThread()

    let releaseStream: (() => void) | undefined
    vi.mocked(queryAicoStream).mockImplementationOnce(async () => {
      await new Promise<void>(resolve => {
        releaseStream = resolve
      })
    })

    const streamPromise = store.submitQuery('question')
    await vi.waitFor(() => expect(store.streamInFlight).toBe(true))

    vi.mocked(worldSessionsApi.enterWorld).mockResolvedValue({
      data: { success: true, result: { summary: 'entered' }, state_patch: {} },
    } as any)
    vi.mocked(worldSessionsApi.getCurrent).mockResolvedValue({
      data: {
        interaction_state: store.interactionState,
        display_policy: null,
        available_worlds: [],
      },
    } as any)

    const enterPromise = store.enterWorld('hicampus')
    await vi.waitFor(() => expect(store.streamInFlight).toBe(false))

    releaseStream?.()
    const finishSubmission = async (submissionPromise: ReturnType<typeof store.submitQuery>) => {
      const submission = await submissionPromise
      if (submission.accepted) {
        await submission.completion
      }
    }
    await Promise.all([finishSubmission(streamPromise), enterPromise])

    expect(worldSessionsApi.enterWorld).toHaveBeenCalledWith('hicampus')
    expect(store.aicoThreads).toHaveLength(0)
  })
})
