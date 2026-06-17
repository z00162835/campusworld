import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorldInteractionView from './WorldInteractionView.vue'
import { tokenApi } from '@/api/token'
import { worldSessionsApi } from '@/api/worldSessions'

vi.mock('@/api/auth', () => ({
  authApi: {
    getProfile: vi.fn(),
    logout: vi.fn(),
    recordActivity: vi.fn(),
  },
}))

vi.mock('@/api/token', () => ({
  tokenApi: {
    refreshWithCookie: vi.fn(),
  },
}))

vi.mock('@/api/worldSessions', () => ({
  worldSessionsApi: {
    getCurrent: vi.fn(),
    getInteractionState: vi.fn(),
    enterWorld: vi.fn(),
    leaveWorld: vi.fn(),
  },
}))

describe('WorldInteractionView session boot', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    document.cookie = 'csrf_token=; Max-Age=0; path=/'
  })

  it('does not load the current world session when cookie restore fails', async () => {
    document.cookie = 'csrf_token=csrf-value; path=/'
    vi.mocked(tokenApi.refreshWithCookie).mockRejectedValue(new Error('expired'))

    mount(WorldInteractionView, {
      global: {
        stubs: {
          EntrySequence: true,
          WorldShell: true,
        },
      },
    })
    await flushPromises()

    expect(tokenApi.refreshWithCookie).toHaveBeenCalledTimes(1)
    expect(worldSessionsApi.getCurrent).not.toHaveBeenCalled()
  })
})
