import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
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
