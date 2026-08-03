# F18 — Agent Quality Gates & Stop Policy

> **Architecture Role：** 将 Agent 运行时的 **质量判定 / 成功检查 / 停止策略** 从代码启发式升级为 **F16 PolicyEngine 上的 check_point + evaluator**。收敛既有 `agent_loop/draft_gate.py`（final_success 实现）与 `tool_gather.py` `ToolGatherBudgets`（fail 条件之一）为统一规则求值；**不**另起引擎。属 L3 思考模型层横切（[F09](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) §6.3）。
>
> **控制流权威：** [F17](F17_AGENT_STATE_MACHINE.md) 状态机 `sm.next` 是 tick 内 **唯一** 控制流权威。F18 仅产出 `PolicyDecision` 信号，由 driver 映射为既有 `runtime.*` flag / event 后供 `sm.next` 消费——与 [F16](F16_AGENT_POLICY_ENGINE.md) 行为安全平面同构（规则引擎 + check_point 插入 + 既有控制流消费）。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（`draft_gate`、Check gate、`RETRY`）、[**F10**](F10_AICO_PERFORMANCE_AND_LATENCY.md)（SLO / 轮次上限 / `ToolGatherBudgets`）、[**F16**](F16_AGENT_POLICY_ENGINE.md)（统一 PolicyEngine、`require_approval` → `pause`）、[**F17**](F17_AGENT_STATE_MACHINE.md)（`sm.next` 控制流、`react_turn_schema`、replan 计数）、[**F15**](F15_AGENT_SKILL_REGISTRY.md)（`selected_skill_allowed` gate）。

**决策状态：** 本章基于 F15–F17 落地后的架构评审：E1（F18 = Policy 机制，复用 F16 PolicyEngine；F17 = 控制流权威）已决策；`max_iterations` = 总 state transition per tick（`snapshot.turn_count`）已决策；S1–S7（推理语义质量优化）已决策：S1 剔除路由置信度、S2 草稿↔obs 重叠、S3 消费 `success_criteria`、S4 操作化 stagnation、S5 P1 结构化 Check、S6 LLM-as-judge offline-only、S7 显式四层分层。

---

## 1. Goal

- 在 [F16](F16_AGENT_POLICY_ENGINE.md) **统一 PolicyEngine** 上注册质量/停止 check_point 与纯函数 evaluator（`final_success_evaluator` / `stop_evaluator` / `react_turn_success_evaluator` / `quality_score_evaluator`），**不**另建 `SuccessChecker`/`StopPolicy` 引擎。
- 收敛 `assess_draft_completeness_with_budget` → `final_success_evaluator` 的 hard_gates；收敛 `ToolGatherBudgets` 耗尽 → `stop_evaluator` 的 `budget_exceeded` 条件。
- Driver 在非流式边界调用 `PolicyEngine.evaluate`，将 `PolicyDecision` **映射**为既有 `runtime.*` flag / event，供 [F17](F17_AGENT_STATE_MACHINE.md) `sm.next` 消费（见 §4.4）。
- v1 `quality_score_evaluator` 为 **规则评分**（不引入 LLM-as-judge，避免 tick 内额外 LLM 调用）。

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）tick 内的质量判定与停止决策；`success_checks` / `stop_policy` 节点 attributes DSL（规则覆盖，非独立引擎配置）；F16 PolicyEngine 新增 check_point 与 evaluator。
- **Non-Goals：**
  - **不**另起独立规则引擎；质量/停止规则注册进 [F16](F16_AGENT_POLICY_ENGINE.md) PolicyEngine。
  - **不**构成并行控制流；`sm.next` 是唯一控制流权威（见 §4.4）。
  - v1 **不**实现跨 tick 异步 `pause`/`resume`（tick 同步不变量；`pause` v1 同步降级为 notice/fail，见 §6 / [F16] §8）。
  - v1 **不**引入 LLM-as-judge 语义评分（S6 已决策：offline-only，tick 热路径永不默认开启）；`quality_score_evaluator` 为规则评分。
  - v1 **不**在 mid-stream 求值 / abort（仅非流式边界；mid-stream abort 为 post-v1）。
  - **不**改变 `ResolvedToolSurface` 冻结面（F08 §5.1）。
  - **不**重写 `agent_loop/` 内层 ReAct；内层 round 控制保留；外层终止经 `sm.next`。

---

## 3. 核心定义

> **锚点约定：** 既有逻辑映射以 **函数名** 为锚（不写死行号），避免 F17 driver 重构后漂移。

### 3.1 CheckPoint（扩展 F16 `check_points.py`，归属 `quality` 域）

F18 **复用** F16 CheckPoint 枚举，新增质量/停止点位。既有 F16 点位（`before_skill_activation` / `before_tool_call` / `after_tool_observation` / `before_final_answer`）不变。按 [F16](F16_AGENT_POLICY_ENGINE.md) §3.0 规则分域，F18 新增点位均归属 **`quality` 域**，evaluator 注册进 `domains/quality_domain.py`，配置走独立配置文件 `backend/config/policy.yaml` 的 `quality:` block（见 [F16] §5.1）。

| CheckPoint（F18 新增） | 触发时机 | v1 | 备注 |
|------------------------|---------|----|------|
| `after_state_execute` | `_execute_state` 返回后、`sm.next` 前 | ✅ | `stop_evaluator`；产出信号映射为 `runtime.*` |
| `before_terminal` | act 锚点 `_detect_tick_emit_deferral` 完成后、构造终态 `FrameworkRunResult` 前 | ✅ | `final_success_evaluator`；`_draft_incomplete` 是其**输入** |
| `per_react_round` | 内层 ReAct 每轮结构化 turn 校验后 | ⏸ opt-in | `react_turn_success_evaluator`；随 `require_structured_turn=true` 启用，否则 evaluator 自守卫返回 `None` |

### 3.2 QualityContext（扩展 F16 `PolicyContext`）

质量/停止求值所需字段挂在 F16 `PolicyContext`（或同会话 DTO）上，**不**新建并行 context 类型：

```python
# 质量字段（与 F16 既有 before_tool_call / before_skill_activation 字段并存）
draft_text: str = ""
tool_results: Sequence[ToolResult] = ()
user_message: str = ""
intent_confidence: Optional[float] = None    # trace-only（S1：不参与 pass_condition）
router_confidence: Optional[float] = None   # trace-only（S1：不参与 pass_condition）
grounding_satisfied: bool = False
mandatory_gap: Optional[Dict[str, Any]] = None
replan_count: int = 0
budget_remaining: bool = True
turn_count: int = 0                    # StateMachineSnapshot.turn_count（总 state transition）
react_turn: Optional[Any] = None       # F17 ReactTurn（opt-in）
selected_skill: Optional[str] = None   # F17 selected_skill（v1 inert，见 §3.5）
```

### 3.3 Evaluators（纯函数，镜像 F16 detectors）

注册进 PolicyEngine；按 check_point 调度：

| Evaluator | check_point | 输出决策（映射后） | 说明 |
|-----------|-------------|-------------------|------|
| `stop_evaluator` | `after_state_execute` | `fail` / `pause` / `replan` / `continue` | 预算、迭代上限、clarification、approval、**check_retry/mandatory_gap 统一收归**（B3，仅 `current_state=='check'`）、**stagnation**（S4，plan/do/check 态，act 抑制 B6-a）等 |
| `final_success_evaluator` | `before_terminal` | `final_success` / `fail` | 包装 `assess_draft_completeness` hard_gates + 分层 quality score（见 §5） |
| `react_turn_success_evaluator` | `per_react_round` | `continue` / `replan` / `fail` | **opt-in**；始终注册但 **自守卫**（`react_turn is None` → 返回 `None`，等价空集）；消费 `success_criteria`（S3） |
| `quality_score_evaluator` | （被 final / react_turn 调用） | `QualityScore`（多维） | 分层评分：surface / process / semantic（见 §5，S7） |

