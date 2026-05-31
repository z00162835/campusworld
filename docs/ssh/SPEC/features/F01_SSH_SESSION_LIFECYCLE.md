# F01 — SSH Session Lifecycle (Idle Timeout & Teardown)

> **Module scope:** `docs/ssh/SPEC/features/F01_*` — SSH transport session only. Same feature number in other modules (e.g. models) is allowed.

## Goal

After SSH login, one session uses **one idle rule** for the entire connection (main shell and `aico -i` REPL). When there is no user activity for the configured duration, the server sends an English warning (optional) then disconnects the client with full transport teardown.

## Non-Goals

- `command_timeout_seconds` (per-command hard cap) — see `docs/ssh/SPEC/TODO.md`
- Absolute max session duration (e.g. 24h force re-login)
- Reusing `security.session_idle_timeout_minutes` (Web JWT idle)

## Configuration (`ssh.session`)

| Key | Default | Description |
|-----|---------|-------------|
| `auth_timeout_seconds` | 20 | `Transport.accept()` login grace |
| `idle_timeout_minutes` | 5 | App idle disconnect; **0 = disabled** |
| `idle_warning_minutes` | 1 | English warning before disconnect; must be `< idle_timeout` |
| `keepalive_interval_seconds` | 30 | Paramiko transport keepalive; **0 = off** |
| `cleanup_poll_interval_seconds` | 60 | Idle worker poll interval |
| `max_sessions_per_user` | 3 | Max concurrent active SSH sessions per account; **0 = unlimited** |

## Activity Semantics

**Active** (refreshes `last_activity` / idle clock):

- **`console_ready` lifecycle anchor** — channel bound, `spawn_user` complete, console about to start (`user_input=False`)
- User keystrokes and submitted lines (main shell and `aico>`)
- Command execution window (including `!` shell escapes from `aico -i`)
- In-flight AICO/LLM tick and streaming output

**Not active:** password authentication alone (no `login` touch); welcome/prompt rendering.

**Idle:** waiting at any prompt with none of the above.

## Pre-Channel Protection

- App idle enforcement applies only when `channel` is bound (interactive shell).
- Orphan sessions (auth succeeded, no channel) are removed after `auth_timeout_seconds * 2` via cleanup worker (`orphan_pre_channel`).

## Per-User Session Cap

When `max_sessions_per_user > 0`, new auth attempts are rejected (`AUTH_FAILED`) if the account already has that many active sessions. Existing sessions are not kicked.

## Disconnect Flow

1. Worker detects `idle_elapsed >= idle_timeout - idle_warning` → one English warning per session.
2. `idle_elapsed >= idle_timeout` → `request_disconnect(reason='idle_timeout')`.
3. Terminal message → `disconnect_event` → console `running=False` → channel + transport close.

Channel EOF/closed: full session disconnect (not return to main shell).

## Observability

- Logs (English): `ssh_session_idle_warning`, `ssh_session_idle_disconnect`, `ssh_session_orphan_removed`, `ssh_session_limit_exceeded`
- `who` Idle column: seconds since **last activity** (any active signal above)

## Cross-References

- F12 `possession_idle_release_seconds`: agent possession only, independent of SSH idle
- F13 `aico -i`: no idle exemption
