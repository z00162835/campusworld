"""Structured ReAct turn schema — tool-as-schema + JSON parse/repair."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.game_engine.agent_runtime.llm_client import (
    LlmCallSpec,
    LlmClient,
    complete,
    complete_with_tools,
    supports_tools,
)
from app.game_engine.agent_runtime.llm_providers.http_utils import LlmRequestCancelled
from app.game_engine.agent_runtime.tool_calling import (
    ConversationTurn,
    TextTurn,
    ToolCall,
    ToolSchema,
)

_LOG = logging.getLogger(__name__)

EMIT_TURN_TOOL_NAME = "emit_turn"

ActionType = Literal["tool_call", "ask_user", "final_answer", "replan", "no_op"]


class ProposedAction(BaseModel):
    action_type: ActionType
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    final_answer_draft: Optional[str] = None

    @model_validator(mode="after")
    def _validate_tool_args_shape(self) -> "ProposedAction":
        # tool_call must carry argv as {"args": [str, ...]} (campus command contract).
        # A flat flag dict like {"-n": "hicampus"} is rejected so it routes through
        # repair/degrade instead of silently dropping flag names.
        if self.action_type == "tool_call" and self.tool_args is not None:
            args = self.tool_args.get("args")
            if not isinstance(args, list):
                raise ValueError(
                    "tool_args must be an object with an 'args' array of strings "
                    "(e.g. {\"args\": [\"-n\", \"hicampus\"]})"
                )
        return self


class ReactTurn(BaseModel):
    turn_id: str
    task_state_summary: str
    reason_summary: str
    selected_skill: Optional[str] = None
    proposed_action: ProposedAction
    expected_observation: str = ""
    success_criteria: List[str] = Field(default_factory=list)


REACT_TURN_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "turn_id",
        "task_state_summary",
        "reason_summary",
        "proposed_action",
        "expected_observation",
        "success_criteria",
    ],
    "properties": {
        "turn_id": {"type": "string"},
        "task_state_summary": {"type": "string"},
        "reason_summary": {"type": "string"},
        "selected_skill": {"type": ["string", "null"]},
        "proposed_action": {
            "type": "object",
            "additionalProperties": False,
            "required": ["action_type"],
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["tool_call", "ask_user", "final_answer", "replan", "no_op"],
                },
                "tool_name": {"type": ["string", "null"]},
                "tool_args": {
                    "type": ["object", "null"],
                    "description": "For tool_call: an object with an 'args' array of argv strings, e.g. {\"args\": [\"-n\", \"hicampus\"]}.",
                    "properties": {"args": {"type": "array", "items": {"type": "string"}}},
                    "required": ["args"],
                },
                "final_answer_draft": {"type": ["string", "null"]},
            },
        },
        "expected_observation": {"type": "string"},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
    },
}


def emit_turn_tool_schema() -> ToolSchema:
    return ToolSchema(
        name=EMIT_TURN_TOOL_NAME,
        description="Emit one structured agent turn. Always call this tool with the full turn object.",
        input_schema=dict(REACT_TURN_JSON_SCHEMA),
    )


def tool_choice_force_emit_turn() -> Dict[str, Any]:
    """Anthropic-style forced tool_choice for emit_turn."""
    return {"type": "tool", "name": EMIT_TURN_TOOL_NAME}


@dataclass(frozen=True)
class StructuredTurnResult:
    ok: bool
    turn: Optional[ReactTurn]
    raw: Dict[str, Any]
    text: str
    tool_calls: Tuple[ToolCall, ...]
    channel: str  # tool_as_schema | json | free_text
    repaired: bool = False
    degraded: bool = False


def parse_react_turn(data: Any) -> ReactTurn:
    if isinstance(data, ReactTurn):
        return data
    if not isinstance(data, dict):
        raise ValueError("react turn payload must be an object")
    return ReactTurn.model_validate(data)


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else None
    except Exception:
        pass
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fence:
        try:
            val = json.loads(fence.group(1))
            return val if isinstance(val, dict) else None
        except Exception:
            pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            val = json.loads(raw[start : end + 1])
            return val if isinstance(val, dict) else None
        except Exception:
            return None
    return None


def tool_calls_from_react_turn(turn: ReactTurn) -> List[ToolCall]:
    action = turn.proposed_action
    if action.action_type != "tool_call" or not action.tool_name:
        return []
    # tool_args is validated to {"args": [str, ...]} (or None) by ProposedAction.
    raw = action.tool_args or {}
    args = [str(x) for x in raw["args"]] if isinstance(raw.get("args"), list) else []
    return [ToolCall.new(str(action.tool_name), args)]


def text_from_react_turn(turn: ReactTurn) -> str:
    action = turn.proposed_action
    if action.action_type == "final_answer" and action.final_answer_draft:
        return str(action.final_answer_draft).strip()
    if turn.reason_summary:
        return str(turn.reason_summary).strip()
    return str(turn.task_state_summary or "").strip()


def _json_system_addon() -> str:
    schema_text = json.dumps(REACT_TURN_JSON_SCHEMA, ensure_ascii=False)
    return (
        "You must reply with a single JSON object matching this schema "
        f"(no markdown prose outside JSON):\n{schema_text}"
    )


def _repair_user_text(error: str) -> str:
    return (
        "Your previous structured turn was invalid. "
        f"Validation error: {error}. "
        "Reply again with a single valid JSON object for the turn schema."
    )


def _try_validate(payload: Dict[str, Any]) -> Tuple[Optional[ReactTurn], Optional[str]]:
    try:
        return (parse_react_turn(payload), None)
    except (ValidationError, ValueError) as exc:
        return (None, str(exc))


def _payload_from_tools_result(res: Any) -> Optional[Dict[str, Any]]:
    """Prefer emit_turn ``input_payload``, then JSON in text / args."""
    for tc in list(getattr(res, "tool_calls", None) or []):
        if getattr(tc, "name", None) == EMIT_TURN_TOOL_NAME and isinstance(getattr(tc, "input_payload", None), dict):
            return dict(tc.input_payload)
    payload = _extract_json_object(getattr(res, "text", "") or "")
    if payload is not None:
        return payload
    for tc in list(getattr(res, "tool_calls", None) or []):
        if getattr(tc, "args", None):
            payload = _extract_json_object(" ".join(tc.args))
            if payload is not None:
                return payload
        if isinstance(getattr(tc, "input_payload", None), dict):
            return dict(tc.input_payload)
    return None


def emit_structured_turn(
    llm: LlmClient,
    *,
    system: str,
    turns: Sequence[ConversationTurn],
    call_spec: Optional[LlmCallSpec] = None,
    force_tool: bool = True,
    cancel_check: Optional[Callable[[], bool]] = None,
    complete_fn: Optional[Callable[..., str]] = None,
    complete_with_tools_fn: Optional[Callable[..., Any]] = None,
) -> StructuredTurnResult:
    """Emit one structured turn via tool-as-schema or JSON-in-prompt.

    On validation failure, performs one repair retry. A second failure degrades
    to free-text (``degraded=True``).
    """
    spec = call_spec or LlmCallSpec()
    do_complete = complete_fn or complete
    do_cwt = complete_with_tools_fn or complete_with_tools
    use_tool = bool(force_tool and supports_tools(llm))

    def _from_payload(payload: Dict[str, Any], *, channel: str, repaired: bool) -> Optional[StructuredTurnResult]:
        turn, err = _try_validate(payload)
        if turn is None:
            return None
        text = text_from_react_turn(turn)
        calls = tuple(tool_calls_from_react_turn(turn))
        return StructuredTurnResult(
            ok=True,
            turn=turn,
            raw=dict(payload),
            text=text,
            tool_calls=calls,
            channel=channel,
            repaired=repaired,
            degraded=False,
        )

    def _free_text(text: str, *, channel: str, repaired: bool) -> StructuredTurnResult:
        return StructuredTurnResult(
            ok=False,
            turn=None,
            raw={},
            text=(text or "").strip(),
            tool_calls=(),
            channel=channel,
            repaired=repaired,
            degraded=True,
        )

    last_text = ""
    last_err = "invalid structured turn"
    channel = "tool_as_schema" if use_tool else "json"

    # Attempt 1
    try:
        if use_tool:
            extra = dict(spec.extra or {})
            extra["tool_choice"] = tool_choice_force_emit_turn()
            forced_spec = LlmCallSpec(
                mode=spec.mode,
                model=spec.model,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
                timeout_sec=spec.timeout_sec,
                extra=extra,
                skill_context_text=spec.skill_context_text,
            )
            res = do_cwt(
                llm,
                system=system,
                turns=list(turns),
                tools=[emit_turn_tool_schema()],
                call_spec=forced_spec,
                cancel_check=cancel_check,
            )
            payload = _payload_from_tools_result(res)
            last_text = getattr(res, "text", "") or ""
            if payload is not None:
                got = _from_payload(payload, channel=channel, repaired=False)
                if got is not None:
                    return got
                _, last_err = _try_validate(payload)
            else:
                last_err = "emit_turn tool response missing JSON payload"
        else:
            sys2 = f"{system}\n\n{_json_system_addon()}"
            user_text = "\n\n".join(
                t.text for t in turns if isinstance(t, TextTurn) and t.role == "user"
            ) or "Emit the structured turn JSON now."
            last_text = do_complete(
                llm,
                system=sys2,
                user=user_text,
                call_spec=spec,
                cancel_check=cancel_check,
            )
            payload = _extract_json_object(last_text)
            if payload is not None:
                got = _from_payload(payload, channel=channel, repaired=False)
                if got is not None:
                    return got
                _, last_err = _try_validate(payload)
            else:
                last_err = "response was not valid JSON"
    except LlmRequestCancelled:
        raise
    except Exception as exc:
        _LOG.warning("structured turn attempt failed: %s", exc)
        last_err = str(exc)

    # Repair retry (once)
    try:
        repair_turns = list(turns) + [TextTurn(role="user", text=_repair_user_text(last_err))]
        if use_tool:
            extra = dict(spec.extra or {})
            extra["tool_choice"] = tool_choice_force_emit_turn()
            forced_spec = LlmCallSpec(
                mode=spec.mode,
                model=spec.model,
                temperature=spec.temperature,
                max_tokens=spec.max_tokens,
                timeout_sec=spec.timeout_sec,
                extra=extra,
                skill_context_text=spec.skill_context_text,
            )
            res = do_cwt(
                llm,
                system=system,
                turns=repair_turns,
                tools=[emit_turn_tool_schema()],
                call_spec=forced_spec,
                cancel_check=cancel_check,
            )
            last_text = getattr(res, "text", "") or last_text
            payload = _payload_from_tools_result(res)
            if payload is not None:
                got = _from_payload(payload, channel=channel, repaired=True)
                if got is not None:
                    return got
        else:
            sys2 = f"{system}\n\n{_json_system_addon()}"
            last_text = do_complete(
                llm,
                system=sys2,
                user=_repair_user_text(last_err),
                call_spec=spec,
                cancel_check=cancel_check,
            )
            payload = _extract_json_object(last_text)
            if payload is not None:
                got = _from_payload(payload, channel=channel, repaired=True)
                if got is not None:
                    return got
    except LlmRequestCancelled:
        raise
    except Exception as exc:
        _LOG.warning("structured turn repair failed: %s", exc)
        last_text = last_text or str(exc)

    return _free_text(last_text, channel="free_text", repaired=True)