**B3 统一收归（check_retry / mandatory_gap）：** 既有 `_execute_check_state` 内的 `check_retry`（`_parse_check_retry_signal` 解析 Check LLM 输出 `RETRY: need_tools=...`）与 `mandatory_gap`（`mandatory_observation_gap` 检测 mandatory 工具缺失/失败）检测逻辑迁入 `stop_evaluator`，在 `after_state_execute` 且 `current_state=='check'` 时求值，产出单一 `PolicyDecision(decision='replan', reason_code='check_retry'/'mandatory_gap', evidence={retry_tools, gap_detail})`。

- **优先级：** `check_retry` 优先于 `mandatory_gap`——evaluator 先调 `_parse_check_retry_signal`，返回非 None 则发 `reason_code='check_retry'`；否则调 `mandatory_observation_gap`，有 gap 则发 `reason_code='mandatory_gap'`。
- **`_execute_check_state` 改造：** 仅保留 Check LLM 调用 + 把 `check_out` 写入 `PolicyContext`（经 `tick_state_ref`），不再内部检测/发 event。
- **post-loop mandatory notice（path B）留在 driver：** 是 UX 层（用户可见 fallback 文案），非 policy 决策，不进 PolicyEngine。
- **byte-equiv 约束：** 统一收归后 `check→plan` transition、`mandatory_gap_retry_override`/`check_retry_triggered` trace 行、`replan_count` 自增逻辑须与既有 byte-equiv（详见 §4.4 映射 + P1 测试 `test_llm_pdca_unified_replan.py`）。

**质量维度分层（S7）：** 评分不再为单一 float，而是显式四层（trace 记录每维子分，可独立开关 / 独立标定阈值）：

| 维度 | 含义 | v1 纯函数信号 | 纳入 `pass_condition`？ |
|------|------|--------------|----------------------|
| `surface` | 可交付形态（长度、deferral、格式） | 已由 hard_gates 覆盖（`min_complete_chars` / `no_deferral_prose`） | 否（hard_gate 已判；score 仅记录） |
| `process` | 过程充分性（工具调用、预算、mandatory gap） | mandatory_gap 关闭、tool rounds 使用率 | 可选（默认 off，保 byte-equivalent） |
| `semantic` | 答案正确性（grounding 对齐、criteria 覆盖、progress） | `grounding_quality`（草稿↔obs 重叠，S2）+ `criteria_coverage`（structured turn，S3）+ `progress`（非停滞，S4） | **是**（核心维度） |
| `judge` | 主观质量（helpfulness、tone） | — | **v1 不纳入**（offline-only，见 §5.1，S6） |

**DSL 形状（节点 attributes 覆盖，非独立引擎）：**

```yaml
success_checks:
  react_turn_success:          # opt-in；默认不启用
    hard_gates: [react_turn_schema_valid, selected_skill_allowed,
                 proposed_action_schema_valid, policy_decision_recorded]
    pass_condition:
      all_hard_gates_pass: true
      # 分层 quality score（S7）：每维独立阈值，默认 off 保 byte-equivalent
      quality_score:
        semantic_gte: 0.75      # grounding_quality + criteria_coverage + progress
        # process_gte: 0.60     # 可选，默认注释
        # surface_gte: 0.80     # 可选，默认注释（多由 hard_gate 覆盖）
  final_success:
    hard_gates: [final_answer_schema_valid, verification_passed,
                 no_pending_approval, grounding_satisfied, min_complete_chars,
                 obs_grounded_claims]   # S2：草稿↔obs 重叠（default-off）
                 # required_citations_present 为 v2（见 §3.5）
    pass_condition:
      all_hard_gates_pass: true
      quality_score:
        semantic_gte: 0.85

stop_policy:
  precedence: [fail, pause, final_success, replan, continue]
  fail:
    any: [max_iterations_exceeded, max_consecutive_tool_failures_exceeded,
          terminal_policy_denial, budget_exceeded, draft_fail_fallback]
  pause:
    any: [user_clarification_required, high_impact_action_requires_approval]
  replan:
    any: [repeated_irrelevant_observations, current_strategy_not_progressing,  # S4：已操作化（见 §5）
          check_retry_signal]
  final_success:
    all: [final_success.pass_condition]
```

precedence 用于 **evaluator 内部** 选择最高优先级命中；**不**由 evaluator 直接改写控制流——命中结果经 §4.4 映射后由 `sm.next` 转移。

### 3.4 Decision = 复用 F16 `PolicyDecision`

复用 [F16](F16_AGENT_POLICY_ENGINE.md) §3.2 `PolicyDecision` 形状。F18 扩展两个 **可选** 字段（向后兼容）：

```python
@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal[
        'deny', 'allow', 'require_approval', 'allow_with_transform',
        # F18 质量/停止扩展（同枚举或并列映射，实现时统一）
        'fail', 'pause', 'final_success', 'replan', 'continue',
    ]
    reason_code: str
    check_point: str
    runtime_action: Literal['block', 'pause', 'transform', 'block_and_rewrite', 'pass']
    transform_applied: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None
    # F18 扩展（可选）
    quality_score: Optional[Dict[str, float]] = None  # 分层子分：{surface, process, semantic}（S7）
    degraded_action: Optional[str] = None  # pause→block/clarify 时记 'block'/'clarify'
```

> **`QualityScore` 形状：** `{"surface": float, "process": float, "semantic": float}`，每维 0..1，trace 记录每维子分；`pass_condition` 按维度独立设阈值（`semantic_gte` / `process_gte` / `surface_gte`），默认仅 `semantic_gte` 生效，其余注释（保 byte-equivalent）。`judge` 维度 v1 不在热路径（offline-only，见 §5.1）。

> **B5 `decision → runtime_action` 派生映射（v1 契约）：** 保留双字段（不合并）——`decision`=语义/审计结果，`runtime_action`=当期命令式行为。F18 evaluator 产出 `decision` 时按下表派生 `runtime_action`：
>
> | `decision` | `runtime_action` | 说明 |
> |-----------|------------------|------|
> | `fail` | `block` | 不可恢复终止，等价 block 终态 |
> | `pause` | `pause` | v1 同步降级时由 `degraded_action` 覆盖为 `block`/`clarify`，但基础 action 标 `pause` 保留语义 |
> | `final_success` | `pass` | 正常通过，无阻断 |
> | `continue` | `pass` | 继续执行，无阻断 |
> | `replan` | `pass` | replan 由 event（`check_retry`/`mandatory_gap`/`stagnation`）驱动 transition，`runtime_action` 保持 `pass` 不阻断 |
>
> 运行时消费者统一走 `is_block`/`is_allow`，不直接读 `decision`/`runtime_action` 做控制流；trace 序列化复用 `execution_gate._policy_decision_to_trace` helper（修复 `llm_pdca._prepare_skill_context` 硬编码 bug，见 [F16] §7）。

### 3.5 hard_gates 来源（既有逻辑映射）

| hard_gate | 既有逻辑 | 锚点（函数） | v1 状态 |
|-----------|---------|-------------|---------|
| `grounding_satisfied` | `_needs_runtime_grounding` + `has_successful_grounding_obs` | `draft_gate.py` | ✅（存在性布尔：grounding 工具成功过） |
| `obs_grounded_claims`（S2） | 草稿与成功 obs 文本的 token/实体重叠 ≥ 阈值 | 新增纯函数 evaluator（`quality_score_evaluator` 内） | ⏸ **default-off**（保 byte-equivalent；启用后从「调过工具」升级为「答案有据」） |
| `min_complete_chars` | `len(draft) < config.min_complete_chars` | `draft_gate.assess_draft_completeness` | ✅ |
| `no_deferral_prose` | `_DEFAULT_DEFERRAL_PATTERNS` / `is_deferral_prose` | `draft_gate.py` | ✅ |
| `verification_passed` | Check 输出含 error 语义（今日子串启发式） | Check 态执行（`_execute_pdca_state` / check path） | ⚠️ v1 placeholder；**P1 升级为结构化 Check 输出**（`PASS\|RETRY\|FAIL` + `reason_codes`，见 S5 / §5.4） |
| `success_criteria_addressed`（S3） | structured turn `success_criteria` 关键词/子串在草稿中命中 ≥ N 条 | 新增 evaluator（opt-in，随 `require_structured_turn`） | ⏸ **opt-in**（free-text 模式跳过） |
| `no_pending_approval` | 无 `guard_blocked_confirmation` / policy block | `execution_gate.evaluate_execution_gate` | ✅ |
| `policy_decision_recorded` | **若本轮需要 policy decision，则须为 allow；无 policy decision = pass**（非「trace 行必须存在」） | [F16](F16_AGENT_POLICY_ENGINE.md) §9 | ✅ 语义修正 |
| `selected_skill_allowed` | `selected_skill ∈ skill_refs`（+ phase 约束） | [F15](F15_AGENT_SKILL_REGISTRY.md) / [F17](F17_AGENT_STATE_MACHINE.md) | ⏸ **inert** 直至 F17 D3-B / D6 `selected_skill` 消费落地 |
| `react_turn_schema_valid` / `proposed_action_schema_valid` / `final_answer_schema_valid` | JSON Schema / Pydantic 校验 | [F17](F17_AGENT_STATE_MACHINE.md) `react_turn_schema` | ✅（随 structured turn opt-in） |
| `required_citations_present` | — | — | ❌ **v2**（无 citation 系统；不列入 v1 `final_success.hard_gates`） |

