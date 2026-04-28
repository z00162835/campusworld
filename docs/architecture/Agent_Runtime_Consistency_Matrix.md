# Agent runtime consistency matrix (F09)

**Purpose:** Record a **layer-by-layer** audit of the repository against [**F09 — Agent four layers**](../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md): what the SPEC claims, where the code lives, and **status** relative to that claim.

**Scope:** `npc_agent` / `app/game_engine/agent_runtime/` and direct dependencies (commands, LTM services). This is an **implementation audit**, not a product roadmap.

**Status values**

| Value | Meaning |
|-------|---------|
| `implemented` | Behavior and boundaries match the F09 claim closely enough to treat as done. |
| `partial` | Core pieces exist; important aspects missing or only reachable outside the cited path. |
| `gap` | Claimed contract (often from F08) is **not** wired in the cited code path. |
| `spec_ahead` | SPEC describes capability (e.g. centralized rules) **ahead of** a single engine in code. |
| `n/a_product` | F09 already marks as **non-commitment** (e.g. L4 has no single directory). |

---

## 1. Verifiable claims extracted from F09 (checklist)

Use this as the **assertion list** the matrix rows map to.

**Global**

- G1: Four layers L1–L4 are defined with distinct responsibilities (§3).
- G2: **Perspective A** is dependency stack L1→L2→L3→L4; **Perspective B** is tick data flow (user → L3, with optional L4 / F07 / L2 observations) (§4).
- G3: F07 `memory_context` is **not** L4 (§4–§5).

**L1 — Type and data**

- L1.1: Graph model, NodeType, ontology seeds are the structural base (§6.1, §7).
- L1.2: “Ontology reasoning / commonsense rules” are **declarative**, testable, not ad-hoc LLM (§6.1).

**L2 — Command tools**

- L2.1: Command registry + authorization gate tool execution (§6.2).
- L2.2: `RegistryToolExecutor`, `ToolRouter`, `tool_allowlist` constrain which command names are tools (§6.2).
- L2.3: **`ToolObservation`** / ToolGather: tool output feeds the LLM context per **F08** (§5 table, §6.2, §7 L2 note).

**L3 — Thinking**

- L3.1: Pluggable frameworks; `LlmPDCAFramework` is a **reference** implementation, not the only shape of L3 (§6.3).
- L3.2: **Slow** path: PDCA + LLM; **fast** path: direct L2 tool use for rules/read-only (§6.3).
- L3.3: `worker.py` orchestrates framework + ports; `npc_agent_nlp.py` is the shared NLP tick entry (§7).

**L4 — Skill / experience**

- L4.1: Experience skills are **optional text** injected into ticks; may come from commands, node attrs, or packages — **no single module** required by F09 (§6.4, §7).

**F07 cross-cutting**

- F07.1: LTM / semantic retrieval and `build_ltm_memory_context_for_tick` feed **`memory_context`**, distinct naming from L4 (§5, §7).

**AICO (§8)**

- A1: Shared L2/L3 code should **not** hardcode `aico` except seed/YAML conventions.

---

## 2. Consistency matrix

