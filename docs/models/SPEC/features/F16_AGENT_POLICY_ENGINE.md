# F16 — Agent Policy Engine（确定性策略引擎）

> **Architecture Role：** 将 Agent 运行时的 **行为安全策略** 从 system_prompt 文本指令迁移到 **确定性引擎**，实现零 Prompt 依赖、check_point 拦截、单一事实来源。收敛既有 `execution_gate` 为 `before_tool_call` 适配器（外部 API 不变）。与 `command_policies`（授权平面）**并存不合并**。

**文档状态：Draft（契约先行；实现按本 SPEC 逐阶段优化）。**

**交叉引用：** [**F08**](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md)（`execution_gate`、`CommandToolSemantics` Tool Profile、`PreauthorizedToolExecutor`）、[**F09**](F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md)（L2/L4 边界）、[**F11**](F11_AGENT_INTENT_CLASSIFIER_RUNTIME.md)（意图分类，与 `before_tool_call` 同向）、[**F14**](F14_AGENT_TOOL_ROUTER_PREPLAN.md)（execution_gate 仍负责最终允许）、[**F15**](F15_AGENT_SKILL_REGISTRY.md)（`before_skill_activation`）、[**F18**](F18_AGENT_QUALITY_GATES.md)（`pause`/`require_approval` 停止决策）。

---

## 1. Goal

- 把 `CAMPUSWORLD_SYSTEM_PRIMER.md` §8–§9 与 `settings.yaml` AICO `system_prompt`/`phase_prompts` 中的 **行为安全规则文本** 迁移到确定性引擎，消除「Prompt 注入依赖」。
- 提供 4 个 check_point 的统一拦截：`before_skill_activation` / `before_tool_call` / `after_tool_observation` / `before_final_answer`。
- 收敛 `execution_gate.py` 为 PolicyEngine 的 `before_tool_call` 适配器，**保持外部 API 与 `GateDecision` 结构稳定**，避免破坏 `PreauthorizedToolExecutor` 与现有测试。

## 2. Scope / Non-Goals

- **Scope：** `npc_agent`（含 AICO）agent tick 内的行为策略；`before_tool_call` / `after_tool_observation` / `before_final_answer` 三个今日可落地的 check_point；`before_skill_activation`（依赖 [F15](F15_AGENT_SKILL_REGISTRY.md)）。
- **Non-Goals：**
  - **不**替代 `command_policies`（权限/角色授权平面，`policy.py` / `command_policies` 表）。PolicyEngine 是 **行为平面**（意图/确认/副作用/数据分级），两平面并存（见 §6）。
  - **不**替代 F11 意图分类器；F11 产出 `intent_hint` 软提示，PolicyEngine 在 check_point 做最终拦截。
  - v1 **不**实现跨 tick 异步 `pause`/`resume` 审批工作流（tick 同步不变量，见 §8 / Open Question Q2）。
  - **不**改变 `ResolvedToolSurface` 冻结面构造（F08 §5.1）。

---

## 3. 核心定义

### 3.1 CheckPoint（`check_points.py`）

| CheckPoint | 触发时机 | 今日可落地 | 依赖 |
|------------|---------|-----------|------|
| `before_skill_activation` | Skill 激活前（`SkillInjection.select` 后） | ❌ 否 | [F15](F15_AGENT_SKILL_REGISTRY.md) |
| `before_tool_call` | 单次工具执行前 | ✅ 是 | — |
| `after_tool_observation` | ToolObservation 生成后、注入后续 LLM 前 | ✅ 是 | — |
| `before_final_answer` | 最终答复发出前 | ⚠️ 部分 | streaming 锚点见 §7 |

### 3.2 PolicyDecision（`decisions.py`）

```python
@dataclass(frozen=True)
class PolicyDecision:
    decision: Literal['deny', 'allow', 'require_approval', 'allow_with_transform']
    reason_code: str
    check_point: str
    runtime_action: Literal['block', 'pause', 'transform', 'block_and_rewrite', 'pass']
    transform_applied: Optional[Dict[str, Any]] = None
    evidence: Optional[Dict[str, Any]] = None  # 命中的 detector / 规则 id
```

### 3.3 Detectors（`detectors.py`）