### 3.6 文件布局与域归属

F18 evaluator 落地为 [F16](F16_AGENT_POLICY_ENGINE.md) §3.0 定义的 **`quality` 域**，文件位于 `backend/app/game_engine/agent_runtime/policy/domains/quality_domain.py`，与 `skill_domain.py` / `gate_domain.py` 并列。`DomainRegistry` 在启动期注册 quality 域单例，`PolicyEngine.evaluate` 按 check_point → domain 派发。

```
backend/app/game_engine/agent_runtime/policy/domains/
├── skill_domain.py     # F15/F16 skill 域
├── gate_domain.py      # F16 gate 域
└── quality_domain.py   # F18 quality 域（本 SPEC 落地）
```

quality 域 v1 注册的 evaluator 见 §3.3；配置开关与默认阈值见 [F16](F16_AGENT_POLICY_ENGINE.md) §5.1（`backend/config/policy.yaml` 的 `quality:` block），节点级覆盖优先级见 §7。

**N1 `build_context` 数据流：** driver 构造域无关的 `base = PolicyContext(check_point=..., extra={'tick_state': tick_state_ref})`，`tick_state_ref` 指向当前 tick 的 draft / tool_results / snapshot / ctx.payload / check_out 等 runtime state。`PolicyEngine` 派发前调目标域 `Domain.build_context(base)`，各域从 `tick_state_ref` 提取本域语义字段（quality 域取 `draft_text`/`tool_results`/`turn_count`/`replan_count`/`react_turn`/`check_out`/`grounding_satisfied`/`mandatory_gap`；skill/gate 域字段见 [F16] §3.0）。域保持纯函数（只读 `tick_state_ref`，不读全局），driver 不再手工拼装全字段 context。

---

## 4. 既有收敛点

> **G1-A 决策（v1 evaluator 定位）：** v1 的 F18 evaluator（`stop_evaluator` / `final_success_evaluator` / `quality_score_evaluator` / `react_turn_success_evaluator`）注册进 `QualityDomain` + 单测覆盖。**P5-A 已接线**：driver 在 `_execute_state` / `_execute_act_state` / `_phase_react_loop` 调用 `PolicyEngine.evaluate` 并记录 `quality_decision` trace 行；新维度经 config 开关 `enable_stop_dimensions` 默认 off，`final_success_evaluator` 经 `final_success_drive_mode`（off/shadow/enforce，D-B）默认 off，默认 config 下 byte-equivalent。`final_success_evaluator` 在 `shadow` 下为 audit + divergence 检测（`_detect_tick_emit_deferral` 仍为权威），`enforce` 下驱动 `draft_incomplete`（`retry_loop→replan` 待 D-I）；`detect_check_replan` 已收归 `stop_evaluator`（P5-B1）；`per_react_round` B4 loop 消费已接线（P5-B2）。本节 §4.4 描述 P5 目标契约。

### 4.1 `draft_gate` → `final_success_evaluator`

- 既有 `assess_draft_completeness_with_budget`（`draft_gate.py`）返回 `DraftCompletenessVerdict{complete, retry_loop, fail_fallback}`（`signals.py`）。
- 收敛契约：`final_success_evaluator` 内部调用既有 `assess_draft_completeness` 作为 hard_gates 求值；映射 `complete`→`final_success`、`retry_loop`→`replan`、`fail_fallback`→`fail`。
- **外部 API 保持稳定**：`assess_draft_completeness_with_budget` / `is_draft_streamable` / `DraftCompletenessVerdict` 导出不变（`agent_loop/__init__.py`）；evaluator 在其上层包装。
- **驱动模式（D-B，`final_success_drive_mode`）：**
  - `off`（默认，byte-equiv）：evaluator 不求值，无 trace 行；`_detect_tick_emit_deferral` 为唯一权威。
  - `shadow`：evaluator 求值并记 `quality_decision` 行；`_detect_tick_emit_deferral` 仍为权威；当 evaluator verdict 与 deferral 结果在 pass/fail 边界上不一致（或为 `retry_loop` 第三态）时，记 `final_success_divergence` 行（不阻断）。
  - `enforce`：evaluator verdict 驱动 `runtime.draft_incomplete`（`final_success` 清、`fail` 置）；`_detect_tick_emit_deferral` 降为 fallback（evaluator 返回 `None`/异常时生效）。`retry_loop→replan` 需 `act→plan` transition（D-I），D-I 落地前 enforce 对 `retry_loop` 仍 audit-only 并回退 deferral。
- **与 act 锚点顺序：** `final_success_evaluator` 在 `_detect_tick_emit_deferral` **之后**求值；`ctx.payload['_draft_incomplete']` 是其**输入**，不与 act 锚点竞争权威重判。
- ⚠️ streaming 张力：`is_draft_streamable` gate SSE prose（`_phase_react_loop` / stream hooks）；收敛不得改变 mid-tick streaming 行为（`test_agent_loop.py` / `test_llm_pdca_*stream*` 锁定）。v1 **不**在 mid-stream 求值。

### 4.2 `ToolGatherBudgets` → `stop_evaluator.budget_exceeded`

- 既有 caps：`max_commands_per_tick` / `max_chars_observations_per_tick` / `max_commands_per_phase` / `max_tool_rounds_per_phase`（`tool_gather.ToolGatherBudgets`）。
- 耗尽 reasons：`tick_command_budget_exhausted` / `tick_char_budget_exhausted`（`tool_runtime_view.resolve_tool_runtime_view`）、`tick_max_commands` / `phase_max_commands` / `tick_max_chars`（`gather_tool_observations`）。
- ⚠️ 张力：今日 caps 常为 **soft-fail**（partial 执行 / 强制 notice / 空 draft），非单一 `fail` 终态。v1 `budget_exceeded` 映射既有 `fail_fallback` 路径（清 draft + `_draft_incomplete` → 经 `act→fail`）；强制 hard-fail 终态为 opt-in（`stop_policy.fail.budget_exceeded` 显式声明时，Open Question Q1）。
- **P5-B3 落地：** `stop_evaluator` 经 `enable_stop_dimensions` 门控读取 tick-level caps（`commands_run`/`max_commands_per_tick`/`observation_chars`/`max_chars_observations_per_tick`，由 driver 经 `tick_state` 注入）。默认 **soft-fail** → `PolicyDecision.continue_("budget_exceeded")`（audit/trace-only；既有 draft-gate `fail_fallback` 路径保持权威，控制流不变）。opt-in **hard-fail** 经 `enable_budget_hard_fail` → `PolicyDecision.fail("budget_exceeded")` → driver 映射 `runtime.stop_fail` → F17 `*→fail`（任意态，Q1）。优先级：fail 级（max_iterations / max_consecutive / budget hard-fail）→ 可恢复 replan（check_retry / mandatory_gap / react_round / stagnation）→ budget soft-fail `continue`（最低，仅 audit）。

### 4.3 既有隐式 stop → `stop_evaluator` 统一前置