| Layer | F09 capability / claim | Code anchor (evidence) | Status | Notes |
|-------|------------------------|-------------------------|--------|--------|
| L1 | Graph types and nodes | `backend/app/models/graph.py` | `implemented` | Core graph ORM / node model. |
| L1 | Ontology / NodeType seeds | `backend/db/ontology/` (`graph_seed_node_types.yaml`, `load.py`, …) | `implemented` | Seeds and loaders present. |
| L1 | Centralized ontology rule engine (commonsense / derivation) | (dispersed: commands, policy evaluators, validators) | `spec_ahead` | No single “rules engine” module; F09 §6.1 allows declarative **tests** without mandating one service. |
| L2 | Register and authorize commands | `backend/app/commands/registry.py` (`get_available_commands`, `authorize_command`) | `implemented` | Policy-backed `CommandPolicyEvaluator`. |
| L2 | Tool executor + allowlist intersection | `backend/app/game_engine/agent_runtime/tooling.py` (`RegistryToolExecutor`, `ToolRouter`); node attr `tool_allowlist`; `backend/app/commands/agent_commands.py` (`agent_tools`) | `implemented` | Listing uses `get_available_commands` then `ToolRouter.filter`; execute path uses `authorize_command` + `execute`. |
| L2 | Unified invoke gateway (aligned with SSH/HTTP) | `backend/app/commands/invoke.py` (`invoke_command_line`) | `implemented` | Same parse → registry → policy → execute pattern as described in module docstring. |
| L2 | ToolGather / `ToolObservation` in LLM prompt | `backend/app/game_engine/agent_runtime/tool_gather.py`; `llm_pdca.py` + `resolved_tool_surface.py` | `implemented` | Parsed JSON `llm_tool_plan`, `PreauthorizedToolExecutor`, observations injected into subsequent phase prompts; caps via `ToolGatherBudgets`. |
| L3 | LLM + PDCA framework | `backend/app/game_engine/agent_runtime/frameworks/llm_pdca.py` (`LlmPDCAFramework`) | `partial` | Tool path wired; full **Pre→Post** phase handler split and **PhaseInnerLoop** multi-round are incremental (see ADR-F08). |
| L3 | Non-LLM PDCA framework | `backend/app/game_engine/agent_runtime/frameworks/pdca.py` (`PDCAFramework`) | `partial` | Runs phases and writes trace; **does not** call `self._tools` (placeholder `graph.patch_device_state` in trace only). |
| L3 | Worker binds memory + framework + tools | `backend/app/game_engine/agent_runtime/worker.py` (`LlmPdcaAssistantWorker`, `AgentWorker.tick`) | `implemented` | Builds `ResolvedToolSurface` / `PreauthorizedToolExecutor` and passes into `LlmPDCAFramework`. |
| L3 | NLP tick entry | `backend/app/commands/npc_agent_nlp.py` (`run_npc_agent_nlp_tick`) | `implemented` | Resolves config, optional passthrough without HTTP LLM, builds worker, passes `memory_context`. |
| L3 | “Fast thinking” via L2 without full LLM loop | (no dedicated abstraction) | `partial` | Read-only / command paths exist globally; not framed as a separate L3 “fast” mode in `agent_runtime`. |
| L4 | Dedicated Skill package or runtime module | — | `n/a_product` | F09 §7: no single directory; acceptable **progressive** posture. |
| L4 | Skill-like behavior via commands + allowlist | `agent_commands`, `tool_allowlist` on nodes | `partial` | Matches “command as skill surface” without a named L4 layer in code. |
| F07 | `memory_context` from LTM | `backend/app/services/ltm_semantic_retrieval.py` (`build_ltm_memory_context_for_tick`); `npc_agent_nlp.maybe_ltm_memory_context` | `implemented` | Gated by `extra.enable_ltm` in YAML; **distinct** from any L4 naming. |
| AICO | Avoid `aico` in shared logic | See §3 below | `partial` | Defaults and dispatch still reference `"aico"` in several modules; seeds/YAML are explicitly allowed. |

---

## 3. AICO: allowlist vs coupling

**Allowed / conventional (F09 §8)**

- **Seed / graph:** `backend/db/seed_data.py` (`ensure_aico_npc_agent`, `service_id: "aico"`, tags).
- **Config:** `agents.llm.by_service_id` materialization for `aico` in `backend/app/game_engine/agent_runtime/agent_llm_config.py` (YAML-driven defaults).
- **User-facing default command:** `backend/app/commands/agent_commands.py` registers the default assistant command named `aico` (product entry point).

**Coupling to review (not automatically forbidden, but counts as “partial” vs A1)**

- **`service_id` default:** `str(attrs.get("service_id") or "aico")` in `npc_agent_nlp.py`, `worker.py` — fallback when attribute missing.
- **`@` dispatch:** `at_agent_dispatch.py` uses `command_registry.get_command("aico")` only to **align authorization** with the `aico` command before resolving the target handle; behavior is generic after that.
- **Resolve by handle:** `agent_commands` resolves the default assistant via handle `"aico"` for the dedicated command class.

**Recommendation:** Treat new **non-default** agents without adding more string literals; prefer `service_id` from the resolved node and shared helpers (already present in `resolve_agent_llm_config_for_npc_tick`).

---

## 4. Follow-ups (post–ToolGather)

1. **PDCAFramework** (`pdca.py`) still does not execute `ToolExecutor`; non-LLM path remains placeholder-first.
2. **L4 productization:** When a first-class Skill module appears, add a row and anchors here; until then **`n/a_product`** stands.
3. **Phase pipeline:** Optional split of **Pre→Post** into dedicated `PhaseHandler` modules and **PhaseInnerLoop** multi-round policies (see ADR-F08).

---

## 5. Related documents

- [**F09**](../models/SPEC/features/F09_CAMPUSWORLD_AGENT_ARCHITECTURE_FOUR_LAYERS.md) — normative layering.
- [**F08**](../models/SPEC/features/F08_AICO_TOOL_CONTEXT_AND_AGENT_LOOP.md) — ToolGather and tool context contracts.
- [**F07**](../models/SPEC/features/F07_PER_USER_AGENT_MEMORY_AND_ASYNC_LTM_PROMOTION.md) — LTM and `memory_context`.
