import { describe, expect, it } from 'vitest'
import { canAttemptRefreshAfter401 } from './index'

describe('API auth refresh policy', () => {
  it('does not retry refresh after the app has already confirmed there is no session', () => {
    expect(canAttemptRefreshAfter401({ token: null, sessionRestoreChecked: true })).toBe(false)
  })

  it('still allows refresh when a token exists or restore has not been checked yet', () => {
    expect(canAttemptRefreshAfter401({ token: 'access-token', sessionRestoreChecked: true })).toBe(true)
    expect(canAttemptRefreshAfter401({ token: null, sessionRestoreChecked: false })).toBe(true)
  })
})