| 层 | stop 信号 | 机制 |
|----|----------|------|
| ReAct 微循环 | prose-only + complete draft | `should_exit_react_round` + draft gate |
| ReAct 微循环 | max rounds / tick caps | break（`_phase_react_loop`） |
| PDCA 宏 | Check `RETRY` / mandatory-gap | `on_event: check_retry` / `mandatory_gap` → `sm.next` |
| tick 终态 | cancel / draft_incomplete | `runtime.cancelled` / `runtime.draft_incomplete` → `sm.next` → `fail` |

v1 `stop_evaluator` 为既有分支的 **统一前置评估器**：在 `after_state_execute` 求值，结果经 §4.4 映射回既有 `runtime` / event（**不**替换 `sm.next`）。

### 4.4 消费契约（F18 → F17，解决控制流权威）

> **状态：P5-A 已接线。** 以下流程描述 driver 接线后的目标行为。P5-A 已在三个 F18 check_point 调用 `PolicyEngine.evaluate` 并记录 `quality_decision` trace 行；stop `fail` 经 `runtime.stop_fail` + F17 `*→fail` 任意态终止（D1）；stagnation 经 F17 `*→plan on_event=stagnation` replan / 超限 `*→fail`（D2）；`per_react_round` 写 `ctx.payload['react_round_decision']`（D3，B4 loop 消费未接线）；trace 行复用 `_policy_decision_to_trace`（D4）。新维度经 config 开关默认 off（byte-equivalent）。`final_success_evaluator` 当前 audit/trace-only（`_detect_tick_emit_deferral` 仍为 draft 权威）；`detect_check_replan` 仍内联；B4 loop 消费未接线——这三项为 P5-B 后续（见 §4 收敛点引言 G1-A）。

```
# 非 act 态（plan/do/check）：
_execute_state
    → PolicyEngine.evaluate(check_point='after_state_execute')   # stop_evaluator
    → map PolicyDecision → runtime flags / events
    → sm.next(current, TransitionContext)                       # 唯一控制流权威（单次）
    → state_transition trace / snapshot.advance

# act 态（单次 sm.next，B6-b）：
_execute_state(act)
    → PolicyEngine.evaluate(check_point='after_state_execute')  # stop_evaluator（仅设 flag，不调 sm.next）
    → _detect_tick_emit_deferral                                # act 锚点权威重判草稿
    → PolicyEngine.evaluate(check_point='before_terminal')      # final_success_evaluator
    → map → runtime.draft_incomplete / success path
    → sm.next(act, TransitionContext)                           # 单次（合并 flag/event）
    → state_transition trace / snapshot.advance

# per_react_round（内层 ReAct，不直接驱动 sm.next，B4）：
每轮结构化 turn 校验后
    → PolicyEngine.evaluate(check_point='per_react_round')      # react_turn_success_evaluator（opt-in）
    → 写 ctx.payload['react_round_decision'] = {decision, reason_code}
    → _phase_react_loop 读 payload：
        continue → 继续下一 round
        replan/fail → break 内层 loop + flag 传递给外层 after_state_execute 二次确认
```

**映射规则（v1，最小侵入，PDCA 模板不变）：**

| `PolicyDecision.decision` | 映射到 | `sm.next` 消费 | 用户可见 |
|---------------------------|--------|----------------|---------|
| `fail`（cancel） | `runtime.cancelled=true` | `*→fail` | 既有 cancel UX（`aico/profile` `kind: cancelled`） |
| `fail`（draft / budget / max_iterations / max_consecutive_failures） | `runtime.stop_fail=true` | `*→fail`（F17 模板 `*→fail on runtime.stop_fail`，任意态生效） | `empty_reply_fallback` 消息（既有，`_resolve_npc_agent_empty_reply_message`） |
| `replan`（check_retry / mandatory_gap，B3 统一收归） | `event=check_retry` / `mandatory_gap` + `budget_remaining` | `check→plan` | **不可见**（用户不感知 replan） |
| `replan`（stagnation，R2 方案A，B6-a 仅 plan/do/check 态） | `event=stagnation`（`replan_count < max_replans and budget_remaining`）；否则 `runtime.stop_fail=true` | `*→plan on_event=stagnation`（F17 模板已落地，受 `replan_count < max_replans` 约束）；超限 → `*→fail` | **不可见**（首次）；超限 → `empty_reply_fallback` |
| `replan`（per_react_round，B4） | 写 `ctx.payload['react_round_decision']`，内层 loop break + flag 传递 | 外层 `after_state_execute` 二次确认 → `event=stagnation`（复用 `*→plan`，P5-B2）；`fail` → `stop_fail` | **不可见** |
| `pause` | v1 同步降级 → clarify/block；`degraded_action` 记入 evidence | 不新增 transition | clarify → 用户见问题；block → 既有 block UX |
| `final_success` / `continue` | 不置 abort flag | 正常出边 → `end` / 下一态 | 正常回复 |

**B6-a（stagnation 在 act 抑制）：** `stop_evaluator` 仅在 `current_state ∈ {plan, do, check}` 时发 `event=stagnation`；在 `act` 态，progress 判定归 `before_terminal` 的 `final_success_evaluator`（draft 完整即 success，deferral 重复走 `fail_fallback`）。避免 `act→plan on_event=stagnation` 拦截 `act→end`。

**B6-b（act 单次 sm.next）：** 非 act 态：`after_state_execute` 求值后直接 `sm.next`（单次）。act 态：`after_state_execute` 仅设 flag（不调 `sm.next`），`_detect_tick_emit_deferral` + `before_terminal` 完成后**单次** `sm.next` 消费合并后的 flag/event。状态机每态只推进一次。

**B4（per_react_round 不直接驱动 sm.next）：** `react_turn_success_evaluator` 写 `ctx.payload['react_round_decision']`，`_phase_react_loop` 消费——`continue` 继续下一 round；`replan`/`fail` break 内层 loop，flag 传递给外层 `after_state_execute` 的 `stop_evaluator` 二次确认（外层按 `react_round_decision` 发 `event=check_retry`/`stagnation`，由 `sm.next` 消费）。外层 `sm.next` 仍是唯一控制流权威。

**可恢复 vs 不可恢复分类（R4）：**

| 质量失败类型 | 决策 | 可恢复？ | 用户可见 |
|------------|------|---------|---------|
| grounding 不足 / criteria 未覆盖 | `replan` | ✅ 可恢复 | 不可见 |
| stagnation（首次） | `replan`（`event=stagnation`） | ✅ 可恢复 | 不可见 |
| stagnation（超 `max_replans`） | `fail` | ❌ 不可恢复 | `empty_reply_fallback` |
| `max_iterations_exceeded` | `fail` | ❌ 不可恢复 | `empty_reply_fallback` |
| `budget_exceeded`（soft-fail） | `fail_fallback`（清 draft + `_draft_incomplete`） | ❌ 不可恢复 | `empty_reply_fallback` |
| `max_consecutive_tool_failures_exceeded` | `fail` | ❌ 不可恢复 | `empty_reply_fallback` |
| `terminal_policy_denial` | `fail` | ❌ 不可恢复 | 既有 block UX |
| cancel | `fail`（`error_code=cancelled`） | ❌ 不可恢复 | 既有 cancel UX |

- **不**引入并行控制流；driver 是唯一把 PolicyDecision 写入 `runtime` 的适配层。
- **显式 `runtime.stop_decision` + 新 transition** 预留为 post-v1 / 可执行自定义 workflow 升级（Open Question Q8）。

---

## 5. v1 `quality_score_evaluator`（分层语义质量，无 LLM judge）

### 5.0 设计原则（S7 显式分层）

业界（RAGAS / Vertex Groundedness / OpenAI evals / LangSmith）将质量分拆为可独立度量、独立标定、独立开关的维度。F18 v1 采用显式四层，trace 记录每维子分：

| 维度 | 含义 | v1 纯函数信号 | 纳入 `pass_condition` |
|------|------|--------------|---------------------|
| `surface` | 可交付形态（长度、deferral、格式） | 已由 hard_gates 覆盖 | 否（hard_gate 已判；score 仅记录） |
| `process` | 过程充分性（工具调用、预算、mandatory gap） | mandatory_gap 关闭、tool rounds 使用率 | 可选（默认 off） |
| `semantic` | 答案正确性（grounding 对齐、criteria 覆盖、progress） | `grounding_quality` + `criteria_coverage` + `progress` | **是**（核心维度） |
| `judge` | 主观质量（helpfulness、tone） | — | **v1 不纳入**（offline-only，见 §5.1） |

