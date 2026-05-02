"""MiniMax Anthropic-compatible Messages API (POST .../anthropic/v1/messages).

Provides both the plain ``complete`` path and the native ``tool_use`` path
(`supports_tools() == True` / :meth:`complete_with_tools`). Wire-format
conversions stay inside this module so the framework only sees the neutral
:mod:`app.game_engine.agent_runtime.tool_calling` primitives.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from app.game_engine.agent_runtime.llm_client import LlmCallSpec
from app.game_engine.agent_runtime.llm_providers.http_utils import httpx_post_json
from app.game_engine.agent_runtime.tool_calling import (
    AssistantToolUseTurn,
    CompleteWithToolsResult,
    ConversationTurn,
    TextTurn,
    ToolCall,
    ToolResultsTurn,
    ToolSchema,
)


def minimax_anthropic_messages_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("base_url required for MiniMax Anthropic Messages client")
    if b.endswith("/v1/messages"):
        return b
    if b.endswith("/anthropic"):
        return f"{b}/v1/messages"
    if "/anthropic" in b.lower():
        return f"{b}/v1/messages"
    return f"{b}/anthropic/v1/messages"


def clamp_anthropic_temperature(value: float) -> float:
    """MiniMax Anthropic layer documents temperature in (0, 1]."""
    if value <= 0.0:
        return 0.01
    if value > 1.0:
        return 1.0
    return value


class MinimaxAnthropicMessagesHttpLlmClient:
    """
    MiniMax Anthropic-compatible Messages API.
    See https://platform.minimax.io/docs/api-reference/text-anthropic-api
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        default_model: str,
        default_temperature: float = 0.2,
        default_max_tokens: int = 4096,
        timeout_sec: float = 120.0,
    ):
        self._base_url = base_url
        self._api_key = api_key
        self._default_model = default_model
        self._default_temperature = default_temperature
        self._default_max_tokens = default_max_tokens
        self._timeout = timeout_sec

    def complete(self, *, system: str, user: str, call_spec: Optional[LlmCallSpec] = None) -> str:
        spec = call_spec or LlmCallSpec()
        model = (spec.model or self._default_model).strip() or self._default_model
        max_tokens = spec.max_tokens if spec.max_tokens is not None else self._default_max_tokens
        timeout = spec.timeout_sec if spec.timeout_sec is not None else self._timeout
        temp = spec.temperature if spec.temperature is not None else self._default_temperature
        temp = clamp_anthropic_temperature(float(temp))

        url = minimax_anthropic_messages_url(self._base_url)
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "system": system or " ",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": user or " "}],
                }
            ],
            "stream": False,
            "temperature": temp,
        }
        extra = dict(spec.extra or {})
        extra.pop("prompt_fingerprint", None)
        body.update(extra)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = httpx_post_json(url, headers=headers, body=body, timeout=timeout)
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            raise RuntimeError(str(err.get("message")))
        parts: list[str] = []
        for block in data.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
        return "\n".join(p.strip() for p in parts if p.strip()).strip()

    # ---------------- native tool_use ----------------

    def supports_tools(self) -> bool:
        return True

    def complete_with_tools(
        self,
        *,
        system: str,
        turns: Sequence[ConversationTurn],
        tools: Sequence[ToolSchema],
        call_spec: Optional[LlmCallSpec] = None,
    ) -> CompleteWithToolsResult:
        """Anthropic-style ``tools`` + ``tool_use`` / ``tool_result`` round-trip."""
        spec = call_spec or LlmCallSpec()
        model = (spec.model or self._default_model).strip() or self._default_model
        max_tokens = spec.max_tokens if spec.max_tokens is not None else self._default_max_tokens
        timeout = spec.timeout_sec if spec.timeout_sec is not None else self._timeout
        temp = spec.temperature if spec.temperature is not None else self._default_temperature
        temp = clamp_anthropic_temperature(float(temp))

        url = minimax_anthropic_messages_url(self._base_url)
        messages = _turns_to_anthropic_messages(turns)
        allowed_names = {str(t.name) for t in tools if getattr(t, "name", None)}
        _validate_anthropic_tool_messages(messages, allowed_tool_names=allowed_names)
        body: Dict[str, Any] = {
            "model": model,
            "max_tokens": int(max_tokens),
            "system": system or " ",
            "messages": messages,
            "stream": False,
            "temperature": temp,
            "tools": [_tool_schema_to_anthropic(t) for t in tools],
        }
        extra = dict(spec.extra or {})
        extra.pop("prompt_fingerprint", None)
        body.update(extra)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = httpx_post_json(url, headers=headers, body=body, timeout=timeout)
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            raise RuntimeError(str(err.get("message")))
        return _parse_anthropic_response(data)


# --------- module-local helpers; no external imports rely on these names ---------


def _tool_schema_to_anthropic(schema: ToolSchema) -> Dict[str, Any]:
    return {
        "name": schema.name,
        "description": schema.description,
        "input_schema": dict(schema.input_schema),
    }


def _tool_result_content_wire(observation_text: str) -> List[Dict[str, str]]:
    """Anthropic ``tool_result.content`` as a text content block (string also legal).

    Using a one-element ``[{"type":"text","text":...}]`` matches the structured
    form in the Messages API reference and avoids empty-string edge cases on
    some compatible gateways.
    """
    return [{"type": "text", "text": observation_text or ""}]


