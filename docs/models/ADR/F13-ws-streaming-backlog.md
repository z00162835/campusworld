# F13 backlog: WebSocket streaming

Execution plan todo **backlog-ws-streaming** (deferred from SSH-first M3).

- **Frames**: independent JSON messages with incremental assistant chunks + final `result` carrying full `message` (product decision P3).
- **Capability**: `supports_aico_stream` (or equivalent) on WS `execute` payload or connection handshake.
- **Frontend**: consume stream frames; do not use only terminal `message` for negotiated clients (F13 D8).

See [`ADR-F13-aico-interactive-streaming.md`](ADR-F13-aico-interactive-streaming.md).

## H10 — client_hint 枚举真源（后端已落地）

- **Python**：[`backend/app/commands/aico_stream.py`](../../../backend/app/commands/aico_stream.py) 中 `AICO_CLIENT_HINTS`；前端 / codegen / CI 镜像（T10.1）应与此集合对齐。
- **Fixture 归属 / E2E**（T10.2、T10.3）：仍待工程勾选 SPEC §17.12.4 Todo list。