### 5.1 `semantic` 维度（核心，S1/S2/S3/S4）

**S1 — 剔除路由置信度：** `intent_confidence` / `router_confidence` **不计入** `semantic` 维度。它们衡量「路由有多确信」，非「答案是否成立」——高置信误路由会抬高「语义分」造成误判。降为 **trace-only 旁路指标**（仍记录，不参与 `pass_condition`）。

**S2 — `grounding_quality`（草稿↔obs 重叠）：** 当 `_needs_runtime_grounding` 为 true 时，对最终草稿做分词/关键名词提取，计算与成功 obs 文本的 token 重叠率（Jaccard 或覆盖率）。低于阈值 → `semantic` 维度低分 / `obs_grounded_claims` hard_gate fail。阈值保守（建议 0.15），default-off 保 byte-equivalent。将「调过工具」升级为「答案有据」。

⚠️ **局限（R5）：** token 重叠是语义对齐的 **粗代理**——无法区分反义（「在三楼」vs「不在三楼」高重叠但矛盾）、同义（「阅览室」vs「图书馆」低重叠但对齐）、词堆砌（高重叠但无意义）。**升级条件：** 当 offline judge（§5.3 rubric）标定后发现 token 重叠的误判率 **> 25%（@configurable）**，则升级为 NLI 或 LLM claim extraction（仍 offline 标定，不入热路径）。v1 分词用轻量策略（正则/字符级 bigram），不引入 jieba 等重依赖。

**S3 — `criteria_coverage`（structured turn）：** `require_structured_turn=true` 时，读 F17 `ReactTurn.success_criteria`，检查草稿中是否出现 criteria 的关键词/子串——**pass 规则为「至少 N 条 criteria 命中」，默认 N=1**（@configurable via `success_checks.react_turn_success.react_turn_min_criteria_hits`，v1 由 evaluator 读 `tick_state['react_turn_min_criteria_hits']`，默认 1）。一条 criterion「命中」= 其所有 token（len≥2）均出现在草稿中。命中数 < N → `replan`（可恢复，R4）；free-text 模式跳过（无 criteria 来源）。先做 soft score（opt-in），稳定后可升 `success_criteria_addressed` hard_gate。

**S4 — `progress`（非停滞）：** 检测连续 K 轮（默认 **K=3**，@configurable via `policy.quality.stagnation_window`）满足任一：
- 相同 `(tool_name, tool_args)` 重复；
- obs 文本哈希重复；
- 草稿为同一 deferral 文案。
**循环模式扩展（R6，已实现）：** 除相邻重复外，还检测 **sliding window 内无新 obs**——最近 2K 轮的 obs 哈希集合大小 ≤ 2（覆盖 A→B→A→B 循环）。纯函数实现：维护 obs 哈希 sliding window set，O(1) 检查。
命中 → `progress` 维度低分 → `stop_evaluator` 发 `replan`（`event=stagnation`，首次，受 `replan_count < max_replans` 约束）→ `fail`（超限）。操作化了 DSL 中的 `repeated_irrelevant_observations` / `current_strategy_not_progressing`（此前为空契约）。

**`semantic` 维度评分：** `grounding_quality * w_g + criteria_coverage * w_c + progress * w_p`，权重 @configurable，默认 `w_g=0.5, w_c=0.3, w_p=0.2`。阈值 `semantic_gte` 默认 0.75（react_turn）/ 0.85（final），可经 `success_checks.<id>.pass_condition.quality_score.semantic_gte` 覆盖。默认 config 下可关掉 semantic 门槛以保持 byte-equivalent。

⚠️ 张力：固定阈值可能阻断今日 `complete` 出口的回复。`quality_score` 与 hard_gates **分立**：`pass_condition` 需 `all_hard_gates_pass: true` **且** `quality_score.semantic_gte`；hard_gates 失败即 fail/replan，quality_score 仅为额外门槛。阈值标定需 offline eval（见 §5.3）。

### 5.2 `process` 维度（可选，default-off）

- mandatory_gap 关闭（所有 mandatory 工具成功调用）→ 高分；
- tool rounds 使用率（已用轮次 / `max_tool_rounds_per_phase`）→ 过低或打满均为弱信号；
- **`observation_relevance`（R7）：** obs 文本与 `user_message` 的 token 重叠 / 关键词匹配——低相关性（obs 答非所问）→ `process` 维度低分。纯函数，与 `grounding_quality` 同类方法但比较对象为 obs vs user_message。default-off。
- 默认注释（不纳入 `pass_condition`），保 byte-equivalent；可作为 trace 诊断。

### 5.3 LLM-as-judge 边界（S6，offline-only）

**硬约束：** LLM-as-judge **只跑 offline eval / 采样审计**（`agent_runtime/eval` harness），**tick 热路径永不默认开启**。

- 理由：tick 内 judge 会引入额外 LLM 调用（延迟翻倍、成本翻倍、非确定性），破坏 [F10](F10_AICO_PERFORMANCE_AND_LATENCY.md) SLO（p95 ≤ 30s 内网）。
- judge 结果用于 **标定 v1 纯函数阈值**（关 Q2），而非实时 gate。
- 可经显式 config 开启 tick 内 judge，但须标注延迟代价，且默认关。

**阈值标定工作流（R10，default off）：**

1. **跑 offline eval**（≥ 50 golden samples）→ 收集 `quality_score.semantic` 分布；
2. **标定阈值** = 使今日 `complete` 出口回复的 P95 通过的分数（即阈值 ≤ complete-reply scores 的 P5）；
3. **Shadow mode**（只记录 `quality_decision` trace，不阻断）→ 验证无误伤；
4. **开启阻断** → 连续 2 个 eval 周期稳定后锁定。
- 默认 config 下 quality 门槛 **off**（保 byte-equivalent）；标定完成后灰度开启。

**Offline rubric 契约（与 `agent_runtime/eval` 对齐）：**

| Rubric 维度 | 度量 | 用途 |
|------------|------|------|
| faithfulness / groundedness | claim 逐条能否被 obs 撑 | 标定 `grounding_quality` 阈值；**R5 升级条件判定**（误判率 > 25% @configurable → 升级 NLI） |
| criteria coverage | `success_criteria` 命中率 | 标定 `criteria_coverage` 阈值 |
| tool necessity | mandatory 是否调用且成功 | 验证 `process` 维度 |
| stagnation rate | 重复 tool/obs/deferral 频率 | 标定 `progress` K 值 |

### 5.4 结构化 Check 输出（S5，P1）

当前 `verification_passed` 映射为 `'error' not in check_out[:80]`（子串启发式，脆弱）。**P1 升级**：Check 输出契约改为结构化首行：

- `PASS` — 验证通过；
- `RETRY: need_tools=<a,b,c>` — 需补工具（已有 `_parse_check_retry_signal` 可扩展）；
- `FAIL: reason=<code>` — 验证失败。

`verification_passed` 读结构化标记而非子串。需改 Check prompt + 解析逻辑。v1 接受 placeholder 至 P1 落地。

### 5.5 Evaluator 性能预算（R8，预留不实现）

v1 evaluator 为纯函数、O(n) 复杂度（n = draft/obs 文本长度），**无额外 LLM 调用**。SPEC 预留性能预算约束但 **v1 不实现** perf 测量函数：

- **预留约束：** 单次评估目标 < 5ms；v1 分词用轻量策略（正则/字符级 bigram），不引入 jieba 等重依赖。
- **预留函数：** `quality_score_evaluator` 接口预留 `eval_ms: Optional[float]` 返回字段（`PolicyDecision.evidence` 内），v1 不填充；post-v1 实现 perf 测量并写入 trace。
- **`per_react_round` 限制（R9）：** v1 `react_turn_success_evaluator` 仅在 `require_structured_turn=true` 时注册（free-text 模式无 per-round 质量检查）。此为 v1 已知限制，不修改；free-text per-round progress 检查为 post-v1 增强（依赖 S4 stagnation 信号，不依赖 structured turn）。`per_react_round` evaluator 接口预留，v1 不在 free-text 模式注册。