def _validate_anthropic_tool_messages(
    messages: Sequence[Dict[str, Any]],
    *,
    allowed_tool_names: set[str],
) -> None:
    """Fail fast before HTTP if ``messages`` break Anthropic tool ordering rules.

    Checks:
      * every ``tool_use`` has a non-empty ``id`` and a ``name`` listed in
        ``allowed_tool_names``;
      * a ``user`` message with ``tool_result`` blocks must immediately follow
        an ``assistant`` message that declared those ``tool_use`` ids;
      * within one ``user`` message, all ``tool_result`` blocks precede any
        ``text`` block (Anthropic constraint when mixing in one message);
      * ``tool_result`` id set equals the pending ``tool_use`` id set from the
        prior assistant message (one user turn answers the whole batch).
    """
    pending_ids: Optional[set[str]] = None

    for idx, msg in enumerate(messages):
        role = msg.get("role")
        raw = msg.get("content")
        if not isinstance(raw, list):
            continue
        blocks = [b for b in raw if isinstance(b, dict)]

        if role == "assistant":
            ids: set[str] = set()
            for b in blocks:
                if b.get("type") != "tool_use":
                    continue
                tid = str(b.get("id") or "").strip()
                if not tid:
                    raise ValueError(f"messages[{idx}] assistant tool_use missing id")
                nm = str(b.get("name") or "").strip()
                if nm not in allowed_tool_names:
                    raise ValueError(
                        f"messages[{idx}] assistant tool_use name {nm!r} "
                        f"not in request tools {sorted(allowed_tool_names)!r}"
                    )
                ids.add(tid)
            pending_ids = ids if ids else None

        elif role == "user":
            tool_result_ids: List[str] = []
            seen_text = False
            for b in blocks:
                btype = b.get("type")
                if btype == "tool_result":
                    if seen_text:
                        raise ValueError(
                            f"messages[{idx}] user: tool_result blocks must come "
                            "before any text block in the same message"
                        )
                    tuid = str(b.get("tool_use_id") or "").strip()
                    if not tuid:
                        raise ValueError(f"messages[{idx}] user tool_result missing tool_use_id")
                    tool_result_ids.append(tuid)
                elif btype == "text":
                    seen_text = True
                else:
                    seen_text = True

            if tool_result_ids:
                if not pending_ids:
                    raise ValueError(
                        f"messages[{idx}] user has tool_result but no preceding "
                        "assistant tool_use ids (protocol violation)"
                    )
                got = set(tool_result_ids)
                if got != pending_ids:
                    raise ValueError(
                        f"messages[{idx}] tool_result ids {sorted(got)!r} != "
                        f"pending assistant tool_use ids {sorted(pending_ids)!r}"
                    )
                pending_ids = None
            elif pending_ids:
                raise ValueError(
                    f"messages[{idx}] user message must carry tool_result for "
                    f"pending tool_use ids {sorted(pending_ids)!r}"
                )

    if pending_ids:
        raise ValueError(
            "messages end with assistant tool_use without a following user "
            f"tool_result turn (pending ids: {sorted(pending_ids)!r})"
        )


def _turns_to_anthropic_messages(turns: Sequence[ConversationTurn]) -> List[Dict[str, Any]]:
    """Map neutral turns to Anthropic ``messages`` array.

    * ``TextTurn`` → ``{role, content: [{type: text, text}]}``.
    * ``AssistantToolUseTurn`` → ``{role: assistant, content: [text?, tool_use…]}``.
    * ``ToolResultsTurn`` → ``{role: user, content: [{type: tool_result, ...}]}``.

    The neutral ``AssistantToolUseTurn`` is produced by the runtime after each
    native tool round; this adapter maps it to wire-format ``tool_use`` blocks
    so ``tool_result`` ids resolve (Anthropic / MiniMax Anthropic-compatible).
    """
    messages: List[Dict[str, Any]] = []
    for t in turns:
        if isinstance(t, TextTurn):
            role = t.role if t.role in ("user", "assistant") else "user"
            messages.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": t.text or " "}],
                }
            )
        elif isinstance(t, AssistantToolUseTurn):
            blocks: List[Dict[str, Any]] = []
            if (t.text or "").strip():
                blocks.append({"type": "text", "text": (t.text or "").strip()})
            for c in t.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": (c.id or "").strip(),
                        "name": c.name,
                        "input": {"args": list(c.args)},
                    }
                )
            if blocks:
                messages.append({"role": "assistant", "content": blocks})
        elif isinstance(t, ToolResultsTurn):
            content_blocks: List[Dict[str, Any]] = []
            for r in t.results:
                content_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": r.id,
                        "content": _tool_result_content_wire(r.text or ""),
                        "is_error": not r.ok,
                    }
                )
            if content_blocks:
                messages.append({"role": "user", "content": content_blocks})
    return messages


def _parse_anthropic_response(data: Dict[str, Any]) -> CompleteWithToolsResult:
    text_parts: List[str] = []
    calls: List[ToolCall] = []
    for block in data.get("content") or []:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            text_parts.append(str(block.get("text") or ""))
        elif btype == "tool_use":
            name = str(block.get("name") or "").strip()
            raw_input = block.get("input") or {}
            args: List[str] = []
            if isinstance(raw_input, dict):
                maybe_args = raw_input.get("args")
                if isinstance(maybe_args, list):
                    args = [str(a) for a in maybe_args]
                else:
                    # Fallback: flatten other primitive fields in declaration order.
                    args = [str(v) for v in raw_input.values() if isinstance(v, (str, int, float))]
            calls.append(ToolCall(id=str(block.get("id") or ""), name=name, args=args))
    finish = str(data.get("stop_reason") or ("tool_use" if calls else "stop"))
    return CompleteWithToolsResult(
        text="\n".join(p.strip() for p in text_parts if p.strip()).strip(),
        tool_calls=calls,
        finish_reason=finish,
    )
