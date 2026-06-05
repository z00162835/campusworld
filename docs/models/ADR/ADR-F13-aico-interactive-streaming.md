# ADR: F13 AICO 交互式会话与 SSH 流式（首版）

## 状态

Accepted（与 [`docs/models/SPEC/features/F13_AICO_INTERACTIVE_UPGRADE.md`](../SPEC/features/F13_AICO_INTERACTIVE_UPGRADE.md) 及执行计划 P1–P10 对齐）

## 上下文

- 命令经 [`SSHHandler`](../../../backend/app/protocols/ssh_handler.py) 单次返回字符串；助手 NLP 经 [`run_npc_agent_nlp_tick`](../../../backend/app/commands/npc_agent_nlp.py)。
- 首版验收 **仅 SSH**：`-i` REPL、NDJSON **侧写 channel**、`_format_command_result` **简短尾行**；**WebSocket 流式** 延后 backlog。
- **`supports_aico_stream` 默认关闭**；由 [`SSHSession.command_ephemeral`](../../../backend/app/ssh/session.py) 显式置 true（opt-in）。

## 决策

### 产品（P1–P10 摘要）

| 项 | 决议 |
|----|------|
| P1 | `-i` 仅 SSH |
| P2 | 侧写 NDJSON；格式化输出仅用简短尾行 |
| P3 | WS 多帧流式 — backlog |
| P4 | `aico` / `@aico` 共用 argv 解析 |
| P5 | `aico -d <uuid>` → 提示 `aico -d confirm`（ephemeral 绑定 uuid，TTL） |
| P6 | Ctrl+C：停增量 + best-effort 中断 |
| P7 | 能力默认关 |
| P8 | 同 thread 并发 tick → 可读错误（PG advisory lock） |
| P9 | SSH 先交付 |
| P10 | `-his` 按 thread 聚合 STM，M1 MUST |

### NDJSON（最小）

每行一个 JSON 对象：

- `{"kind":"meta","thread_id":"…","correlation_id":"…"}`（可选）
- `{"kind":"delta","text":"…"}`
- `{"kind":"end","full_text":"…"}`
- `{"kind":"error","code":"…","message":"…"}`（可选）

**Superseded (2026-05):** 呈现层与认知层（PDCA）解耦。**Stream anchor**：每 tick 仅允许一个阶段向用户流式输出 prose（Act 未 skip → Act；否则 Do 未 skip → Do；否则 Plan ReAct 末轮），与 `FrameworkRunResult.message` 来源一致；JSON `commands` 计划与 Check 阶段永不进入 `delta`。状态行用 `{"kind":"meta","scope":"activity","activity":"working|tool|writing|rewrite"}`，**不向 UI 暴露** PDCA 阶段名。tick 结束若正文已流式发出则仅 `kind:end` + `scope=tick` `phase=complete`；否则 fallback `emit_assistant_stream_ndjson`。Check 重试发 `activity=rewrite` 并清空当前助手气泡。

**2026-06:** Agent Loop 完整性门禁（`agent_loop/`）在 react loop 与 tick emit 边界拦截 deferral-only 中间态终稿；`error.code=draft_incomplete` 与 cancel/timeout 分轨。

### D4

[`try_restore_conversation_thread_from_transport`](../../../backend/app/game_engine/agent_runtime/conversation_stm_service.py) **不得以 thread.transport_session_id 拒绝** 合法线程；续聊依赖 owner + agent + thread id。

### WS backlog

独立多帧 `type` + payload，末帧 `result` 含全文 `message`；见执行计划 todo `backlog-ws-streaming`。

## 后果

- SSH 客户端需在 opt-in 时解析 NDJSON 行或展示裸流（调试）。
- 并发 tick 依赖 PostgreSQL advisory lock；非 PG 测试环境跳过锁。

## Review / 一致性（执行计划 阶段 C + C2）

- **授权**：`!` 路径与普通命令一致；禁止 `!aico`。
- **兼容**：未开启 `supports_aico_stream` 且未设置 `SSH_AICO_STREAM` 时行为与历史上批量 `message` 一致。
- **文档**：[`F13_AICO_INTERACTIVE_UPGRADE.md`](../SPEC/features/F13_AICO_INTERACTIVE_UPGRADE.md) 命令面与 `get_usage` / help 对齐。
- **WS 延后**：[F13-ws-streaming-backlog.md](F13-ws-streaming-backlog.md)。
