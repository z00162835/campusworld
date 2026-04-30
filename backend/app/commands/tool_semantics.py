"""Command tool semantics for agent manifest and guard metadata."""

from __future__ import annotations

from typing import Any, Dict, Optional


_MUTATE_COMMANDS = {
    "task",
    "create",
    "notice",
    "world",
}

_DOCUMENT_COMMANDS = {
    "help",
    "primer",
    "version",
}


def _routing_hint_i18n_for(name: str) -> Dict[str, str]:
    if name == "task":
        return {
            "zh-CN": "若用户问 task 的例子/语法/用法，先走 help task（或 primer）；不要把示例请求当作执行请求。仅在用户明确执行且确认后才可调用会改状态的 task 子命令。",
            "en-US": "For task examples/syntax/usage, route to `help task` (or primer) first; do not treat example requests as execute intent. Call state-changing task subcommands only after explicit execution intent and confirmation.",
        }
    if name == "create":
        return {
            "zh-CN": "create 会改变系统状态。示例/语法问题应使用 help create；仅在明确执行且确认后调用。",
            "en-US": "create mutates system state. Example/syntax requests should use `help create`; call only with explicit execution intent and confirmation.",
        }
    return {}


def _default_guard_for(profile: str) -> Dict[str, Any]:
    if profile == "mutate":
        return {
            "requires_confirmation": True,
            "allowed_intents": ["execute"],
            "block_when_intent_only_examples": True,
            "side_effect_scope": "state_change",
        }
    if profile == "document":
        return {
            "requires_confirmation": False,
            "allowed_intents": ["informational", "verify_state"],
            "block_when_intent_only_examples": False,
            "side_effect_scope": "none",
        }
    return {
        "requires_confirmation": False,
        "allowed_intents": ["verify_state", "informational"],
        "block_when_intent_only_examples": False,
        "side_effect_scope": "none",
    }


def get_command_tool_semantics(command_name: str) -> Dict[str, Any]:
    """Return semantic metadata used by ability sync and tool manifest."""
    name = str(command_name or "").strip().lower()
    pending = False
    if name in _MUTATE_COMMANDS:
        profile = "mutate"
    elif name in _DOCUMENT_COMMANDS:
        profile = "document"
    else:
        # D12 default
        profile = "read"
        pending = True

    hints = _routing_hint_i18n_for(name)
    routing_hint = hints.get("en-US", "") if hints else ""
    return {
        "interaction_profile": profile,
        "semantic_pending": pending,
        "routing_hint": routing_hint,
        "routing_hint_i18n": hints,
        "invocation_guard": _default_guard_for(profile),
    }


def pick_routing_hint(attrs: Dict[str, Any], locale: str) -> Optional[str]:
    raw_i18n = attrs.get("routing_hint_i18n")
    if isinstance(raw_i18n, dict):
        if locale in raw_i18n and str(raw_i18n.get(locale) or "").strip():
            return str(raw_i18n[locale]).strip()
        # fallback to en-US
        if str(raw_i18n.get("en-US") or "").strip():
            return str(raw_i18n["en-US"]).strip()
    raw = attrs.get("routing_hint")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
