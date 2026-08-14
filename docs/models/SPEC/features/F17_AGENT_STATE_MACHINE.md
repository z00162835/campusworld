# F17 — Agent State Machine DSL & Structured Turn

> **Architecture Role：** 将 [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) `LlmPDCAFramework` 的 **硬编码 PDCA 四阶段** 升级为 **可配置状态机 DSL**，并引入 **结构化 turn 输出**（`react_turn_schema`）。默认 workflow = PDCA，保证现有 AICO 行为等价；新 workflow 为 opt-in。属 L3 思考模型层（[F09](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.3）。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（PDCA、`llm_tool_plan`、dual-track、Check `RETRY`）、[**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L3 层）、[**F15**](F15_AGENT_SKILL_REGISTRY.md)（`selected_skill` 字段来源）、[**F16**](F16_AGENT_POLICY_ENGINE.md)（check_point 插入）、[**F18**](F18_AGENT_QUALITY_GATES.md)（`react_turn_success` hard gates）、[**F10**](F10_AICO_PERFORMANCE_AND_LATENCY.md)（轮次/延迟上限）。

---

## 1. Goal

- 把 `_run_inner`（`llm_pdca.py`）的外层 PDCA 转移到 **数据驱动状态机**（states + transitions + condition_evaluators），使 workflow 可经节点 `attributes.workflow` 配置。
- 引入 `react_turn_schema`：强制 LLM 每轮输出结构化 JSON（opt-in via `runtime.require_structured_turn`），含 `selected_skill` / `proposed_action` / `success_criteria`。
- **默认 workflow = PDCA 四阶段**，与今日 AICO 行为 golden-trace 等价；新 workflow 为 opt-in，不破坏现有 tick。

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）外层 tick 状态机；`react_turn_schema` 的 schema + 校验 + repair；`attributes.workflow` 加载；可序列化 FSM 快照。
- **Non-Goals：**
  - **不**重写 `agent_loop/` 内层 ReAct 微循环（`draft_gate` / `should_exit_react_round` / `detect_pending_tool_work` 保持；状态机驱动外层，内层 ReAct 仍为 stage 内子循环，见 §7）。
  - v1 **不**强制所有 provider 走 `response_format: json_schema`；优先 **tool-as-schema**，无 tools 的 provider 走 JSON 解析容错 + repair（见 §5.3）。
  - **不**改变 `ResolvedToolSurface` 冻结面（F08 §5.1）。
  - **不**引入新 replan 机制与既有 Check `RETRY` / `agent_loop` draft retry 冲突（见 §7 边界）。

---

## 3. 状态机模型

### 3.1 StateMachine（`state_machine.py`）

```python
@dataclass(frozen=True)
class StateDef:
    id: str
    skill: Optional[str] = None
    tools: Optional[Tuple[str, ...]] = None
    exit: bool = False                  # True for end / fail
    phase_llm_key: Optional[str] = None

@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    when: Optional[str] = None          # condition_evaluator expression
    on_event: Optional[str] = None      # 'check_retry' | 'mandatory_gap' | 'stagnation'

@dataclass(frozen=True)
class StateMachine:
    states: Tuple[StateDef, ...]
    transitions: Tuple[Transition, ...]
    initial: str
    max_replans: int = 1
    def next(self, current: str, ctx: TransitionContext) -> str: ...

@dataclass(frozen=True)
class TransitionContext:
    snapshot: StateMachineSnapshot
    runtime: Dict[str, Any]  # do_mode, act_mode, budget_remaining, ...
    event: Optional[str] = None

@dataclass(frozen=True)
class StateExecutionResult:
    output_text: str = ""
    event: Optional[str] = None
    draft_text: str = ""
    gather_counters: Optional[Dict[str, Any]] = None
```

### 3.2 workflow schema（节点 `attributes.workflow`）

```yaml
workflow:
  mode: pdcp              # v1 仅 pdcp | pdca（= 今日 PDCA）；react/think reserved
  # stages / interactions / replan.from 为 reserved（D3/D4/D5）：
  #   - 自定义 stages：loader 可解析，v1 不执行（worker 回退 PDCA + warn）
  #   - interactions：语义待 F18 pause/resume，v1 不交付
  #   - replan.from：v1 不约束 replan 目标，仅 replan.max 生效
  #   - stage.skill / stage.tools：v1 仅声明（inert），执行面绑定随「可执行 workflow」里程碑
  replan:
    max: 1
```

### 3.3 默认 workflow = PDCA（等价契约）

`mode: pdcp` / 缺省 workflow 等价今日 `_run_inner`：`plan` → `do`（可 skip）→ `check` → `act`（可 skip）→ `end`，含 **Check `RETRY` 单次 replan**（无二次 Check LLM）。缺失 `attributes.workflow` 时 framework 加载 PDCA 模板。

⚠️ **等价性硬约束：** 默认 PDCA 状态机必须复现今日 **隐式转移**：thin PDCA（plan react + skip do + check fast + skip act）、`RETRY` 单次、mandatory-gap override、skip-do draft 路径（`assemble_plan_skip_do_draft`）。golden 测试锁定这些行为。

**默认 PDCA 转移表：**

| from | to | when | on_event | 说明 |
|------|-----|------|----------|------|
| plan | do | `runtime.do_mode != "skip"` | — | 非 skip-do |
| plan | check | `runtime.do_mode == "skip" and state.replan_count == 0` | — | skip-do 首次 |
| plan | act | `runtime.do_mode == "skip" and state.replan_count > 0` | — | skip-do replan 后 |
| do | check | `state.replan_count == 0` | — | 首次 Check |
| do | act | `state.replan_count > 0` | — | replan 后无二次 Check |
| check | plan | `state.replan_count < sm.max_replans and runtime.budget_remaining` | `check_retry` | RETRY 信号 |
| check | plan | `state.replan_count < sm.max_replans and runtime.budget_remaining and runtime.mandatory_gap_missing` | `mandatory_gap` | mandatory gap |
| any | plan | `state.replan_count < sm.max_replans and runtime.budget_remaining` | `stagnation` | F18 stagnation replan（R2 方案A；driver 映射 `stop_evaluator` stagnation → `event=stagnation`） |
| check | act | — | — | 始终进入 act（skip-act 在态内 `mode=skip` 发迹） |
| act | plan | `state.replan_count < sm.max_replans and runtime.budget_remaining` | `draft_retry` | F18 `final_success_evaluator` retry_loop→replan（D-I-B；enforce 模式驱动，计入 `replan_count`；超限 → `runtime.stop_fail` → `*→fail`） |
| act | end | — | — | 成功终态 |
| any | fail | `runtime.cancelled` | — | 取消：任意态即时终态 |
| any | fail | `runtime.stop_fail` | — | F18 stop_evaluator 不可恢复终止（max_iterations / max_consecutive_tool_failures / stagnation 超限）；driver 映射 `stop_evaluator` fail → `runtime.stop_fail`（D1，`enable_stop_dimensions` 门控，默认 off） |
| act | fail | `runtime.draft_incomplete` | — | 草稿不完整：仅 act（presentation anchor）终态 |

转移求值顺序：`any → fail`（`cancelled` / `stop_fail`，phase 1 优先，忽略 `on_event`）→ `act → fail`（`draft_incomplete`）→ `on_event` 匹配（`check_retry` / `mandatory_gap` / `stagnation` / `draft_retry`）→ `when` 求值 → 首个匹配生效。

Check RETRY → plan replan 路径 **保留** guardrail hint 注入（等价今日 `plan2_user`）。
Draft retry → plan 路径注入上一版被拒草稿、质量判定原因和补全/grounding 指令；相同输入的盲重试不属于支持契约。

**`fail` 终态契约（D1-A）：** abort 必须经状态机进入 `fail`，不得提前 `return` 绕过 `sm.next`。

| 原因 | `runtime` 标志 | `FrameworkRunResult` |
|------|----------------|----------------------|
| 取消 | `cancelled=true` | `ok=false`, `final_phase=fail`, `error_code=cancelled` |
| F18 stop 不可恢复终止 | `stop_fail=true` | `ok=false`, `final_phase=fail`, `error_code=<reason_code>`（如 `max_iterations_exceeded` / `stagnation_replan_exhausted`） |
| Draft retry 不可执行 | `stop_fail=true` | `ok=false`, `final_phase=fail`, `error_code=draft_retry_exhausted` 或 `draft_retry_unsupported` |
| 草稿不完整 | `draft_incomplete=true` | `ok=false`, `final_phase=fail`, `error_code=draft_incomplete` |

- 态前 / 态内取消：置 `cancelled`，本轮不执行（或截断执行）后 `sm.next` → `fail`（任意态）。
- ReAct 内预算耗尽致 `_draft_incomplete`：**不**即时终态；plan/do 置位后继续流转到 act，由 act 锚点重判（见下）。
- Act 后 deferral-only 检测（`_detect_tick_emit_deferral`，act 锚点权威）：据 **最终草稿** 重判 `draft_incomplete`——deferral-only 且无 grounding → 置位 `act→fail`；完整草稿 → 清除 plan/do 残留软标志，使成功路径与 post-loop mandatory-gap 通知可达；空草稿 → 保留 plan/do 残留标志（不静默成功）。
- 成功路径终态仍为 `end`；`finish_run` 相位对 abort 记为 `fail`。
- **adapter 层对齐：** `npc_agent_nlp` 捕获 `LlmRequestCancelled` 时亦回 `final_phase='fail'` + `error_code='cancelled'`（不经状态机，但契约一致）；streaming 层（`aico/profile`）以 `error_code=='cancelled'` 识别 cancel 并发 `kind: cancelled` NDJSON（线缆格式不变）。
- **abort 不发 skip-do draft：** cancel / `draft_incomplete` 经 `fail` 时不补发合成 `do` skipped 项（与重构前 early-return 行为一致；skip-do draft 仅在成功路径跳过 `do` 时发）。

### 3.4 FSM 状态快照（Serializable Snapshot）

```python
@dataclass(frozen=True)
class StateMachineSnapshot:
    schema_version: str = "1"
    current_state: str = ""
    turn_count: int = 0
    replan_count: int = 0
    completed_states: Tuple[str, ...] = ()
    last_event: Optional[str] = None
    # to_dict() / from_dict()
```

- 与 application context（`FrameworkRunContext`、`gather_counters` 等不可序列化对象）**分离**。
- 写入 `command_trace` 的 `step: "state_transition"` 行，字段：`from` / `to` / `when` / `event` / `replan_count`（D8：`replan_count` 为契约字段，便于 replay/debug）。
- v1 仅保证可序列化形状（`to_dict` / `from_dict`）；**持久化与 pause/resume 归 [F18](F18_AGENT_QUALITY_GATES.md)**，本特性为它铺路，不交付恢复语义。

---

## 4. condition_evaluators（`condition_evaluators.py`）

v1 最小语法：

- 原子：`field op literal`，`op ∈ {==, !=, <, >, <=, >=, in}`
- 组合：`and` / `or` / `not`
- 字段路径：`state.field`（如 `state.replan_count < 1`）、`runtime.field`（如 `runtime.do_mode == "skip"`）、`sm.field`（如 `sm.max_replans`，D9：正式纳入 v1 语法，PDCA 模板已用）
- **不**引入 Spring/SPel；纯函数求值
- v1 **不**支持 `${skill.*}`（Skill prompt 模式仅产文本）；结构化 skill 字段启用后另开契约

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
    "tool_args": {"args": ["string", ...]}?,   // tool_call 契约：argv 数组（见下）
    "final_answer_draft": "string?"
  },
  "expected_observation": "string",
  "success_criteria": ["string"]
}
```

**`tool_args` 契约（D2/方案A）：** `action_type == "tool_call"` 时 `tool_args` 必须为 `{"args": [str, ...]}` 形态（campus 命令 argv 契约，如 `{"args": ["-n", "hicampus"]}`）。`ProposedAction.model_validator` 拒绝 flat flag dict（如 `{"-n": "hicampus"}`），使其路由到 **repair retry → degrade 自由文本**，而非静默丢弃 flag 名。`tool_calls_from_react_turn` 仅从 `tool_args["args"]` 取 argv，不再接受任意 dict 分支。`REACT_TURN_JSON_SCHEMA` 对应 `tool_args` 子 schema 收紧为 `properties: {args: array of string}, required: [args]`。

### 5.2 强制与降级

- **opt-in：** `runtime.require_structured_turn: true` 启用。v1 **默认关**（保持 AICO 自由文本）。
- **与既有 tool 协议：** 启用结构化 turn 时 **关闭 native tool_use**，避免双通道意图重复（Q1 决策）。
- **streaming：** `require_structured_turn=true` 时禁 prose 流式（Q5 决策）。

⚠️ **SPEC 张力：** [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §7 默认 `commands` JSON；本 SPEC 将 `react_turn_schema` 定为 **opt-in**，不取代 §7 默认路径。

### 5.3 provider 强制策略（tool-as-schema）

| Provider 能力 | v1 策略 |
|---------------|---------|
| `supports_tools() == True` | **tool-as-schema**：定义 `emit_turn` tool，`input_schema` = turn schema，`tool_choice` 强制该 tool |
| `supports_tools() == False` | JSON-in-system-prompt + parse + **一次** repair retry → 再失败降级自由文本 |

统一 port：`emit_structured_turn(schema, messages, force_tool=True) -> dict`。

---

## 6. 与 `phase_llm` / `mode_models` 集成

- `merge_phase_config(phase, ...)` 接受任意 phase 字符串键。
- 状态机 stage id → `phase_llm` 键；缺省回退 `mode_models`。
- v1 仅执行 PDCA stage（`plan/do/check/act`）；自定义 workflow 的 `phase_llm[stage_id]` seed **不生效**，待「可执行 workflow」里程碑（D3-B）。

---

## 7. 与 `agent_loop/` 内层 ReAct 的边界

- **外层状态机**驱动 stage 间转移。
- **内层 ReAct**（`agent_loop/`）仍是 stage 内子循环；状态机不接管 round 控制。
- v1 状态机 `replan` 映射 Check `RETRY` / mandatory-gap / stagnation / draft_retry（外层）；内层 draft retry 保留 `agent_loop`（`max_rounds` 预算）。**D-I-B 决策：** 外层 replan 共享 `max_replans` 计数器；内层 draft retry（同计划加 hint 重试）保留独立 `max_rounds` 预算——粒度不同不混用（业界实践：LangGraph `recursion_limit` vs per-node retry、AutoGen `max_consecutive_auto_reply` vs 外层轮次均分离）。

### 7.1 Driver 三段边界

1. **Pre-loop setup：** intent 分类、tool router、schema allowlist、skill context、plan user 组装（不进入 `_execute_state`）。
2. **Driver loop（physical order，D11）：** `_execute_state` →（可选）[F16](F16_AGENT_POLICY_ENGINE.md)/[F18](F18_AGENT_QUALITY_GATES.md) `PolicyEngine.evaluate(check_point='after_state_execute')` → 将 `PolicyDecision` 映射为既有 `runtime.*` flag / event（`fail`→`runtime.stop_fail`、`replan`(stagnation)→`event=stagnation`，超限→`stop_fail`）→ `sm.next`（求值 `any→fail`(cancel/stop_fail) / `act→fail`(draft_incomplete) / `on_event`(check_retry/mandatory_gap/stagnation) / `when`）→ `state_transition` trace → `snapshot.advance`。abort 经 `sm.next → fail` 在此返回，不再旁路。
3. **Post-loop gates：** act 锚点 `_detect_tick_emit_deferral` 后可咨询 `PolicyEngine.evaluate(check_point='before_terminal')`（F18 `final_success_evaluator`）；成功路径 mandatory notice 追加；abort 已在 driver 内经 `fail` 终态返回（不再于 post-loop 旁路改写 `final_phase`）。

**控制流权威：** `sm.next` 是 tick 内 **唯一** 控制流权威。F18 质量/停止规则复用 F16 PolicyEngine，仅产出决策信号；driver 映射到既有 `runtime` / event 后由本状态机消费——**不**引入并行 StopPolicy 控制流（见 [F18](F18_AGENT_QUALITY_GATES.md) §4.4）。F18 stagnation 信号经 `event=stagnation` 映射，PDCA 模板新增 `any→plan on_event=stagnation`（受 `replan_count < max_replans` 约束；超限走 `fail`）。

**`draft_incomplete` 路由（D2）：** 检测在 ReAct 环内可置位（预算耗尽），但 **不** 即时终态；plan/do 置位后继续流转到 act，由 act 锚点 `_detect_tick_emit_deferral` 据 **最终草稿** 权威重判，路由经 `runtime.draft_incomplete` + `act→fail`（非 `any→fail`），以保证成功路径 post-loop mandatory-gap 通知可达；成功路径 post-loop 不再二次改写 `final_phase`。F18 `before_terminal` 在该重判 **之后** 求值，以 `_draft_incomplete` 为输入而非竞争裁判。

---

## 8. 节点 `attributes.workflow` 加载

- `workflow_loader.py` 从 `attributes.workflow` 解析；缺失 → PDCA 默认模板。
- **v1 可执行面仅 `mode: pdcp|pdca`（D3-A）：** loader 可解析自定义 stages（forward-compat / 校验），但 worker 发现非 PDCA 可执行 workflow 时 **回退 PDCA 模板 + warn**，避免 tick 触发未实现的 stage handler。可执行自定义 workflow 为 D3-B 里程碑。
- seed：merge-if-missing；**不**强制覆盖既有自定义 `workflow`。
- `cognition_profile_ref` 保留 inert（Q6）；`workflow` 缺失时回退 PDCA。
- 与 task 域 `workflow_ref` **不同域，不复用**。

---

## 9. prompt_fingerprint

- fingerprint 为 **输入侧**；v1 非正确性契约。
- 结构化 turn 改输出形状；schema 提示放 **system 段**。

---

## 10. Acceptance Criteria

**PDCA v1（已交付）：**

- [x] `StateMachine` 数据驱动，默认 PDCA 模板与今日 `_run_inner` golden-trace 等价
- [x] `fail` 终态：cancel / draft_incomplete 经 `sm.next` 进入 `fail`，`final_phase=fail` + `error_code`（D1-A）
- [x] `react_turn_schema`：tool-as-schema 优先；JSON 解析失败触发一次 repair，再失败降级自由文本
- [x] `require_structured_turn` 默认关；启用时关闭 native tool_use 并禁流式
- [x] `condition_evaluators` 支持 `state.*` / `runtime.*` / `sm.*`；`${skill.*}` 延后
- [x] 不破坏 `agent_loop/` 内层 ReAct / Check `RETRY` / mandatory-gap
- [x] 转移图属性（默认 PDCA）：每非终态有出边；每状态可达 `end` 或 `fail`；无死状态
- [x] `StateMachineSnapshot` 可序列化；`state_transition`（含 `replan_count`）写入 `command_trace`
- [x] `workflow_loader` 从 `attributes.workflow` 解析；缺失回退 PDCA
- [x] 单元测试位于 `backend/tests/game_engine/`

**DSL v1（部分 / 铺路，不交付可执行自定义 workflow）：**

- [ ] 自定义 `mode: react` stages 可执行（D3-B，里程碑外）
- [ ] `interactions` 人机中断语义（D4，待 F18 pause/resume）
- [ ] `mode: think` / `replan.from` 契约化（D5，reserved）
- [ ] `StateDef.skill` / `tools` 执行面绑定（D6，随 D3-B）
- [ ] `selected_skill` 消费 → `model_selected` Skill L2 body 注入（随 D3-B / D6；F17 v1 仅暴露 schema 字段，driver loop 不消费 `structured_turn.selected_skill`，`SkillInjection` 仍按 `phase_mapped` 确定性映射激活 body）
- [ ] Snapshot 持久化 + pause/resume replay（D7，归 F18）
- [x] 任意 loaded workflow 的转移图属性测试（默认 PDCA 已覆盖）

---

## 11. SPEC 同步

- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §7：`require_structured_turn=true` 时由本特性 `react_turn_schema` 强制；`commands` JSON 为降级路径。
- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §12.4：状态机 `replan` 映射 Check `RETRY`。
- [F09](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §7 L3 行更新为含 `agent_runtime/state_machine/`。

---

## 12. Open Questions / 决策

- **Q1（结构化 turn 与 native tool_use）：** **已决策 v1 互斥**（启用结构化 turn 关 native tool_use）。
- **Q2（replan 统一）：** **已决策（D-I-B）** — 外层 replan（check_retry / mandatory_gap / stagnation / draft_retry）共享 `max_replans`；内层 draft retry 保留 `agent_loop` `max_rounds`。`act→plan on_event=draft_retry` 已落地（§6）。
- **Q3（`${skill.*}`）：** v1 不支持；待 Skill 结构化输出。
- **Q4（provider json_schema）：** 不阻塞；v1 用 tool-as-schema / JSON repair。
- **Q5（streaming）：** **已决策** `require_structured_turn=true` 时禁流式。
- **Q6（`cognition_profile_ref`）：** **已决策** v1 保留 inert；workflow 缺失回退 PDCA。
- **D1（`fail` 终态）：** **已决策 A** — abort（cancel / draft_incomplete）经 `sm.next` 进入 `fail`；`final_phase=fail` + 对应 `error_code`（见 §3.3）。
- **D2（`draft_incomplete` 路由）：** **已决策** — ReAct 环内可置位但不即时终态；act 锚点据最终草稿权威重判，路由经 `act→fail`（非 `any→fail`）；成功路径 post-loop 不二次改写 `final_phase`（见 §7.1）。
- **D3（自定义 workflow 可执行性）：** **已决策 A（v1）** — 仅执行 `pdcp|pdca`；loader 可解析自定义 stages，worker 回退 PDCA + warn。**B（可执行自定义 workflow）** 为后续里程碑。
- **D4（`interactions` 语义）：** **延后 F18** — v1 不交付人机中断 / pause-resume 生命周期。
- **D5（`mode: think` / `replan.from`）：** **reserved** — v1 不契约化；`replan.max` 生效，`replan.from` 忽略。
- **D6（`StateDef.skill` / `tools`）：** **v1 inert（仅声明）** — 执行面绑定随 D3-B。
- **D7（Snapshot 持久化）：** **归 F18** — v1 仅可序列化形状，不交付 persist/replay。
- **D8（`state_transition.replan_count`）：** **已决策** — 纳入契约字段（见 §3.4）。
- **D9（condition 路径 `sm.*`）：** **已决策** — 正式纳入 v1 语法（见 §4）。
- **D10（Acceptance 校准）：** **已决策** — 拆「PDCA v1 done」vs「DSL v1 铺路」（见 §10）。
- **D11（driver 步骤顺序）：** **已决策** — 以代码 physical order 为准（见 §7.1）。

---

## 13. Implementation Phases

| Phase | Scope |
|-------|-------|
| SPEC | 补全契约（本文件） |
| P0a | `StateMachine` / Snapshot / PDCA template + unit tests |
| P0b | `_run_inner` → driver loop + `_execute_state`；golden 等价 |
| P3 | `condition_evaluators` 替换硬编码条件 |
| P1 | `workflow_loader` + seed merge-if-missing |
| P2 | `react_turn_schema` tool-as-schema + JSON repair |
