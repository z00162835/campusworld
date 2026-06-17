import { describe, expect, it } from 'vitest'
import { buildAuthSessionConfig } from './authSession'

describe('auth session config', () => {
  it('uses production-safe defaults when env values are missing or invalid', () => {
    const config = buildAuthSessionConfig({
      VITE_AUTH_ACCESS_REFRESH_BUFFER_SECONDS: 'not-a-number',
      VITE_AUTH_ACTIVITY_SYNC_INTERVAL_MS: '',
    })

    expect(config.accessRefreshBufferSeconds).toBe(60)
    expect(config.accessRefreshBufferMs).toBe(60_000)
    expect(config.activitySyncIntervalMs).toBe(60_000)
    expect(config.refreshLockTtlMs).toBe(10_000)
    expect(config.refreshWaitTimeoutMs).toBe(12_000)
    expect(config.logoutTimeoutMs).toBe(3_000)
    expect(config.idleFallbackMs).toBe(30 * 60 * 1000)
  })

  it('clamps client-side timeout overrides to bounded ranges', () => {
    const config = buildAuthSessionConfig({
      VITE_AUTH_ACCESS_REFRESH_BUFFER_SECONDS: '1',
      VITE_AUTH_ACTIVITY_SYNC_INTERVAL_MS: '1000',
      VITE_AUTH_REFRESH_LOCK_TTL_MS: '60000',
      VITE_AUTH_REFRESH_WAIT_TIMEOUT_MS: '4000',
      VITE_AUTH_LOGOUT_TIMEOUT_MS: '30000',
    })

    expect(config.accessRefreshBufferSeconds).toBe(5)
    expect(config.activitySyncIntervalMs).toBe(15_000)
    expect(config.refreshLockTtlMs).toBe(30_000)
    expect(config.refreshWaitTimeoutMs).toBe(32_000)
    expect(config.logoutTimeoutMs).toBe(10_000)
  })
})
