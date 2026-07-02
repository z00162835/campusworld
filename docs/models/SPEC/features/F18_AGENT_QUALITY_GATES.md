# F18 — Agent Quality Gates & Stop Policy

> **Architecture Role：** 将 Agent 运行时的 **质量判定 / 成功检查 / 停止策略** 从代码启发式升级为 **结构化 DSL**。收敛既有 `agent_loop/draft_gate.py`（final_success 实现）与 `tool_gather.py` `ToolGatherBudgets`（fail 条件之一）为统一 `SuccessChecker` / `StopPolicy`。属 L3 思考模型层横切（[F09](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.3）。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（`draft_gate`、Check gate、`RETRY`）、[**F10**](F10_AICO_PERFORMANCE_AND_LATENCY.md)（SLO / 轮次上限 / `ToolGatherBudgets`）、[**F16**](F16_AGENT_POLICY_ENGINE.md)（`require_approval` → `pause`）、[**F17**](F17_AGENT_STATE_MACHINE.md)（`react_turn_success` hard gates、replan 计数）、[**F15**](F15_AGENT_SKILL_REGISTRY.md)（`selected_skill_allowed` gate）。

---

## 1. Goal

- 定义 `SuccessChecker`（hard_gates + semantic_score + pass_condition）与 `StopPolicy`（precedence: fail > pause > final_success > replan > continue）。
- 收敛 `assess_draft_completeness_with_budget` → `SuccessChecker.final_success` 的 hard_gates；收敛 `ToolGatherBudgets` 耗尽 → `StopPolicy.fail` 条件。
- v1 `semantic_scorer` 为 **规则评分**（不引入 LLM-as-judge，避免 tick 内额外 LLM 调用）。

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）tick 内的质量判定与停止决策；`success_checks` / `stop_policy` 节点 attributes DSL。
- **Non-Goals：**
  - v1 **不**实现跨 tick 异步 `pause`/`resume`（tick 同步不变量；`pause` v1 同步降级为 notice/fail，见 §6 / [F16] §8）。
  - v1 **不**引入 LLM-as-judge 语义评分（v2 可选）；`semantic_scorer` 为规则评分。
  - **不**改变 `ResolvedToolSurface` 冻结面（F08 §5.1）。
  - **不**重写 `agent_loop/` 内层 ReAct；`StopPolicy` 驱动外层 tick 终止，内层 round 控制保留。

---

## 3. 核心定义

### 3.1 SuccessChecker（`success_checks.py`）

```yaml
success_checks:
  react_turn_success:
    hard_gates: [react_turn_schema_valid, selected_skill_allowed,
                 proposed_action_schema_valid, policy_decision_recorded]
    pass_condition:
      all_hard_gates_pass: true
      semantic_score_gte: 0.75
  final_success:
    hard_gates: [final_answer_schema_valid, verification_passed,
                 no_pending_approval, required_citations_present,
                 grounding_satisfied, min_complete_chars]
    pass_condition:
      all_hard_gates_pass: true
      semantic_score_gte: 0.85
```

- `react_turn_success`：每轮结构化 turn 校验（依赖 [F17](F17_AGENT_STATE_MACHINE.md) `react_turn_schema`；`require_structured_turn=false` 时此检查降级为空集）。
- `final_success`：tick 终态前最终答复校验。

### 3.2 hard_gates 来源（既有逻辑映射）

| hard_gate | 既有逻辑 | 文件:行 |
|-----------|---------|---------|
| `grounding_satisfied` | `_needs_runtime_grounding` + `has_successful_grounding_obs` | `draft_gate.py:75-90`, `55-62` |
| `min_complete_chars` | `len(draft) < config.min_complete_chars` | `draft_gate.py:110-114` |
| `no_deferral_prose` | `_DEFAULT_DEFERRAL_PATTERNS` | `draft_gate.py:10-24`, `45-52` |
| `verification_passed` | Check `'error' not in check_out[:80]` | `llm_pdca.py:814-815` |
| `no_pending_approval` | 无 `guard_blocked_confirmation` | `execution_gate.py:110-111` |
| `policy_decision_recorded` | `policy_decision` trace 行存在 | [F16](F16_AGENT_POLICY_ENGINE.md) §9 |
| `selected_skill_allowed` | `selected_skill ∈ skill_refs ∩ allowed_in_react_states` | [F15](F15_AGENT_SKILL_REGISTRY.md) |
| `react_turn_schema_valid` / `proposed_action_schema_valid` / `final_answer_schema_valid` | JSON Schema 校验 | [F17](F17_AGENT_STATE_MACHINE.md) |

### 3.3 QualityGates（`quality_gates.py`）

per-stage `semantic_score_threshold`（@configurable）；gate 不通过触发 `StopPolicy.replan` 或 `fail`。

### 3.4 StopPolicy（`stop_policy.py`）

```yaml
stop_policy:
  precedence: [fail, pause, final_success, replan, continue]
  fail:
    any: [max_iterations_exceeded, max_consecutive_tool_failures_exceeded,
          terminal_policy_denial, budget_exceeded, draft_fail_fallback]
  pause:
    any: [user_clarification_required, high_impact_action_requires_approval]
  replan:
    any: [repeated_irrelevant_observations, current_strategy_not_progressing,
          check_retry_signal]
  final_success:
    all: [final_success.pass_condition]
```

precedence 高者优先；`fail` 终态，`pause` v1 同步降级，`final_success` 终态成功，`replan` 回到状态机 replan 入口（[F17](F17_AGENT_STATE_MACHINE.md)），`continue` 进入下一 stage/round。

---

## 4. 既有收敛点

### 4.1 `draft_gate` → `SuccessChecker.final_success`

- 既有 `assess_draft_completeness_with_budget`（`draft_gate.py:120-138`）返回 `DraftCompletenessVerdict{complete, retry_loop, fail_fallback}`（`signals.py:8-11`）。
- 收敛契约：`SuccessChecker.final_success` 内部调用既有 `assess_draft_completeness` 作为 hard_gates 求值；映射 `complete`→`final_success`、`retry_loop`→`replan`、`fail_fallback`→`fail`。
- **外部 API 保持稳定**：`assess_draft_completeness_with_budget` / `is_draft_streamable` / `DraftCompletenessVerdict` 导出不变（`agent_loop/__init__.py:7-21`）；`SuccessChecker` 在其上层包装。
- ⚠️ streaming 张力：`is_draft_streamable` gate SSE prose（`llm_pdca.py:302-319`, `510-512`）；收敛不得改变 mid-tick streaming 行为（`test_agent_loop.py` / `test_llm_pdca_*stream*` 锁定）。

### 4.2 `ToolGatherBudgets` → `StopPolicy.fail`

- 既有 caps：`max_commands_per_tick` / `max_chars_observations_per_tick` / `max_commands_per_phase` / `max_tool_rounds_per_phase`（`tool_gather.py:18-39`）。
- 耗尽 trace reasons：`tick_command_budget_exhausted` / `tick_char_budget_exhausted`（`tool_runtime_view.py:29-32`）、`tick_max_commands` / `phase_max_commands` / `tick_max_chars`（`tool_gather.py:204-221`）。
- ⚠️ 张力：今日 caps 常为 **soft-fail**（partial 执行 / 强制 notice / 空 draft，`tool_gather.py:203-208`, `llm_pdca.py:621-625`），非单一 `StopPolicy.fail` 终态。v1 `budget_exceeded` 映射既有 `fail_fallback` 路径（清 draft + `_draft_incomplete`，`llm_pdca.py:602-607`）；强制 hard-fail 终态为 opt-in（`stop_policy.fail.budget_exceeded` 显式声明时，Open Question Q1）。

### 4.3 既有隐式 stop（无统一 evaluator 今日）

| 层 | stop 信号 | 机制 |
|----|----------|------|
| ReAct 微循环 | prose-only + complete draft | `should_exit_react_round` + draft gate |
| ReAct 微循环 | max rounds / tick caps | break（`llm_pdca.py:667-668`） |
| PDCA 宏 | Check `RETRY` | 单次 replan（`847-877`） |
| tick 终态 | cancel / timeout / draft_incomplete | `FrameworkRunResult`（`914-940`） |

v1 `StopPolicy` 为既有分支的 **统一前置评估器**：在既有 break/replan 点先求值 `StopPolicy.evaluate(context)`，结果映射回既有行为（不替换既有控制流，包装层）。

---

## 5. v1 `semantic_scorer`（规则评分，无 LLM judge）

今日无可运行语义评分（draft gate 返回 enum，非 float）。v1 复用既有 **置信度/规则信号** 组合为 0..1 分：

| 信号 | 来源 | 文件:行 |
|------|------|---------|
| intent confidence | `intent_hint.confidence` | `llm_pdca.py:712-718`; `intent_classifier_interface.py:64-69` |
| tool router confidence | `RouterResult.router_confidence` | `tool_router/pipeline.py:101`; `router_thresholds.py:18-20` |
| SLM intent confidence | `PeftIntentClassifier` | `peft_intent_classifier.py:78-81` |
| grounding 满足 | `has_successful_grounding_obs` | `draft_gate.py:55-62` |
| mandatory gap | `mandatory_observation_gap` | `mandatory_gap.py:32-115` |

v1 评分函数：加权组合（`intent_confidence * w1 + grounding_satisfied * w2 + ...`），权重 @configurable，默认值在 `policy.platform_defaults` / `agents.llm.extra`。阈值 `0.75` / `0.85` 为默认，可经 `success_checks.<id>.pass_condition.semantic_score_gte` 覆盖。

⚠️ 张力：固定阈值可能 **阻断今日 `complete` 出口的回复**（今日仅布尔 draft gate）。v1 `semantic_score` 与 hard_gates **分立**：`pass_condition` 需 `all_hard_gates_pass: true` **且** `semantic_score_gte`；hard_gates 失败即 fail/replan，semantic_score 仅为额外门槛。默认阈值可经灰度调整（Open Question Q2）。

---

## 6. `pause` 与 `require_approval`（v1 同步降级）

- 今日 tick 同步端到端，无 `pause`/`resume`/`pending_approval`（[F16](F16_AGENT_POLICY_ENGINE.md) §8）。
- v1 `StopPolicy.pause` 触发时 **同步降级**：
  - `user_clarification_required` → 既有 clarification 路径（Plan 问一个问题，`settings.yaml` plan prompt）。
  - `high_impact_action_requires_approval` → 同步 block + 失败 ToolObservation（[F16] `require_approval` 降级）。
- 跨 tick 异步 pause/resume 工作流 **延后**（需 WS `awaiting_approval` 事件 + 持久化，今日不存在）。

---

## 7. 节点 attributes 与配置面

- 新增 `attributes.success_checks` / `attributes.stop_policy`（今日 **不存在**）。
- ⚠️ 配置面张力：今日质量旋钮散布于 `agents.llm.extra`（`tool_gather_max_*`、`agent_loop_min_complete_chars`、`deferral_patterns`）+ `attributes.phase_llm`。`success_checks`/`stop_policy` 为 **第三配置面**。v1 **不迁移** 既有旋钮（surgical），`SuccessChecker`/`StopPolicy` **读取既有 `agents.llm.extra` + `ToolGatherBudgets`** 作为默认，`attributes.success_checks`/`stop_policy` 仅作覆盖/追加。迁移合并延后（Open Question Q3）。
- seed 升级：参照 `phase_llm` merge-if-missing（`seed_data.py:249-264`）。

---

## 8. 可观测性

- 今日无 quality/stop 事件类型（`observability.py:48-68` 仅 LLM/tool/HTTP）；`TraceEvent` 为 eval-only（`eval/schema.py:136-157`）。
- v1 新增 `command_trace` 行：`success_check`（`{check_id, hard_gates_results, semantic_score, pass}`）、`stop_decision`（`{decision, reason, precedence_winner}`）。
- 标准化 `TraceEvent.SUCCESS_REPORT` / `STOP_DECISION` 由可观测性标准化阶段（[F10]）统一；本 SPEC 仅定义 trace 行 schema。

---

## 9. 与 F10 关系

- [F10](F10_AICO_PERFORMANCE_AND_LATENCY.md) §3/§4 定义 `max_tool_rounds_per_phase`（默认 3）、`ToolGatherBudgets` caps、RETRY 追加一整轮、单 gate budget 耗尽验收 —— 这些成为 `StopPolicy.fail.budget_exceeded` 候选。
- F10 §9 SLO（p95 ≤ 30s 内网 / ≤ 60s 公网）为 **wall-time**，非逻辑 stop；F10 §6 deadline（aspirational，未实现）—— v1 `StopPolicy.fail` **不**含 wall-time（今日无 tick deadline 实现，[F10] §6 为 SPEC-only）；wall-time deadline 纳入 `StopPolicy.fail` 需先落地 tick deadline 传递（Open Question Q4）。

---

## 10. Acceptance Criteria

- [ ] `SuccessChecker.final_success` 包装 `assess_draft_completeness`，外部 API 稳定
- [ ] `StopPolicy.evaluate` 在既有 break/replan 点前置求值，映射回既有控制流
- [ ] `budget_exceeded` 映射既有 `fail_fallback` 路径（v1 soft-fail 兼容）
- [ ] `semantic_scorer` v1 规则评分，无 LLM 调用；阈值 @configurable
- [ ] `pause` v1 同步降级（clarification / block），无跨 tick resume
- [ ] `success_check` / `stop_decision` trace 行写入 `command_trace`
- [ ] `attributes.success_checks` / `stop_policy` merge-if-missing seed
- [ ] 不破坏既有 streaming / `test_agent_loop.py` / golden trace
- [ ] 单元测试位于 `backend/tests/game_engine/`

---

## 11. Open Questions

- **Q1（budget hard-fail vs soft-fail）：** v1 `budget_exceeded` 走 soft-fail；何时 opt-in hard-fail 终态？需 `stop_policy.fail.budget_exceeded` 显式声明。
- **Q2（semantic_score 阈值）：** 默认 0.75/0.85 可能阻断今日 `complete` 回复；灰度策略与阈值标定？需 eval 集回归。
- **Q3（配置面合并）：** `agents.llm.extra` + `phase_llm` + `success_checks`/`stop_policy` 三面何时合并为单一 quality 配置？
- **Q4（wall-time deadline）：** F10 §6 tick deadline 未实现；`StopPolicy.fail.max_wall_time` 何时落地（需 deadline 传递）？
- **Q5（replan 统一）：** `StopPolicy.replan` 与 [F17](F17_AGENT_STATE_MACHINE.md) 状态机 `replan` / Check `RETRY` / `agent_loop` draft retry 何时统一为 `max_replans` 计数器？
- **Q6（LLM-as-judge）：** v2 何时引入 LLM-as-judge 语义评分（需 tick 内额外 LLM 调用预算评估）？
- **Q7（`pause` 异步化）：** 跨 tick pause/resume 何时引入（与 [F16](F16_AGENT_POLICY_ENGINE.md) Q2 联动）？

---

## 12. 后续

- [F10](F10_AICO_PERFORMANCE_AND_LATENCY.md) §stop conditions 标注为「`StopPolicy.fail` 候选」。
- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §12.4 Check gate 标注为「`SuccessChecker.final_success.verification_passed`」。
- `react_turn_success` hard_gates 依赖 [F17](F17_AGENT_STATE_MACHINE.md) `react_turn_schema`；`selected_skill_allowed` 依赖 [F15](F15_AGENT_SKILL_REGISTRY.md)。
