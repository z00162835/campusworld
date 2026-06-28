import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useLogout } from './useLogout'

const archiveConversationsMock = vi.hoisted(() => vi.fn())
const logoutMock = vi.hoisted(() => vi.fn())
const replaceMock = vi.hoisted(() => vi.fn())

vi.mock('@/stores/worldSession', () => ({
  useWorldSessionStore: () => ({
    archiveConversations: archiveConversationsMock,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    token: 'snapshot-token',
    logout: logoutMock,
  }),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}))

describe('useLogout', () => {
  beforeEach(() => {
    archiveConversationsMock.mockReset()
    logoutMock.mockReset()
    replaceMock.mockReset()
  })

  it('does not let best-effort archive block local logout and navigation', async () => {
    const calls: string[] = []
    let finishLogout: ((value: { success: true }) => void) | undefined

    archiveConversationsMock.mockImplementation(() => {
      calls.push('archive')
      return new Promise<void>(() => {})
    })
    logoutMock.mockImplementation(() => {
      calls.push('logout')
      return new Promise(resolve => {
        finishLogout = resolve
      })
    })
    replaceMock.mockImplementation(async () => {
      calls.push('replace')
    })

    const { logout } = useLogout()
    const result = logout()
    await Promise.resolve()

    expect(calls).toEqual(['archive', 'logout', 'replace'])
    expect(archiveConversationsMock).toHaveBeenCalledWith('snapshot-token')
    expect(archiveConversationsMock).toHaveBeenCalledTimes(1)
    expect(logoutMock).toHaveBeenCalledTimes(1)
    expect(replaceMock).toHaveBeenCalledWith('/login')

    finishLogout?.({ success: true })
    await expect(result).resolves.toEqual({ success: true })
  })
})