纯函数检测器，读 `resolve_command_tool_semantics` 返回的 [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §1.3 字段 + tick 上下文，**不**读第二个元数据源：

| Detector | 输入 | 用途 |
|----------|------|------|
| `action_type_match` | `interaction_profile` / `side_effect_level` | 校验提议动作类型与 caller ceiling |
| `side_effect_level` | `side_effect_level` | `write_high` → `require_approval` |
| `data_classification` | `data_classification` | `confidential`/`restricted` 触发 `allow_with_transform`（脱敏） |
| `pattern_match` | `user_message` / `args` | Prompt 注入模式 / 越权短语 |
| `pii_scanner` | `ToolObservation` / `final_answer` | v1 规则模式；PII 模式扫描 |

---

## 4. 与 `execution_gate` 的收敛（适配器契约）

### 4.1 既有 `execution_gate` 现状（`execution_gate.py`）

- `evaluate_execution_gate(*, db_session, command_name, args, context_metadata) -> GateDecision`（`92:112`）。
- 返回 `GateDecision{allow, reason_code, intent, effective_profile, effective_guard, caller_profile, callee_profile}`（`12:20`）。
- `reason_code`：`guard_pass` / `guard_blocked_profile_ceiling` / `guard_blocked_intent` / `guard_blocked_scope` / `guard_blocked_confirmation`。
- 读 `CommandToolSemantics` 的 `interaction_profile` + `invocation_guard`（`69:75`），**未读** `side_effect_level` / `data_classification`。
- 调用方：`PreauthorizedToolExecutor.execute_command`（`resolved_tool_surface.py:84`）；trace 在 `tool_gather.py:226-233`。

### 4.2 收敛契约

- `evaluate_execution_gate` 外部签名 + `GateDecision` 字段 + `reason_code` 字符串集 **保持稳定**（适配器，非重写）。
- 内部委托 `PolicyEngine.evaluate(check_point='before_tool_call', ...)`，映射结果到 `GateDecision`。
- 新增读 `side_effect_level` / `data_classification`（经 `resolve_command_tool_semantics`），用于 `side_effect_level` / `data_classification` detector。
- **保持** `PreauthorizedToolExecutor` 在 `before_tool_call` 内调用（F08 R2：构造面时鉴权等价、tick 内不重复 `authorize_command`）。
- trace：`guard_pass` / `guard_block`（`reason_code` 前缀 `guard_blocked_`）保持；新增 `policy_decision` trace 行（见 §9）。

---

## 5. 规则来源与加载

### 5.1 平台默认（`settings.yaml` 新增 `policy.platform_defaults`）

由 [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §1.3 `side_effect_level` 自动推导：

| `side_effect_level` | 默认 decision |
|---------------------|--------------|
| `none` / `read` | `allow` |
| `write_low` | `allow`（caller `require_confirmation_for_mutate` 仍生效） |
| `write_high` | `require_approval` |

`policy.platform_defaults` 位于 `backend/config/settings.yaml` 顶层 `policy:` block（与 `commands:` 并列；当前 **不存在**，需新增 `PolicyConfig` 于 `settings.py`）。

### 5.2 实例规则（图节点 `nodes.attributes.safety.rules`）

```yaml
safety:
  schema_version: "1.0.0"
  rules:
    - id: no_permission_change
      who: any
      what: modify_permission
      decision: approve
    - id: sensitive_data_mask
      who: any
      what: read
      on: sensitive_data
      decision: allow
      transform: desensitize
```

`rules_loader.py` 合并顺序：平台默认（基线）→ 实例 `safety.rules`（覆盖/追加）。规则为内存加载的纯函数求值，check_point 仅在 4 个点位插入（性能：纯函数，无 DB / 无 LLM）。

---

## 6. 两平面边界（不变量）

| 平面 | 职责 | 载体 | 时机 |
|------|------|------|------|
| **授权平面** `command_policies` | 权限/角色能否调用该命令 | `command_policies` 表 + `policy.py` | `authorize_command`（构造冻结面时等价） |
| **行为平面** PolicyEngine | 意图/确认/副作用/数据分级/PII | `policy/` + `safety.rules` + 平台默认 | check_point（tick 内） |

**不合并**：授权是「**能否调**」，行为是「**这次该不该放行/变形**」。PolicyEngine **不**写 `command_policies`，`command_policies` **不**做行为判定。

---

## 7. check_point 在 `llm_pdca.py` 的插入点

| CheckPoint | 插入位置（`llm_pdca.py`） | 备注 |
|------------|-------------------------|------|
| `before_tool_call` | `_phase_react_loop` 工具 gather 前（`609:641`，`gather_tool_observations` 前） | 今日 `PreauthorizedToolExecutor` 内已有 gate，适配器收敛 |
| `after_tool_observation` | `build_round_tool_results` 后（`641:666`） | 观测 shaping / `data_classification` 脱敏 |
| `before_final_answer` | Act 阶段（`889:912`）`final_text` 赋值后 | ⚠️ streaming：Do 末轮 prose 可能先达用户（`_call_llm_dual_track` `436:463`），v1 在 Act 锚点拦截非流式路径；流式 `before_final_answer` 为 Open Question Q1 |
| `before_skill_activation` | `SkillInjection.select` 后 | 依赖 [F15](F15_AGENT_SKILL_REGISTRY.md) |

`_phase_react_loop` 被 Plan（`754`）/ Do（`780`/`869`）/ Check-retry Plan（`854`）调用，check_point 在所有 react 入口生效。

---

## 8. `require_approval` 与 `pause` 语义（v1 同步）

- **今日 tick 同步端到端**（`npc_agent_nlp.py:54-173` blocking）；无 `pause`/`resume`/`pending_approval` 机制。
- v1 `require_approval` decision → **同步降级为 block**：`CommandResult.error_result(reason_code='guard_blocked_confirmation')` + 失败 ToolObservation（既有路径，`resolved_tool_surface.py:85-86` / `tool_gather.py:210-233`）。
- **跨 tick 异步 pause/resume 审批工作流延后**（需 WS `awaiting_approval` 事件 + 持久化 hook，今日不存在）。`StopPolicy.pause`（[F18](F18_AGENT_QUALITY_GATES.md)）在 v1 同样降级为同步 fail/notice。
- **确认信号**：今日 `_is_confirmed` 读 `user_message` 子串 + `confirmed_execute` metadata（`execution_gate.py:60-67`）；生产无 `confirmed_execute` producer。v1 保持子串确认；结构化确认令牌延后（Open Question Q3）。

---

## 9. 可观测性

- 新增 trace 行 `policy_decision`（写入 `command_trace`，F10 审计）：`{step: 'policy_decision', check_point, decision, reason_code, detector, evidence}`。
- 既有 `guard_pass` / `guard_block`（`tool_gather.py:230-233`）保持兼容；eval adapter（`eval/adapters/aico.py`）映射不变。
- 标准化 `TraceEvent.POLICY_DECISION` 由 [F10/F05 可观测性] 标准化阶段统一（本 SPEC 仅定义 trace 行 schema）。

---

## 10. system_prompt 安全文本迁移

迁移目标（**迁移后从 prompt 移除**，由确定性引擎承接）：

| 来源 | 内容 | 承接 detector |
|------|------|--------------|
| `CAMPUSWORLD_SYSTEM_PRIMER.md` §8 Invariants | 角色不变量、世界状态必须基于工具观测 | `pattern_match`（越权短语）+ `after_tool_observation`（grounding 校验交 F18） |
| `CAMPUSWORLD_SYSTEM_PRIMER.md` §9 Commands | 意图路由（informational → `help`；execute 需显式意图） | `action_type_match` + `pattern_match` |
| `settings.yaml` AICO `system_prompt` (`255:259`) | informational / 确认规则 | 同上 |
| `settings.yaml` AICO `phase_prompts.plan` (`263:271`) | intent 分类 / 确认信号 | 同上 |
| `settings.yaml` AICO `phase_prompts.check` (`302:308`) | informational→execution 升级 fail | `before_final_answer` |

**保留**：`CAMPUSWORLD_SYSTEM_PRIMER.md` 中 **不变量陈述**（角色边界、不泄漏 phase tag）作为 LLM 行为指引，**移除具体规则条文**。

⚠️ **迁移风险：** 今日存在三处意图执行（prompt §9、F11 classifier `llm_pdca.py:712-718`、execution_gate regex `44:58`）。移除 prompt 规则后，行为依赖 F11 + PolicyEngine；需 golden trace 对比验证 AICO 工具选择行为等价（Open Question Q4）。

---

## 11. Acceptance Criteria

- [ ] `PolicyEngine.evaluate(check_point, context) -> PolicyDecision` 纯函数，无 LLM 调用
- [ ] `evaluate_execution_gate` 外部 API + `GateDecision` + `reason_code` 集稳定，内部委托 PolicyEngine
- [ ] `before_tool_call` 读 `side_effect_level`：`write_high` → `require_approval`（v1 同步降级 block）
- [ ] `data_classification` `confidential`/`restricted` → `allow_with_transform`（脱敏）
- [ ] Prompt 注入模式被 `before_tool_call` / `before_final_answer` `pattern_match` 拦截
- [ ] `settings.yaml` 新增 `policy.platform_defaults`；`settings.py` 新增 `PolicyConfig`
- [ ] `policy_decision` trace 行写入 `command_trace`
- [ ] `system_prompt` 安全规则文本段移除，AICO golden trace 行为等价
- [ ] `command_policies` 授权平面不被 PolicyEngine 写入/替代
- [ ] 单元测试位于 `backend/tests/game_engine/`

---

## 12. Open Questions

- **Q1（streaming `before_final_answer`）：** Do 末轮流式 prose 先达用户，Act 锚点拦截滞后；是否引入流式 pre-flush policy gate？延后到流式体验迭代。
- **Q2（异步审批）：** v1 同步降级；跨 tick pause/resume 何时引入（需 WS 事件 + 持久化）？
- **Q3（确认令牌）：** v1 子串确认；结构化 `confirmed_execute` 令牌何时由 UI/会话层产出？
- **Q4（迁移等价性）：** 移除 prompt 安全文本后，如何 golden trace 验证 AICO 工具选择不退化？需回归测试集。
- **Q5（PII detector 强度）：** v1 规则模式；是否引入扫描库（如 regex PII / 第三方）？
- **Q6（`before_skill_activation`）：** 随 [F15](F15_AGENT_SKILL_REGISTRY.md) 落地后补；v1 `SkillActivation.allowed_tool_groups` 违规记警告，强制阻断延后。

---

## 13. 后续

- [F08](F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) §execution_gate 标注为「PolicyEngine `before_tool_call` 适配器」。
- [F14](F14_AGENT_TOOL_ROUTER_PREPLAN.md) §「execution_gate 仍负责最终是否允许执行」保持，补充「= PolicyEngine 适配器」。
- `pause` 停止决策与 [F18](F18_AGENT_QUALITY_GATES.md) `StopPolicy.pause` 联动（v1 同步降级）。
