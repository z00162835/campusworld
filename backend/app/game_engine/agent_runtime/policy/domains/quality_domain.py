"""Quality domain quality/stop evaluators.

Owns the ``after_state_execute`` / ``before_terminal`` / ``per_react_round``
check_points. ``stop_evaluator`` carries two families: the legacy
``check_retry`` / ``mandatory_gap`` detection (routed through
PolicyEngine) and new dimensions (stagnation, max_iterations,
max_consecutive_tool_failures, gated by ``enable_stop_dimensions``).

The detection logic lives here (统一收归); ``stop_evaluator`` calls
:func:`detect_check_replan` for the check state and emits formal
``PolicyDecision.replan`` signals consumed by the driver.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.game_engine.agent_runtime.policy.config import QualityDomainConfig
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.domain import Domain, Evaluator
from app.game_engine.agent_runtime.agent_loop.draft_gate import (
    assess_draft_completeness as assess_final_draft_completeness,
)
from app.game_engine.agent_runtime.agent_loop.draft_gate import (
    _needs_runtime_grounding as _draft_needs_runtime_grounding,
)

logger = logging.getLogger("campusworld.policy.quality")

_CHECK_RETRY_RE = re.compile(
    r"RETRY\s*:\s*need_tools\s*=\s*([A-Za-z0-9_.\-]+(?:\s*,\s*[A-Za-z0-9_.\-]+)*)",
    flags=re.IGNORECASE,
)


def parse_check_retry_signal(text: str) -> Optional[List[str]]:
    """Return the list of requested tool names from a ``RETRY: need_tools=...`` line.

    Returns ``None`` when no RETRY marker is found. The list may be empty
    when the Check phase asks for a retry without nominating tools.
    """
    if not text:
        return None
    m = _CHECK_RETRY_RE.search(text)
    if not m:
        return None
    raw = m.group(1) or ""
    tools = [t.strip() for t in raw.split(",") if t.strip()]
    return tools


def detect_check_replan(
    *,
    check_out: str,
    check_skipped: bool,
    tool_router_snapshot: Optional[Dict[str, Any]],
    accumulated_tick_tool_results: List[Any],
    plan_trace: List[Dict[str, Any]],
) -> Tuple[Optional[str], Optional[List[str]], Optional[Dict[str, Any]]]:
    """Unified check-replan detection: check_retry beats mandatory_gap.

    Returns ``(event, retry_tools, gap_detail)``:
    - ``('check_retry', tools, None)`` when Check LLM output has a RETRY marker.
    - ``('mandatory_gap', tools, gap_detail)`` when mandatory tools have a gap.
    - ``(None, None, None)`` when no replan is needed.

    Pure function; no side effects. Called by ``_execute_check_state`` to
    preserve byte-equivalent trace ordering (the caller applies the side
    effects: ``mandatory_gap_retry_override`` trace row, ``bag`` mutation).
    """
    retry_tools = None if check_skipped else parse_check_retry_signal(check_out or "")
    if retry_tools is not None:
        return ("check_retry", retry_tools, None)

    if isinstance(tool_router_snapshot, dict):
        mans_retry = [
            str(x).strip()
            for x in (tool_router_snapshot.get("mandatory_tool_names") or [])
            if str(x).strip()
        ]
        if mans_retry:
            from app.game_engine.agent_runtime.tool_router.mandatory_gap import (
                mandatory_observation_gap,
            )

            (has_gap_retry, gap_retry_detail) = mandatory_observation_gap(
                mans_retry, accumulated_tick_tool_results, plan_trace=plan_trace,
            )
            if has_gap_retry:
                retry_tools = sorted(
                    set(
                        [
                            str(x).strip()
                            for x in (gap_retry_detail.get("missing") or [])
                            if str(x).strip()
                        ]
                        + [
                            str(x).strip()
                            for x in (gap_retry_detail.get("failed") or [])
                            if str(x).strip()
                        ]
                    )
                )
                return ("mandatory_gap", retry_tools, gap_retry_detail)

    return (None, None, None)


def stop_evaluator(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """v1 stop_evaluator for the ``after_state_execute`` check_point.

    Carries two families of stop signals:
    - **Legacy ``check_retry`` / ``mandatory_gap``** (always on, check state only):
      routed through PolicyEngine via :func:`detect_check_replan`. The driver
      maps the returned ``replan`` decision to ``event=check_retry`` /
      ``mandatory_gap`` and applies the bag/trace side-effects.
    - **New dimensions** (stagnation / max_iterations / max_consecutive_tool_failures
      / budget_exceeded): gated by ``tick_state['enable_stop_dimensions']``
      (default off → byte-equiv).

    ``budget_exceeded`` surfaces ``ToolGatherBudgets``
    exhaustion (commands / observation chars) as a formal decision. v1 default
    is **soft-fail** → ``continue`` (audit/trace-only; the existing draft-gate
    ``fail_fallback`` path clears the draft + ``_draft_incomplete`` → ``act→fail``
    remains authoritative). Opt-in **hard-fail** (``enable_budget_hard_fail``)
    emits ``fail`` so ``*→fail on runtime.stop_fail`` aborts immediately.

    Precedence: max_iterations / max_consecutive / budget hard-fail (fail) →
    check_retry / mandatory_gap (replan) → react_round_decision (fail/replan)
    → stagnation (replan) → budget soft-fail (continue, audit). Returns ``None``
    (no opinion) when nothing fires.
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.AFTER_STATE_EXECUTE:
        return None
    tick_state = ctx.extra.get("tick_state") if ctx.extra else None
    if not isinstance(tick_state, dict):
        return None
    current_state = tick_state.get("current_state")

    enable_stop_dims = bool(tick_state.get("enable_stop_dimensions"))
    budget_exceeded = False
    if enable_stop_dims:
        turn_count = int(tick_state.get("turn_count", 0))
        max_iterations = int(tick_state.get("max_iterations", 12))
        tool_failure_count = int(tick_state.get("consecutive_tool_failures", 0))
        max_consecutive = int(tick_state.get("max_consecutive_tool_failures", 3))
        # max_iterations_exceeded (total state transitions per tick).
        if max_iterations > 0 and turn_count >= max_iterations:
            return PolicyDecision.fail(
                CheckPoint.AFTER_STATE_EXECUTE,
                "max_iterations_exceeded",
                evidence={"turn_count": turn_count, "max_iterations": max_iterations},
            )
        # max_consecutive_tool_failures_exceeded.
        if max_consecutive > 0 and tool_failure_count >= max_consecutive:
            return PolicyDecision.fail(
                CheckPoint.AFTER_STATE_EXECUTE,
                "max_consecutive_tool_failures_exceeded",
                evidence={"consecutive_tool_failures": tool_failure_count, "threshold": max_consecutive},
            )
        # Tick-level budget exhaustion surfaced via tick_state by the driver.
        commands_run = int(tick_state.get("commands_run", 0))
        max_commands = int(tick_state.get("max_commands_per_tick", 0))
        obs_chars = int(tick_state.get("observation_chars", 0))
        max_obs_chars = int(tick_state.get("max_chars_observations_per_tick", 0))
        budget_exceeded = (
            (max_commands > 0 and commands_run >= max_commands)
            or (max_obs_chars > 0 and obs_chars >= max_obs_chars)
        )
        # Opt-in hard-fail terminal: abort immediately from any state.
        if budget_exceeded and bool(tick_state.get("enable_budget_hard_fail")):
            return PolicyDecision.fail(
                CheckPoint.AFTER_STATE_EXECUTE,
                "budget_exceeded",
                evidence={
                    "commands_run": commands_run,
                    "max_commands_per_tick": max_commands,
                    "observation_chars": obs_chars,
                    "max_chars_observations_per_tick": max_obs_chars,
                    "mode": "hard_fail",
                },
            )

    # Legacy check_retry / mandatory_gap detection (check state only,
    # always on). The driver applies side-effects (bag.retry_tools, trace rows).
    if current_state == "check":
        event, retry_tools, gap_detail = detect_check_replan(
            check_out=tick_state.get("check_out") or "",
            check_skipped=bool(tick_state.get("check_skipped")),
            tool_router_snapshot=tick_state.get("tool_router_snapshot"),
            accumulated_tick_tool_results=tick_state.get("tool_results") or [],
            plan_trace=tick_state.get("plan_trace") or [],
        )
        if event == "check_retry":
            return PolicyDecision.replan(
                CheckPoint.AFTER_STATE_EXECUTE,
                "check_retry",
                evidence={"retry_tools": retry_tools, "detector": "detect_check_replan"},
            )
        if event == "mandatory_gap":
            return PolicyDecision.replan(
                CheckPoint.AFTER_STATE_EXECUTE,
                "mandatory_gap",
                evidence={
                    "retry_tools": retry_tools,
                    "gap_detail": gap_detail,
                    "detector": "detect_check_replan",
                },
            )

    # Per-ReAct-round secondary confirmation. A react_round `fail`
    # routes to stop_fail (any state); a `replan` reuses the stagnation event
    # (*→plan, replan-cap guarded) — per_react_round does not drive sm.next
    # directly. Opt-in (react_turn present); None under default config.
    rr = tick_state.get("react_round_decision")
    if isinstance(rr, dict):
        rr_dec = rr.get("decision")
        if rr_dec == "fail":
            return PolicyDecision.fail(
                CheckPoint.AFTER_STATE_EXECUTE,
                "react_round_fail",
                evidence={"react_round_decision": rr, "detector": "react_turn_success_evaluator"},
            )
        if rr_dec == "replan":
            return PolicyDecision.replan(
                CheckPoint.AFTER_STATE_EXECUTE,
                "stagnation",
                evidence={"react_round_decision": rr, "detector": "react_turn_success_evaluator"},
            )

    # Stagnation applies only to plan/do/check; act is suppressed.
    if enable_stop_dims and current_state in ("plan", "do", "check"):
        recent_signatures = tick_state.get("recent_signatures") or []
        stagnation_window = int(tick_state.get("stagnation_window", 3))
        # H7: cycle-window multiplier is @configurable (cycle window =
        # multiplier × stagnation_window). Read from tick_state so the
        # control-flow-driving consumer honors config.
        cycle_mult = int(tick_state.get("stagnation_cycle_window_multiplier", 2))
        if _progress(
            stagnation_window, list(recent_signatures),
            cycle_window_multiplier=cycle_mult,
        ) == 0.0:
            return PolicyDecision.replan(
                CheckPoint.AFTER_STATE_EXECUTE,
                "stagnation",
                evidence={
                    "stagnation_window": stagnation_window,
                    "stagnation_cycle_window_multiplier": cycle_mult,
                    "recent_signatures": list(recent_signatures[-(cycle_mult * stagnation_window):]),
                },
            )
    # budget_exceeded soft-fail: audit/trace-only ``continue``. The
    # existing draft-gate ``fail_fallback`` path (clear draft + _draft_incomplete
    # → act→fail) remains authoritative for the soft-fail outcome; this only
    # surfaces the condition as a formal decision for provenance / future
    # hard-fail opt-in. Lowest precedence — fires only when nothing else did.
    if enable_stop_dims and budget_exceeded and not tick_state.get("enable_budget_hard_fail"):
        return PolicyDecision.continue_(
            CheckPoint.AFTER_STATE_EXECUTE,
            reason_code="budget_exceeded",
            evidence={
                "commands_run": int(tick_state.get("commands_run", 0)),
                "max_commands_per_tick": int(tick_state.get("max_commands_per_tick", 0)),
                "observation_chars": int(tick_state.get("observation_chars", 0)),
                "max_chars_observations_per_tick": int(tick_state.get("max_chars_observations_per_tick", 0)),
                "mode": "soft_fail",
            },
        )
    return None


