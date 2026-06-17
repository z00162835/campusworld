export interface AuthSessionConfig {
  accessRefreshBufferSeconds: number
  accessRefreshBufferMs: number
  activitySyncIntervalMs: number
  refreshLockTtlMs: number
  refreshWaitTimeoutMs: number
  logoutTimeoutMs: number
  idleFallbackMs: number
}

type AuthSessionEnv = Record<string, unknown>

const DEFAULTS = {
  accessRefreshBufferSeconds: 60,
  activitySyncIntervalMs: 60_000,
  refreshLockTtlMs: 10_000,
  refreshWaitTimeoutMs: 12_000,
  logoutTimeoutMs: 3_000,
  idleFallbackMs: 30 * 60 * 1000,
}

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max)

const readNumber = (
  env: AuthSessionEnv,
  key: string,
  fallback: number,
  min: number,
  max: number,
) => {
  const raw = env[key]
  if (raw === '') return fallback
  const parsed = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(parsed)) return fallback
  return clamp(parsed, min, max)
}

export function buildAuthSessionConfig(env: AuthSessionEnv = import.meta.env): AuthSessionConfig {
  const accessRefreshBufferSeconds = readNumber(
    env,
    'VITE_AUTH_ACCESS_REFRESH_BUFFER_SECONDS',
    DEFAULTS.accessRefreshBufferSeconds,
    5,
    300,
  )
  const activitySyncIntervalMs = readNumber(
    env,
    'VITE_AUTH_ACTIVITY_SYNC_INTERVAL_MS',
    DEFAULTS.activitySyncIntervalMs,
    15_000,
    300_000,
  )
  const refreshLockTtlMs = readNumber(
    env,
    'VITE_AUTH_REFRESH_LOCK_TTL_MS',
    DEFAULTS.refreshLockTtlMs,
    3_000,
    30_000,
  )
  const requestedRefreshWaitTimeoutMs = readNumber(
    env,
    'VITE_AUTH_REFRESH_WAIT_TIMEOUT_MS',
    DEFAULTS.refreshWaitTimeoutMs,
    5_000,
    60_000,
  )
  const refreshWaitTimeoutMs = Math.max(requestedRefreshWaitTimeoutMs, refreshLockTtlMs + 2_000)
  const logoutTimeoutMs = readNumber(
    env,
    'VITE_AUTH_LOGOUT_TIMEOUT_MS',
    DEFAULTS.logoutTimeoutMs,
    1_000,
    10_000,
  )

  return {
    accessRefreshBufferSeconds,
    accessRefreshBufferMs: accessRefreshBufferSeconds * 1000,
    activitySyncIntervalMs,
    refreshLockTtlMs,
    refreshWaitTimeoutMs,
    logoutTimeoutMs,
    idleFallbackMs: DEFAULTS.idleFallbackMs,
  }
}

export const authSessionConfig = buildAuthSessionConfig()
