# F17 — Agent State Machine DSL & Structured Turn

> **Architecture Role：** 将 [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) `LlmPDCAFramework` 的 **硬编码 PDCA 四阶段** 升级为 **可配置状态机 DSL**，并引入 **结构化 turn 输出**（`react_turn_schema`）。默认 workflow = PDCA，保证现有 AICO 行为等价；新 workflow 为 opt-in。属 L3 思考模型层（[F09](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.3）。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（PDCA、`llm_tool_plan`、dual-track、Check `RETRY`）、[**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L3 层）、[**F15**](F15_AGENT_SKILL_REGISTRY.md)（`selected_skill` 字段来源）、[**F16**](F16_AGENT_POLICY_ENGINE.md)（check_point 插入）、[**F18**](F18_AGENT_QUALITY_GATES.md)（`react_turn_success` hard gates）、[**F10**](F10_AICO_PERFORMANCE_AND_LATENCY.md)（轮次/延迟上限）。

---

## 1. Goal

- 把 `_run_inner`（`llm_pdca.py:699-940`）的外层 PDCA 转移到 **数据驱动状态机**（states + transitions + condition_evaluators），使 workflow 可经节点 `attributes.workflow` 配置。
- 引入 `react_turn_schema`：强制 LLM 每轮输出结构化 JSON（opt-in via `runtime.require_structured_turn`），含 `selected_skill` / `proposed_action` / `success_criteria`。
- **默认 workflow = PDCA 四阶段**，与今日 AICO 行为 golden-trace 等价；新 workflow 为 opt-in，不破坏现有 tick。

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）外层 tick 状态机；`react_turn_schema` 的 schema + 校验 + repair；`attributes.workflow` 加载。
- **Non-Goals：**
  - **不**重写 `agent_loop/` 内层 ReAct 微循环（`draft_gate` / `should_exit_react_round` / `detect_pending_tool_work` 保持；状态机驱动外层，内层 ReAct 仍为 stage 内子循环，见 §7）。
  - v1 **不**强制所有 provider 走结构化输出；`response_format: json_schema` provider 支持参差，v1 走 **JSON 解析容错 + repair** 降级路径（见 §5）。
  - **不**改变 `ResolvedToolSurface` 冻结面（F08 §5.1）。
  - **不**引入新 replan 机制与既有 Check `RETRY` / `agent_loop` draft retry 冲突（见 §7 边界）。

---

## 3. 状态机模型

### 3.1 StateMachine（`state_machine.py`）

```python
@dataclass(frozen=True)
class StateDef:
    id: str
    skill: Optional[str] = None        # 关联 Skill id（[F15]）
    tools: Optional[Tuple[str, ...]] = None  # 该 stage 工具 schema 子集提示
    exit: bool = False                  # 终态

@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    when: Optional[str] = None   # condition_evaluator 表达式
    on_event: Optional[str] = None  # 如 'check_retry'

class StateMachine:
    states: Tuple[StateDef, ...]
    transitions: Tuple[Transition, ...]
    initial: str
    def next(self, current, context) -> str: ...
```

### 3.2 workflow schema（节点 `attributes.workflow`）

```yaml
workflow:
  mode: react              # react | pdcp | think（pdcp = 今日 PDCA 别名）
  stages:
    - id: understand_intent
      skill: problem_framing
    - id: collect_info
      skill: retrieval_reasoning
      tools: [find, describe]
    - id: generate_answer
      skill: final_synthesis
      exit: true
  interactions:
    - id: user_clarification
      when: "${problem_framing.confidence} < 0.8"
      resume_to: understand_intent
  replan:
    from: understand_intent
    max: 2
```

### 3.3 默认 workflow = PDCA（等价契约）

`mode: pdcp` / 缺省 workflow 等价今日 `_run_inner`：`plan` → `do`（可 skip）→ `check` → `act`（可 skip）→ 终态，含 **Check `RETRY` 单次 replan**（`llm_pdca.py:847-877`，无二次 Check LLM）。默认 workflow 不要求节点声明 `attributes.workflow`；缺失时 framework 加载 PDCA 模板。

⚠️ **等价性硬约束：** 默认 PDCA 状态机必须复现今日 **隐式转移**：thin PDCA（plan react + skip do + check fast + skip act）、`RETRY` 单次、mandatory-gap override（`816:839`）、skip-do draft 路径（`assemble_plan_skip_do_draft`）。golden 测试 `test_aico_harness_golden.py` 锁定这些行为。

---

## 4. condition_evaluators（`condition_evaluators.py`）

- 表达式形式：`${skill.field} op value`（如 `${problem_framing.confidence} < 0.8`）。
- v1 评估对象：tick 运行时状态（`intent_hint.confidence`、`tool_router_snapshot.router_confidence`、`gather_counters`、`selected_skill` 输出字段）。
- **今日 agent_runtime 无 `${}` 模板引擎**；v1 实现极简求值器（字段路径 + 比较运算），**不**引入 Spring/SPel 依赖。
- `selected_skill` 字段依赖 [F15](F15_AGENT_SKILL_REGISTRY.md) Skill 运行时；F15 未落地前，`condition_evaluators` 中 `${skill.*}` 无对象可读 —— v1 condition_evaluators **仅支持运行时上下文字段**，`${skill.*}` 为 F15 后启用（Open Question Q3）。

---

## 5. react_turn_schema（`react_turn_schema.py`）

### 5.1 schema

```json
{
  "turn_id": "string",
  "task_state_summary": "string",
  "reason_summary": "string",
  "selected_skill": "string?",
  "proposed_action": {
    "action_type": "tool_call | ask_user | final_answer | replan | no_op",
    "tool_name": "string?",
    "tool_args": "object?",
    "final_answer_draft": "string?"
  },
  "expected_observation": "string",
  "success_criteria": ["string"]
}
```

### 5.2 强制与降级

- **opt-in：** `runtime.require_structured_turn: true` 启用（[F06 runtime 参数] / 节点 `attributes.runtime`，见 [F02] runtime）。v1 **默认关**（保持 AICO 自由文本），逐步灰度。
- **provider 能力：** 今日仅 `minimax_anthropic` 支持 native `tool_use`（`minimax_anthropic.py:131`）；OpenAI/MiniMax native `supports_tools() -> False`（`openai_compatible.py:60`）；**无** provider 实现 `response_format: json_schema`。v1 走 **JSON 解析容错**：复用 `parse_tool_invocation_plan_from_text` / `_try_parse_json_object` 容错模式（`tool_gather.py:64-99`），解析失败触发 **repair retry**（一次重发 + schema 提示），再失败降级为自由文本。
- **与既有 tool 协议关系：** 今日两条通道（native `tool_use` / `commands` JSON）。`react_turn_schema` 是 **第三条正交通道**（turn envelope）；`proposed_action` 映射为 `ToolCall` 或 `final_answer_draft` → 用户消息。v1 `react_turn_schema` **与 native `tool_use` 不并存**（避免工具意图重复：schema 字段 + 并行 tool_use）；启用结构化 turn 时关闭 native tool_use，走纯 JSON envelope（Open Question Q1）。

⚠️ **SPEC 张力：** [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §7 / §12.4 今日规定 `llm_tool_plan` 为可选 + 自由文本 Check + `RETRY:` 行解析。Phase 3「强制 schema」与 §7/§12.4 冲突；本 SPEC 将 `react_turn_schema` 定为 **opt-in**，**不**取代 §7 默认 `commands` JSON，仅作为 `require_structured_turn=true` 时的强契约。F08 §7 需补注「`require_structured_turn` 时由 [F17] react_turn_schema 强制」（见 §11）。

---

## 6. 与 `phase_llm` / `mode_models` 集成

- 今日 `merge_phase_config(phase, ...)` 接受任意 phase 字符串键（`phase_llm_resolve.py:13`），但 `_run_inner` 仅传 `plan|do|check|act`。
- 状态机 stage id → `phase_llm` 键映射：自定义 workflow stage 用其 `id` 作为 `phase_llm` 键；缺省键回退到 `mode_models` 默认模型。
- ⚠️ resolver 默认（unknown phase → `plan` mode）≠ AICO seed（`fast`/`skip`）；等价性依赖 **seeded** `phase_llm`，非 resolver 单独。自定义 workflow 需显式 seed `phase_llm[stage_id]`。

---

## 7. 与 `agent_loop/` 内层 ReAct 的边界

- **外层状态机**驱动 stage 间转移（`understand_intent → collect_info → ...`）。
- **内层 ReAct**（`agent_loop/`）仍是 stage 内子循环（LLM → tool gather → draft gate）；状态机不接管内层 round 控制。
- **三个 replan 触发器**今日并存：`agent_loop` draft retry（`llm_pdca.py:583-608`）、Check `RETRY`（`847-877`）、mandatory tool gap（`mandatory_gap.py`）。状态机 `replan` 必须与三者 **对齐**，不引入第四套。v1 状态机 `replan` 仅映射 Check `RETRY`（外层 replan），内层 draft retry 保留 `agent_loop`（Open Question Q2）。

---

## 8. 节点 `attributes.workflow` 加载

- 今日 `npc_agent` **无** `workflow` attribute（seed `cognition_profile_ref: pdca_v1`，`seed_data.py:304`）。
- ⚠️ 命名张力：`task` 节点有 `workflow_ref`（任务域状态机，`task_state_machine.py`），与 agent workflow DSL **不同域，不复用**。
- 加载：`workflow_loader.py` 从 `attributes.workflow` 解析；缺失 → PDCA 默认模板。
- seed 升级：参照 `phase_llm` merge-if-missing 模式（`seed_data.py:249-264`）；**不**强制覆盖既有自定义 `workflow`。
- `cognition_profile_ref: pdca_v1` 与 `workflow.mode: pdcp` 语义重叠 —— v1 `workflow` 缺失时回退 PDCA，`cognition_profile_ref` 保留 inert（与 [F15] §4.1 一致）。

---

## 9. prompt_fingerprint

- fingerprint 为 **输入侧**（`world_snapshot`/`tool_manifest_text`/`user_message`，`prompt_fingerprint.py:5-7`），HTTP 前剥离，**v1 非正确性契约**（当前不驱动返回答案的缓存；与 [F15](F15_AGENT_SKILL_REGISTRY.md) §5.3 一致——F15 skill 文本纳入 fingerprint 同此定位）。
- 结构化 turn 改 **输出形状**，不改 fingerprint 输入。
- ⚠️ 若 `react_turn_schema` 提示注入 system/manifest 文本，则 fingerprint 输入变 —— v1 将 F17 **schema 提示** 放 **system 段**（**不同于 [F15](F15_AGENT_SKILL_REGISTRY.md) Skill 注入的 user/input context 通道 `skill-context`**）；fingerprint desync **非 v1 正确性 bug**（输入侧、HTTP 前剥离），仅为 trace/dedup 完整性 + 前向兼容。**未来接入 provider prompt-cache / 内部响应缓存时**升级为正确性契约，届时须 **per-loop-phase** 计算 + 含 `skill_context_text`（[F15](F15_AGENT_SKILL_REGISTRY.md) §5.3 已规定该结构），精确缓存失效随之落地。

---

## 10. Acceptance Criteria

- [ ] `StateMachine` 数据驱动，默认 PDCA 模板与今日 `_run_inner` golden-trace 等价
- [ ] `workflow_loader` 从 `attributes.workflow` 解析；缺失回退 PDCA
- [ ] `react_turn_schema` 校验拒绝畸形输出，触发一次 repair retry，再失败降级自由文本
- [ ] `require_structured_turn` 默认关；启用时关闭 native tool_use，走 JSON envelope
- [ ] `condition_evaluators` 支持运行时上下文字段求值；`${skill.*}` 待 [F15] 启用
- [ ] `phase_llm` 接受 stage id 键；自定义 workflow 需显式 seed
- [ ] 不破坏 `agent_loop/` 内层 ReAct / Check `RETRY` / mandatory-gap
- [ ] 单元测试位于 `backend/tests/game_engine/`

---

## 11. SPEC 同步

- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §7 `llm_tool_plan` 补注：「`require_structured_turn=true` 时由 [F17] `react_turn_schema` 强制，`commands` JSON 为降级路径」。
- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §12.4 Check `RETRY` 保持；补注「状态机 `replan` 映射此信号」。
- [F09](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §7 L3 行更新为 `agent_runtime/state_machine/`。

---

## 12. Open Questions

- **Q1（结构化 turn 与 native tool_use 并存）：** v1 互斥（启用结构化 turn 关 native tool_use）；是否可并存（schema envelope + native tool_use 并行）？需避免工具意图重复。
- **Q2（replan 统一）：** 状态机 `replan` 与 `agent_loop` draft retry / Check `RETRY` 如何统一为单一 replan 计数器（`max_replans`）？延后到 [F18](F18_AGENT_QUALITY_GATES.md) `StopPolicy`。
- **Q3（`${skill.*}` 求值）：** 依赖 [F15](F15_AGENT_SKILL_REGISTRY.md) Skill 运行时产出结构化字段；F15 prompt 模式仅产文本，`skill.confidence` 等字段何时可用？
- **Q4（provider json_schema）：** 何时实现 `response_format: json_schema` 原生支持（minimax_anthropic / openai_compatible）？
- **Q5（streaming 冲突）：** `require_structured_turn` 与 `_should_stream_user_prose`（自由 prose 流式）冲突；结构化 turn 阶段是否禁流式？
- **Q6（`cognition_profile_ref` 处置）：** 与 `workflow.mode` 重叠；是否在 workflow 落地后移除 `cognition_profile_ref`？与 [F15] Q3 联动。