def final_success_evaluator(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """v1 final_success_evaluator for the ``before_terminal`` check_point.

    Wraps the existing ``assess_draft_completeness`` hard_gates and maps the
    verdict to a PolicyDecision:

    - ``complete``      → ``final_success`` (pass)
    - ``retry_loop``    → ``replan`` (recoverable)
    - ``fail_fallback`` → ``fail`` (unrecoverable)

    Driving is governed by ``tick_state['final_success_drive_mode']``:
    - ``"off"``     → return ``None`` (byte-equiv; no trace row).
    - ``"shadow"`` → compute verdict + return decision (audit/trace-only; the
      driver records a ``quality_decision`` row + a ``final_success_divergence``
      row when the verdict disagrees with ``_detect_tick_emit_deferral``).
      ``_detect_tick_emit_deferral`` remains the authoritative source.
    - ``"enforce"`` → compute verdict + return decision; the driver lets the
      verdict drive control flow. Recoverable drafts request an outer replan;
      the driver owns transition capability and budget checks.

    Exceptions are re-raised to the policy engine safety net; the driver then
    retains the existing deferral verdict rather than applying a partial result.
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TERMINAL:
        return None
    tick_state = ctx.extra.get("tick_state") if ctx.extra else None
    if not isinstance(tick_state, dict):
        return None
    drive_mode = str(tick_state.get("final_success_drive_mode") or "off").strip().lower()
    if drive_mode not in ("shadow", "enforce"):
        # "off" / missing → byte-equiv (no opinion, no trace row).
        return None
    draft_text = tick_state.get("draft_text") or ""
    user_message = tick_state.get("user_message") or ""
    tool_results = tick_state.get("tool_results") or []
    config = tick_state.get("agent_loop_config")
    reason_context = tick_state.get("reason_context")
    draft_incomplete = bool(tick_state.get("draft_incomplete"))
    if config is None:
        return None
    from app.game_engine.agent_runtime.agent_loop.signals import (
        DraftCompletenessVerdict,
    )

    try:
        verdict = assess_final_draft_completeness(
            user_message=user_message,
            draft_text=draft_text,
            tool_results=tool_results,
            config=config,
            reason_context=reason_context,
        )
    except Exception:
        # Let the policy engine safety net preserve the existing deferral result.
        raise

    if verdict == DraftCompletenessVerdict.complete:
        # S2 obs_grounded_claims hard_gate (default-off): when runtime grounding is
        # needed and the draft's token overlap with successful observations is
        # below threshold, upgrade complete → replan (recoverable, R4). Upgrades
        # "called tools" to "answer is grounded". R5: token overlap is a coarse
        # proxy (default-off until offline calibration, see §5.3 R10).
        if tick_state.get("enable_obs_grounded_claims_gate"):
            gte = float(tick_state.get("obs_grounded_gte", 0.15))
            tml = int(tick_state.get("token_min_length", 2))
            if _draft_needs_runtime_grounding(user_message, context=reason_context):
                gq = _grounding_quality(draft_text, tool_results, min_length=tml)
                if gq < gte:
                    return PolicyDecision.replan(
                        CheckPoint.BEFORE_TERMINAL,
                        reason_code="obs_grounded_claims_unmet",
                        evidence={
                            "verdict": "complete",
                            "draft_incomplete": draft_incomplete,
                            "drive_mode": drive_mode,
                            "grounding_quality": gq,
                            "obs_grounded_gte": gte,
                        },
                    )
        # S3 success_criteria_addressed hard_gate (default-off): when success
        # criteria are configured and the draft doesn't hit enough of them,
        # upgrade complete → replan (recoverable, R4). Reuses the same
        # hit-count rule as react_turn_success_evaluator.
        if tick_state.get("enable_success_criteria_gate"):
            success_criteria = tick_state.get("success_criteria") or []
            if success_criteria:
                n_required = int(tick_state.get("react_turn_min_criteria_hits", 1))
                tml = int(tick_state.get("token_min_length", 2))
                hit_count = _criteria_hit_count(draft_text, success_criteria, min_length=tml)
                if hit_count < n_required:
                    return PolicyDecision.replan(
                        CheckPoint.BEFORE_TERMINAL,
                        reason_code="success_criteria_addressed_unmet",
                        evidence={
                            "verdict": "complete",
                            "draft_incomplete": draft_incomplete,
                            "drive_mode": drive_mode,
                            "criteria_hit_count": hit_count,
                            "criteria_required": n_required,
                        },
                    )
        return PolicyDecision.final_success(
            CheckPoint.BEFORE_TERMINAL,
            reason_code="final_success_complete",
            evidence={"verdict": "complete", "draft_incomplete": draft_incomplete, "drive_mode": drive_mode},
        )
    if verdict == DraftCompletenessVerdict.retry_loop:
        return PolicyDecision.replan(
            CheckPoint.BEFORE_TERMINAL,
            reason_code="final_success_retry_loop",
            evidence={"verdict": "retry_loop", "draft_incomplete": draft_incomplete, "drive_mode": drive_mode},
        )
    # fail_fallback
    return PolicyDecision.fail(
        CheckPoint.BEFORE_TERMINAL,
        reason_code="final_success_fail_fallback",
        evidence={"verdict": "fail_fallback", "draft_incomplete": draft_incomplete, "drive_mode": drive_mode},
    )


_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


def _tokenize(text: str, *, min_length: int = 2) -> List[str]:
    """Cheap tokenizer for overlap heuristics.

    Splits on whitespace and common punctuation (both ASCII and CJK). For text
    containing CJK characters (Chinese/Japanese/Korean), the split segments are
    further decomposed into **character-level bigrams** so that ``图书馆在二楼``
    and ``图书馆位于二楼`` produce overlapping bigrams (``图书馆``, ``书馆在``,
    etc.) instead of two non-overlapping whole-sentence tokens. This implements
    the SPEC (F18 §5.1 R5) ``字符级 bigram`` strategy without a heavy CJK
    segmentation dependency.

    Note: tokens are returned in original case; callers lowercase as needed
    (preserves the original contract).
    """
    if not text:
        return []
    tokens: List[str] = []
    for segment in re.split(r"[\s,，。.!！?？;；:：、()\[\]{}\"']+", text):
        if not segment:
            continue
        if _CJK_RE.search(segment):
            # CJK segment: emit character-level bigrams (and the segment itself
            # if it's long enough, so mixed CJK+ASCII content keeps whole-word
            # coverage for the ASCII parts).
            if len(segment) >= min_length:
                tokens.append(segment)
            for i in range(len(segment) - 1):
                bigram = segment[i : i + 2]
                if len(bigram) >= min_length:
                    tokens.append(bigram)
        else:
            if len(segment) >= min_length:
                tokens.append(segment)
    return tokens


def _grounding_quality(draft_text: str, tool_results: List[Any], *, min_length: int = 2) -> float:
    """Overlap between draft tokens and successful tool observation text.

    Returns 0..1 — fraction of draft tokens covered by observation text. Pure
    function; no LLM. When there are no tool results, grounding is vacuously
    satisfied (1.0) only if the draft is empty (no claims to ground); a non-empty
    draft with no observations scores 0.

    **P1 fix:** only successful tool results (``tr.ok`` truthy, or missing ``ok``
    attribute for backward compat) contribute observation text. A failed result
    carrying answer keywords must not inflate the grounding score.
    """
    draft_tokens = set(t.lower() for t in _tokenize(draft_text, min_length=min_length))
    if not draft_tokens:
        return 1.0
    obs_text_parts: List[str] = []
    for tr in tool_results or []:
        # Skip failed tool results — their text (often error messages) must not
        # count as grounding evidence. Objects without an ``ok`` attribute are
        # treated as successful (backward compat for test stubs).
        ok = getattr(tr, "ok", True)
        if ok is False:
            continue
        text = getattr(tr, "text", None) or getattr(tr, "output", None) or ""
        if text:
            obs_text_parts.append(str(text))
    if not obs_text_parts:
        return 0.0
    obs_tokens = set(t.lower() for t in _tokenize(" ".join(obs_text_parts), min_length=min_length))
    if not obs_tokens:
        return 0.0
    covered = draft_tokens & obs_tokens
    return len(covered) / len(draft_tokens)


def _criteria_coverage(draft_text: str, success_criteria: List[str], *, min_length: int = 2) -> float:
    """Fraction of success_criteria tokens present in the draft."""
    if not success_criteria:
        return 1.0
    draft_tokens = set(t.lower() for t in _tokenize(draft_text, min_length=min_length))
    if not draft_tokens:
        return 0.0
    covered = 0
    total = 0
    for criterion in success_criteria:
        crit_tokens = [t.lower() for t in _tokenize(criterion, min_length=min_length)]
        if not crit_tokens:
            continue
        total += 1
        if all(t in draft_tokens for t in crit_tokens):
            covered += 1
    return covered / total if total else 1.0


def _criteria_hit_count(draft_text: str, success_criteria: List[str], *, min_length: int = 2) -> int:
    """Number of criteria whose tokens are all present in the draft.

    A criterion is "hit" when every one of its tokens (len ≥ ``min_length``)
    appears in the draft. Used by ``react_turn_success_evaluator`` for the N-hit
    pass rule.
    """
    if not success_criteria:
        return 0
    draft_tokens = set(t.lower() for t in _tokenize(draft_text, min_length=min_length))
    if not draft_tokens:
        return 0
    count = 0
    for criterion in success_criteria:
        crit_tokens = [t.lower() for t in _tokenize(criterion, min_length=min_length)]
        if not crit_tokens:
            continue
        if all(t in draft_tokens for t in crit_tokens):
            count += 1
    return count


def _progress(
    stagnation_window: int,
    recent_signatures: List[str],
    *,
    cycle_window_multiplier: int = 2,
) -> float:
    """1.0 when not stagnating (recent signatures show progress), 0.0 when
    the last ``stagnation_window`` signatures are identical (adjacent repeat),
    or when the last ``cycle_window_multiplier * stagnation_window`` signatures
    collapse to ≤ 2 distinct values (cycle mode, e.g. A→B→A→B)."""
    if not recent_signatures:
        return 1.0
    k = stagnation_window if stagnation_window > 0 else 3
    mult = cycle_window_multiplier if cycle_window_multiplier > 0 else 2
    # Adjacent repeat: last K signatures all identical.
    recent_k = recent_signatures[-k:]
    if len(recent_k) >= 2 and len(set(recent_k)) == 1:
        return 0.0
    # Cycle mode: last mult*K signatures use ≤ 2 distinct values.
    cycle_window = recent_signatures[-(mult * k):]
    if len(cycle_window) >= mult * k and len(set(cycle_window)) <= 2:
        return 0.0
    return 1.0


def compute_quality_score(
    *,
    draft_text: str,
    tool_results: List[Any],
    success_criteria: List[str],
    recent_signatures: List[str],
    stagnation_window: int,
    semantic_weight_grounding: float = 0.5,
    semantic_weight_criteria: float = 0.3,
    semantic_weight_progress: float = 0.2,
    stagnation_cycle_window_multiplier: int = 2,
    token_min_length: int = 2,
) -> Dict[str, float]:
    """Compute the layered QualityScore (surface / process / semantic).

    Pure function; no LLM. ``surface`` is recorded but not computed here (hard
    gates already judge form); ``process`` is a placeholder (default-off); the
    core dimension is ``semantic`` = grounding + criteria + progress.
    """
    grounding = _grounding_quality(draft_text, tool_results, min_length=token_min_length)
    criteria = _criteria_coverage(draft_text, success_criteria, min_length=token_min_length)
    progress = _progress(
        stagnation_window, recent_signatures,
        cycle_window_multiplier=stagnation_cycle_window_multiplier,
    )
    # semantic = weighted average (weights @configurable, H6).
    semantic = (
        semantic_weight_grounding * grounding
        + semantic_weight_criteria * criteria
        + semantic_weight_progress * progress
    )
    return {
        "surface": 1.0,  # recorded; hard gates already judged form
        "process": 1.0,  # placeholder (default-off)
        "semantic": round(semantic, 4),
    }


def quality_score_evaluator(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """v1 quality_score_evaluator — layered scoring, default-off.

    Returns ``None`` (no opinion → allow) unless ``enable_quality_score`` is on.
    When enabled, computes the layered score and attaches it as ``quality_score``
    evidence on an ``allow`` decision (audit/trace-only; does not block in v1).
    Threshold gating (``semantic_gte``) is a later enforcement concern.
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.BEFORE_TERMINAL:
        return None
    tick_state = ctx.extra.get("tick_state") if ctx.extra else None
    if not isinstance(tick_state, dict):
        return None
    if not tick_state.get("enable_quality_score"):
        return None
    draft_text = tick_state.get("draft_text") or ""
    tool_results = tick_state.get("tool_results") or []
    success_criteria = tick_state.get("success_criteria") or []
    recent_signatures = tick_state.get("recent_signatures") or []
    stagnation_window = int(tick_state.get("stagnation_window", 3))
    try:
        score = compute_quality_score(
            draft_text=draft_text,
            tool_results=tool_results,
            success_criteria=success_criteria,
            recent_signatures=recent_signatures,
            stagnation_window=stagnation_window,
            semantic_weight_grounding=float(tick_state.get("semantic_weight_grounding", 0.5)),
            semantic_weight_criteria=float(tick_state.get("semantic_weight_criteria", 0.3)),
            semantic_weight_progress=float(tick_state.get("semantic_weight_progress", 0.2)),
            stagnation_cycle_window_multiplier=int(tick_state.get("stagnation_cycle_window_multiplier", 2)),
            token_min_length=int(tick_state.get("token_min_length", 2)),
        )
    except Exception as exc:  # noqa: BLE001 — evaluator safety net
        logger.error("evaluator_error: quality_score_evaluator raised: %s", exc)
        return None
    return PolicyDecision(
        decision="allow",
        reason_code="quality_score_recorded",
        check_point=CheckPoint.BEFORE_TERMINAL,
        runtime_action="pass",
        evidence={},
        quality_score=score,
    )


# ---------------------------------------------------------------------------
# Structured Check output parsing — replaces substring heuristics.
# ---------------------------------------------------------------------------

_STRUCTURED_CHECK_RE = re.compile(
    r"^\s*(PASS|RETRY|FAIL)\b", flags=re.IGNORECASE,
)
_NEED_TOOLS_RE = re.compile(
    r"need_tools\s*=\s*([A-Za-z0-9_.\-]+(?:\s*,\s*[A-Za-z0-9_.\-]+)*)",
    flags=re.IGNORECASE,
)
_REASON_RE = re.compile(
    r"reason\s*[:：=]\s*(.+)", flags=re.IGNORECASE,
)


def parse_structured_check_output(text: str) -> Dict[str, Any]:
    """Parse a structured Check LLM output line.

    Recognized shapes (case-insensitive, prefix-anchored):
    - ``PASS``
    - ``RETRY: need_tools=task,agent``
    - ``FAIL: reason=<text>``

    Returns ``{"verdict": "pass"|"retry"|"fail"|"unknown", "need_tools": [...],
    "reason": str}``. Pure function; replaces the legacy substring heuristic
    ``verification_passed`` (``'error' not in co.lower()[:80]``).
    """
    if not text:
        return {"verdict": "unknown", "need_tools": [], "reason": ""}
    m = _STRUCTURED_CHECK_RE.search(text)
    if not m:
        # Fall back to legacy heuristic for backward compatibility with free-text
        # Check outputs that don't follow the structured shape.
        verdict = "pass" if "error" not in text.lower()[:80] else "fail"
        return {"verdict": verdict, "need_tools": [], "reason": ""}
    verdict = m.group(1).lower()
    need_tools: List[str] = []
    reason = ""
    if verdict == "retry":
        nm = _NEED_TOOLS_RE.search(text)
        if nm:
            need_tools = [t.strip() for t in (nm.group(1) or "").split(",") if t.strip()]
    if verdict == "fail":
        rm = _REASON_RE.search(text)
        if rm:
            reason = (rm.group(1) or "").strip()
    return {"verdict": verdict, "need_tools": need_tools, "reason": reason}


def react_turn_success_evaluator(ctx: PolicyContext) -> Optional[PolicyDecision]:
    """v1 react_turn_success_evaluator for the ``per_react_round`` check_point.

    **opt-in**: registered only when ``require_structured_turn`` is enabled
    (the driver gates registration; when free-text, this evaluator is not in
    the chain). Consumes ``success_criteria`` and writes the decision to
    ``ctx.payload['react_round_decision']`` for the inner ReAct loop to consume
    (continue → next round; replan/fail → break loop + flag propagation).

    Returns ``None`` (no opinion) when not at the per_react_round check_point or
    when no structured turn is available; otherwise writes the payload and
    returns an ``allow`` decision (the inner loop reads the payload, not the
    decision, for control flow).
    """
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    if ctx.check_point != CheckPoint.PER_REACT_ROUND:
        return None
    tick_state = ctx.extra.get("tick_state") if ctx.extra else None
    if not isinstance(tick_state, dict):
        return None
    react_turn = tick_state.get("react_turn")
    success_criteria = tick_state.get("success_criteria") or []
    if react_turn is None:
        return None
    # Required criteria hits; defaults to 1 until success checks configure it.
    n_required = int(tick_state.get("react_turn_min_criteria_hits", 1))
    tml = int(tick_state.get("token_min_length", 2))
    try:
        draft_text = ""
        if isinstance(react_turn, dict):
            draft_text = str(react_turn.get("final_answer") or react_turn.get("reasoning") or "")
        if not success_criteria:
            decision = "continue"
            reason_code = "react_turn_no_criteria"
        else:
            hit_count = _criteria_hit_count(draft_text, success_criteria, min_length=tml)
            if hit_count >= n_required:
                decision = "continue"
                reason_code = "react_turn_criteria_met"
            else:
                # Criteria unmet is recoverable, so request a replan.
                decision = "replan"
                reason_code = "react_turn_criteria_unmet"
    except Exception as exc:  # noqa: BLE001 — evaluator safety net
        logger.error("evaluator_error: react_turn_success_evaluator raised: %s", exc)
        decision = "continue"
        reason_code = "react_turn_evaluator_error"
    # Write the payload for the inner ReAct loop to consume.
    payload = ctx.payload if isinstance(ctx.payload, dict) else {}
    payload["react_round_decision"] = {"decision": decision, "reason_code": reason_code}
    return PolicyDecision.allow(CheckPoint.PER_REACT_ROUND, reason_code=reason_code)


class QualityDomain(Domain):
    domain_id = "quality"
    check_points = (
        "after_state_execute",
        "before_terminal",
        "per_react_round",
    )

    def __init__(self, config: QualityDomainConfig) -> None:
        self._config = config

    def evaluators(self) -> List[Evaluator]:
        return [
            stop_evaluator,
            quality_score_evaluator,
            final_success_evaluator,
            react_turn_success_evaluator,
        ]

    def build_context(self, base: PolicyContext) -> PolicyContext:
        return base