### 5.6 `max_consecutive_tool_failures_exceeded`（R11）

DSL `stop_policy.fail.any` 列出但此前无定义。**R11 定义：**

- **计数器：** 连续 `ToolResult.ok=False` 计数（在 `after_tool_observation` check_point 更新；成功调用重置为 0）。
- **阈值：** 默认 **3**（@configurable via `stop_policy.fail.max_consecutive_tool_failures`）。
- **决策：** 计数 ≥ 阈值 → `stop_evaluator` 发 `fail`（不可恢复，见 §4.4 R4 表）。
- **纯函数：** 在 `stop_evaluator` 内读计数器判定。

### 5.7 Evaluator 异常处理（B7）

质量门是 tick 热路径上的新增逻辑，evaluator 自身必须有 fail-safe 语义——**质量门异常不应比「无质量门」更糟**。

| Evaluator | 异常来源 | 处理策略 |
|-----------|---------|---------|
| `stop_evaluator` | 分词失败、字段访问、stagnation 哈希计算等 | log `evaluator_error` reason_code + 返回 `allow`（byte-equiv 保底，tick 按既有路径继续） |
| `quality_score_evaluator` | 分词、criteria 解析、obs 重叠计算 | log `evaluator_error` + 返回 `allow`（不阻断；score 维度记为 null） |
| `final_success_evaluator` | 包装的 `assess_draft_completeness` **自身异常** | 走既有 `fail_fallback`（**不吞掉**既有异常路径，保既有行为） |
| `final_success_evaluator` | 外层逻辑（hard_gates 组装、quality_score 调用）异常 | log `evaluator_error` + 降级为既有 `assess_draft_completeness` 结果（跳过 quality_score 维度） |
| `react_turn_success_evaluator` | 结构化 turn 解析异常 | log `evaluator_error` + 写 `ctx.payload['react_round_decision']={'continue'}`（内层 loop 继续，不阻断） |

- **trace：** 异常时 `quality_decision`/`policy_decision` trace 行记录 `reason_code='evaluator_error'` + 异常摘要（不静默吞掉），供 offline 排查。
- **核心原则：** 增量门异常时回退到「无门」即 byte-equiv；`final_success_evaluator` 包装的既有 `assess_draft_completeness` 异常保留既有 `fail_fallback` 路径，不被 evaluator 外层吞掉。

---

## 6. `pause` 与 `require_approval`（v1 同步降级）

- 今日 tick 同步端到端，无 `pause`/`resume`/`pending_approval`（[F16](F16_AGENT_POLICY_ENGINE.md) §8）。
- v1 `stop_evaluator` 发出 `pause` 时 **同步降级**：
  - `user_clarification_required` → 既有 clarification 路径（Plan 问一个问题，`settings.yaml` plan prompt）；`degraded_action='clarify'`。
  - `high_impact_action_requires_approval` → 同步 block + 失败 ToolObservation（[F16] `require_approval` 降级）；`degraded_action='block'`。
- **可审计：** `quality_decision` / `policy_decision` trace 行同时记录 `decision='pause'` + `degraded_action` + `reason_code`（不得只记降级后的 block）。
- 跨 tick 异步 pause/resume 工作流 **延后**（需 WS `awaiting_approval` 事件 + 持久化，今日不存在）。

---

## 7. 节点 attributes 与配置面

- 按 [F16](F16_AGENT_POLICY_ENGINE.md) §3.0 规则分域，F18 质量域平台默认配置走 **独立配置文件 `backend/config/policy.yaml`** 的 `quality:` block（见 [F16] §5.1，由 `PolicyConfig` 加载）+ 节点级 `attributes.success_checks` / `attributes.stop_policy`（域内覆盖）。
- 新增 `attributes.success_checks` / `attributes.stop_policy`（今日 **不存在**）；节点级域覆盖命名空间为 `attributes.policy.quality.*`（v1 仍代码注册，YAML 覆盖延后，见 [F16] §5.2）。
- **解析优先级（冲突时）：** `agents.llm.extra`（默认旋钮） < `attributes.phase_llm`（阶段覆盖） < `attributes.success_checks` / `attributes.stop_policy`（质量域 DSL 覆盖） < `policy.yaml: quality.*`（平台默认开关/阈值，仅作未覆盖时的兜底）。
- ⚠️ 配置面张力：今日质量旋钮散布于 `agents.llm.extra`（`tool_gather_max_*`、`agent_loop_min_complete_chars`、`deferral_patterns`）+ `attributes.phase_llm`。`success_checks`/`stop_policy` 为 **第三配置面**。v1 **不迁移** 既有旋钮（surgical）；evaluator **读取既有 `agents.llm.extra` + `ToolGatherBudgets`** 作为默认，attributes 仅作覆盖/追加。迁移合并延后（Open Question Q3）。
- seed 升级：参照 `phase_llm` merge-if-missing（`seed_data.ensure_aico_npc_agent`）。

---

## 8. 可观测性

- 今日 runtime observability（`observability.AgentRuntimeObservability`）仅 LLM/tool/HTTP；`TraceEvent` 为 eval-only（`agent_runtime/eval/schema.py`）。
- v1 新增 `command_trace` 行：`quality_decision`（复用 [F16](F16_AGENT_POLICY_ENGINE.md) `policy_decision` 形状 + `quality_score`（多维子分 `{surface, process, semantic}`）/ `degraded_action`；`check_point` 区分 `after_state_execute` / `before_terminal` / `per_react_round`）。trace 记录每维子分以便调试与阈值标定。
- 亦可写作 `step: policy_decision` 且 `check_point` 为 F18 点位——与 F16 行 schema 兼容，eval adapter 按 `check_point` 分流即可。
- 标准化 `TraceEvent` 枚举由可观测性标准化阶段（[F10]）统一；本 SPEC 仅定义 trace 行 schema。

---

## 9. 与 F10 关系

- [F10](F10_AICO_PERFORMANCE_AND_LATENCY.md) §3/§4 定义 `max_tool_rounds_per_phase`（默认 3）、`ToolGatherBudgets` caps、RETRY 追加一整轮、单 gate budget 耗尽验收 —— 这些成为 `stop_evaluator` 的 `budget_exceeded` 候选。
- **`max_iterations_exceeded`：** 计量单位 = 一次 tick 内 **总 state transition**（`StateMachineSnapshot.turn_count`）。默认建议 **12**（plan/do/check/act × 含 1 replan + 余量；上线前标定）。与 F17 snapshot 字段天然对齐；**不是** LLM call 计数。
- F10 §9 SLO（p95 ≤ 30s 内网 / ≤ 60s 公网）为 **wall-time**，非逻辑 stop；F10 §6 deadline（aspirational，未实现）—— v1 `stop_evaluator` **不**含 wall-time；wall-time deadline 纳入需先落地 tick deadline 传递（Open Question Q4）。

---

## 10. Acceptance Criteria

> **B1 实现阶段划分：** 验收项按 P0-P5 六阶段组织。**P0-P4：evaluator 注册 + 单测覆盖，audit/trace-only（driver 不接线，保 byte-equivalence）**；**P5：driver 接线**（在 F18 check_point 调用 `PolicyEngine.evaluate` 并映射 `PolicyDecision → runtime.*`），需 golden trace 回归。每阶段有独立 byte-equiv 检查点，可独立合入。
>
> **G1-A 决策落地：** P5-A 已接线：driver 在三个 F18 check_point 调用 `PolicyEngine.evaluate` 并记录 `quality_decision` trace 行；`stop_evaluator` body 已实现 stagnation / max_iterations / max_consecutive（经 `enable_stop_dimensions` 门控，默认 off）；`detect_check_replan` 纯函数仍由 `_execute_check_state` 直接调用保 trace 顺序（P5-B 统一）；`final_success_evaluator` audit/trace-only（`_detect_tick_emit_deferral` 仍为 draft 权威）；`quality_score_evaluator` / `react_turn_success_evaluator` 注册并经各自 config 门控。剩余 P5-B 项：`detect_check_replan` 迁移、`final_success` 驱动、B4 loop 消费、`budget_exceeded`。

### P0 — F16 分域重构（纯重构，无行为变化）

- [x] 建 `policy/domain.py`（`Domain` 基类 + `DomainRegistry`）+ `policy/config.py`（`PolicyConfig` 加载 `backend/config/policy.yaml`）
- [x] 建 `policy/domains/{skill_domain.py,gate_domain.py}`，迁 `detectors.py` 既有 detector（保留顺序，N2）
- [x] 实现 `Domain.build_context`（D2，数据源 `base.extra['tick_state']`，N1）
- [x] `engine.py` `evaluate` 按 `check_point → domain` 派发，派发前调目标域 `build_context`
- [x] 删 `detectors.py`（不留 re-export shim，D3）
- [x] 新建 `backend/config/policy.yaml`（三域顶层键 `skill`/`gate`/`quality`）
- [x] **byte-equiv 检查点：** 既有 `tests/game_engine/policy/` + `test_execution_gate.py` 全绿；`test_domain_registry.py`/`test_build_context.py`/`test_detector_order.py` 通过

### P1 — stop_evaluator + 统一收归 check_retry/mandatory_gap

- [x] `stop_evaluator` 注册进 `QualityDomain`（audit/trace-only，body 为 stub 返回 allow）；**driver 接线 (P5)**
- [x] **B3 统一收归：** `check_retry`（`parse_check_retry_signal`）+ `mandatory_gap`（`mandatory_observation_gap`）检测迁入 `quality_domain.detect_check_replan` 纯函数（仅 `current_state=='check'`），由 `_execute_check_state` 直接调用保 byte-equiv trace 顺序；优先级 check_retry beats mandatory_gap；`_execute_check_state` 仅保留 LLM 调用 + 写 `check_out` + 调 `detect_check_replan` 应用结果
- [x] **B6-a：** stagnation 仅 plan/do/check 态发 `event=stagnation`，act 态抑制（P5-A 已落地，`enable_stop_dimensions` 门控）
- [x] **B6-b：** act 单次 `sm.next`（`_detect_tick_emit_deferral` 后 `after_state_execute` 仅设 flag，`before_terminal` 后单次 sm.next）
- [x] `budget_exceeded` 映射既有 `fail_fallback` 路径（v1 soft-fail 兼容）— **P5-B3 已落地**：`stop_evaluator` 经 `enable_stop_dimensions` 门控读取 `ToolGatherBudgets` tick-level caps（`commands_run`/`max_commands_per_tick`/`observation_chars`/`max_chars_observations_per_tick`），默认 soft-fail → `continue`（audit/trace-only，既有 draft-gate `fail_fallback` 路径保持权威）；opt-in hard-fail 经 `enable_budget_hard_fail` → `fail`（`*→fail on runtime.stop_fail`，Q1）
- [x] `max_iterations_exceeded` 读 `snapshot.turn_count`（总 state transition）；默认阈值可配置（P5-A 已落地，`enable_stop_dimensions` 门控）
- [x] `max_consecutive_tool_failures_exceeded`（R11）：连续 `ToolResult.ok=False` ≥ 3（@configurable）→ `fail`（P5-A 已落地，`enable_stop_dimensions` 门控）
- [x] **B7：** evaluator 异常 → log `evaluator_error` + 返回 `allow`（byte-equiv 保底）
- [x] **byte-equiv 检查点：** 默认 config 下 `test_llm_pdca_*`（含 `test_llm_pdca_mandatory_gap_*`、`test_llm_pdca_plan_cancel`、`test_llm_pdca_tick_cancel`）全绿；`test_llm_pdca_unified_replan.py`/`test_llm_pdca_act_single_sm_next.py`/`test_stop_evaluator_exception.py` 通过

### P2 — final_success_evaluator

- [x] `final_success_evaluator` 包装 `assess_draft_completeness`，外部 API 稳定；注册进 `QualityDomain`（audit/trace-only）；**driver 在 `_detect_tick_emit_deferral` 之后接线 (P5)**
- [x] 映射 `complete→final_success`/`retry_loop→replan`/`fail_fallback→fail`；`_draft_incomplete` 作为输入
- [x] **B7：** `assess_draft_completeness` 自身异常走既有 `fail_fallback`；外层异常 log + 降级既有结果
- [x] **byte-equiv 检查点：** `test_agent_loop.py` + `test_llm_pdca_*stream*` + draft gate 测试全绿

### P3 — quality_score_evaluator（default-off）

- [x] `quality_score_evaluator` v1 分层评分（surface / process / semantic），无 LLM 调用；`semantic` 维度含 `grounding_quality`（S2）+ `criteria_coverage`（S3）+ `progress`（S4）；**剔除** intent/router confidence（S1，降为 trace-only）；阈值 @configurable；默认 config 可关闭以保持等价
- [ ] `obs_grounded_claims` hard_gate（S2）default-off；`success_criteria_addressed`（S3）opt-in **(P5)**
- [x] `no_stagnation` / `current_strategy_not_progressing`（S4）操作化：连续 K=3 轮重复 tool/obs/deferral + **sliding window 2K 循环模式检测**（R6，已实现）→ `replan`（`event=stagnation`，P5-A）→ `fail`（超限，D2）**(P5)**
- [ ] `observation_relevance`（R7）信号预留于 `process` 维度，default-off
- [ ] Evaluator 性能预算（R8）预留 `eval_ms` 字段，v1 不实现 perf 测量
- [ ] 阈值标定工作流（R10）default off；shadow mode → 灰度 → 锁定
- [ ] LLM-as-judge **offline-only**（S6）；tick 热路径永不默认开启
- [x] `quality_decision`（或兼容 `policy_decision`）trace 行写入 `command_trace`，含 `check_point` / `quality_score`（多维子分，一等字段 G2） / `degraded_action`（一等字段 G2）
- [x] `attributes.success_checks` / `stop_policy` merge-if-missing seed；配置优先级见 §7
- [x] **byte-equiv 检查点：** 默认 config 行为不变；新 trace 行仅在显式开启时出现

### P4 — react_turn_success_evaluator + 结构化 Check（S5）

- [x] `react_turn_success_evaluator` 注册进 `QualityDomain`（audit/trace-only，evaluator 自我守卫 `react_turn is None`）；**opt-in driver 接线 (P5)**；消费 `success_criteria`；free-text 模式无 per-round 检查（R9 v1 限制）
- [x] **B4：(P5-B2)** 写 `ctx.payload['react_round_decision']`，内层 ReAct loop 消费（continue→继续；replan/fail→break + flag 传递 `after_state_execute`），不直接驱动 `sm.next`；`stop_evaluator` 二次确认（fail→`react_round_fail`→`stop_fail`；replan→`stagnation` event 复用 `*→plan`）；opt-in（`require_structured_turn=true`），默认 off 保 byte-equiv
- [x] **P1 升级（S5）：** 结构化 Check 输出（`PASS|RETRY|FAIL` + `reason_codes`）解析器 `parse_structured_check_output` 落地（替换子串启发式 `verification_passed`；legacy fallback 保留至 Check prompt 改造）
- [ ] `selected_skill_allowed` v1 inert；`required_citations_present` 不在 v1 hard_gates
- [x] **byte-equiv 检查点：** opt-in 不影响默认 free-text 路径

### P5 — driver 接线（evaluator 驱动控制流，需 golden trace 回归）

> **目标：** 把 P1-P4 注册的 evaluator 从 audit/trace-only 升级为控制流驱动。driver 在 F18 check_point 调用 `PolicyEngine.evaluate`，按 §4.4 映射表把 `PolicyDecision` 写入 `runtime.*` / event，由 `sm.next` 消费。

> **P5-A 落地范围（本次）：** driver 已在三个 F18 check_point 调用 `PolicyEngine.evaluate` 并记录 `quality_decision` trace 行（复用 `_policy_decision_to_trace`，D4）；新维度（stagnation / max_iterations / max_consecutive_tool_failures）经 config 开关 `enable_stop_dimensions` 默认 off，`final_success_evaluator` 经 `final_success_drive_mode`（off/shadow/enforce，D-B）默认 off，默认 config 下不产生 trace 行、不覆盖 event/runtime（byte-equivalent）。stop `fail` 经 `runtime.stop_fail` + F17 `*→fail` 任意态终止（D1）；stagnation 经 F17 `*→plan on_event=stagnation` replan / 超限 `*→fail`（D2）；`per_react_round` 写 `ctx.payload['react_round_decision']`（D3）。**P5-B1：** `detect_check_replan` 已从 `_execute_check_state` 内联迁移至 `stop_evaluator`（B3 统一收归），check_retry/mandatory_gap 现经 PolicyEngine 决策；`mandatory_gap_retry_override` trace 行移至 `check_entry` 之后。**P5-B2：** B4 内层 ReAct loop 消费已接线——replan/fail→break + flag 传递，`after_state_execute` 二次确认（fail→`stop_fail`；replan→`event=stagnation`），flag 消费后清空。**D-B Step1：** `final_success_drive_mode` 引入 `shadow`（audit + `final_success_divergence` 检测，deferral 仍权威）与 `enforce`（evaluator 驱动 `draft_incomplete`，deferral 降为 fallback；`retry_loop→replan` 待 D-I）；默认 `off` 保 byte-equiv。

- [x] `_execute_state`（非 act 态）后调 `PolicyEngine.evaluate(check_point='after_state_execute')`，映射 `stop_evaluator` 决策：`fail`（max_iterations / max_consecutive）→ `runtime.stop_fail`（F17 `*→fail` 任意态，D1）；`replan`（stagnation）→ `event=stagnation`（F17 `*→plan`，受 `replan_count < max_replans`，超限 → `stop_fail`，D2）；单次 `sm.next` 消费；`check_retry` / `mandatory_gap` / `budget_exceeded` 仍走既有内联路径（保 byte-equiv，P5-B 统一）
- [x] `_execute_act_state`：`_detect_tick_emit_deferral` 后 `after_state_execute` 仅设 flag（不调 `sm.next`），`before_terminal` 完成后单次 `sm.next` 消费合并 flag/event（B6-b）
- [x] `before_terminal` 调 `PolicyEngine.evaluate`，`final_success_evaluator` 决策记 `quality_decision` trace 行；驱动模式 `final_success_drive_mode`（D-B）：`off` byte-equiv / `shadow` audit + `final_success_divergence` 检测（deferral 仍权威）/ `enforce` 驱动 `draft_incomplete`（deferral 降为 fallback；`retry_loop→replan` 待 D-I）
- [x] `_phase_react_loop` 每轮调 `PolicyEngine.evaluate(check_point='per_react_round')`（仅 `require_structured_turn=true` 且 `react_turn` 非空），写 `ctx.payload['react_round_decision']`（D3）+ trace 行；**B4 内层 loop 消费已接线**（P5-B2）：replan/fail→break + flag 传递，`after_state_execute` 二次确认（fail→`stop_fail`；replan→`event=stagnation`）；flag 消费后清空避免跨态污染
- [x] `detect_check_replan` 调用从 `_execute_check_state` 内联迁移至 `stop_evaluator` 经 `PolicyEngine.evaluate` 路径触发（B3 统一收归，P5-B1）；`mandatory_gap_retry_override` trace 行随之移至 `check_entry` 之后（trace 顺序翻转，已确认 golden 测试不锁定该顺序）；driver 映射 `replan`(check_retry/mandatory_gap) → event + bag.retry_tools + trace 行，over-cap 由 `sm.next` 落到 act（保 byte-equiv）
- [x] 计数器采集前置：`max_consecutive_tool_failures` 计数器在 `after_tool_observation` 更新（`_update_tool_failure_counter`）；`recent_signatures`（obs 哈希 / tool 签名）sliding window 由 `_append_obs_signatures` 维护
- [x] **byte-equiv 检查点：** golden trace 回归（`test_llm_pdca_*` 全量 + `test_agent_loop.py` + streaming）确认接线后行为等价；新维度（stagnation / max_iterations / max_consecutive_failures）默认 off 时不改变 trace（`test_p5_quality_wiring.py` 锁定）

### 跨阶段

- [x] **B5：** `decision → runtime_action` 派生映射表落地；`llm_pdca._prepare_skill_context` trace 序列化复用 `execution_gate._policy_decision_to_trace`（修复硬编码 bug）；运行时消费者走 `is_block`/`is_allow`；F18 决策 factory（`fail`/`pause`/`final_success`/`replan`/`continue_`）内聚映射（G13）；`is_allow` 覆盖 `transform`（G10）
- [x] **可恢复 vs 不可恢复分类（R4）：** evaluator 映射已遵循（`retry_loop→replan`、`fail_fallback→fail`、criteria 未命中→`replan`）；driver 接线后由 `sm.next` 消费生效（P5）
- [x] `pause` v1 同步降级契约落地（`pause` factory + `degraded_action` 一等字段 G2 + trace 序列化）；evaluator 实际 emit `pause` 为 P5
- [x] **默认 config（无 success_checks/stop_policy 覆盖）行为与今日 byte-equivalent**（不破坏 streaming / `test_agent_loop.py` / golden trace；642 项 game_engine 测试全绿）
- [x] 单元测试位于 `backend/tests/game_engine/`

---

## 11. Open Questions

- **Q1（budget hard-fail vs soft-fail）：** v1 `budget_exceeded` 走 soft-fail；何时 opt-in hard-fail 终态？需 `stop_policy.fail.budget_exceeded` 显式声明。
- **Q2（quality_score 阈值标定）：** 默认 `semantic_gte` 0.75/0.85 可能阻断今日 `complete` 回复；标定需 offline eval rubric（见 §5.3）回归。
- **Q3（配置面合并）：** `agents.llm.extra` + `phase_llm` + `success_checks`/`stop_policy` 三面何时合并为单一 quality 配置？
- **Q4（wall-time deadline）：** F10 §6 tick deadline 未实现；`stop_evaluator.max_wall_time` 何时落地（需 deadline 传递）？
- **Q5（replan 统一）：** `stop_evaluator` 的 replan 信号与 [F17](F17_AGENT_STATE_MACHINE.md) 状态机 `replan` / Check `RETRY` / `agent_loop` draft retry 何时统一为 `max_replans` 计数器？
- **Q6（LLM-as-judge 边界）：** **已决策（S6）** — offline-only；tick 热路径永不默认开启。tick 内 opt-in 需标注延迟代价。何时引入 offline judge rubric harness（见 §5.3）？
- **Q7（`pause` 异步化）：** 跨 tick pause/resume 何时引入（与 [F16](F16_AGENT_POLICY_ENGINE.md) Q2 联动）？
- **Q8（显式 `runtime.stop_decision`）：** v1 用 driver 映射到既有 flag/event；何时升级为 PDCA 模板显式 `runtime.stop_decision` transition（可配置 workflow 可直接引用）？
- **Q9（quality gate bypass，R12a）：** v1 无 bypass 机制；何时引入 per-context 信任级别（admin / test / trusted session）bypass quality gate？需 context 信任级别传递。v1 缓解：default-off 保 byte-equivalent，CI 不受影响；提供 **config 开关** `success_checks.bypass`（v1 预留，default false）。
- **Q10（跨 tick quality 趋势，R12b）：** v1 评估单 tick 质量；跨 session 质量漂移检测何时引入（需 `quality_decision` trace 聚合 + dashboard）？v1 铺路：trace 行已含多维子分，外部可消费。

---

## 12. 后续

- [F16](F16_AGENT_POLICY_ENGINE.md) §3.1 CheckPoint 表补充 F18 点位（`after_state_execute` / `before_terminal` / `per_react_round`）。
- [F17](F17_AGENT_STATE_MACHINE.md) §7.1 注明 driver 在 stage 边界咨询 PolicyEngine；F18 决策经 runtime flag 消费，**不**新增控制流权威。
- [F10](F10_AICO_PERFORMANCE_AND_LATENCY.md) budget / 轮次上限标注为「`stop_evaluator` 的 `budget_exceeded` / `max_iterations_exceeded` 候选」。
- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §12.4 Check gate 标注为「`final_success_evaluator.verification_passed`」。
- `react_turn_success` hard_gates 依赖 [F17](F17_AGENT_STATE_MACHINE.md) `react_turn_schema`（opt-in）；`selected_skill_allowed` 依赖 [F15](F15_AGENT_SKILL_REGISTRY.md) + F17 D3-B/D6 消费。
