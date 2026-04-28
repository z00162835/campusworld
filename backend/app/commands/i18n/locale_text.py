"""
Locale normalization and i18n string picking for the command / help / tool manifest.

Follows: requested language → default zh-CN → en-US → single-language legacy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from app.commands.base import CommandContext

# Application default: matches existing `User.language` and graph defaults
DEFAULT_LOCALE = "zh-CN"
FALLBACK_CHAIN: Tuple[str, ...] = (DEFAULT_LOCALE, "en-US")

# BCP-47 style tags; extend cautiously
_LOCALE_ALIASES: Dict[str, str] = {
    "": DEFAULT_LOCALE,
    "zh": "zh-CN",
    "zh-cn": "zh-CN",
    "zh_hans": "zh-CN",
    "zh-hans": "zh-CN",
    "en": "en-US",
    "en-us": "en-US",
}


def normalize_locale(raw: Optional[str]) -> str:
    """Map loose user/config strings to stable BCP-47 style tags (subset)."""
    if raw is None:
        return DEFAULT_LOCALE
    s = str(raw).strip()
    if not s:
        return DEFAULT_LOCALE
    key = s.replace("_", "-").lower()
    if key in _LOCALE_ALIASES:
        return _LOCALE_ALIASES[key]
    if key.startswith("zh-hans") or key == "zho":
        return "zh-CN"
    if key.startswith("zh-"):
        return "zh-CN"
    if key.startswith("en") and (len(key) == 2 or key[2:3] in ("-", "_")):
        return "en-US"
    if "-" in s:
        parts = s.split("-", 1)
        lang = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        if lang == "zh":
            return f"zh-{rest[:2].upper()}" if rest else "zh-CN"
        if lang == "en":
            return f"en-{rest[:2].upper()}" if rest else "en-US"
    return s


@dataclass(frozen=True)
class I18nPick:
    value: str
    hit_locale: str
    fallback_used: bool


def pick_i18n(
    mapping: Optional[Dict[str, str]],
    requested_locale: str,
    fallbacks: Tuple[str, ...] = FALLBACK_CHAIN,
    *,
    legacy_default: Optional[str] = None,
) -> I18nPick:
    """
    Return first non-empty string in order: requested → each fallback → legacy.
    `mapping` values are treated as text; empty strings are ignored.
    """
    norm = normalize_locale(requested_locale)
    if not mapping:
        base = (legacy_default or "").strip()
        return I18nPick(value=base, hit_locale=norm, fallback_used=True)

    order: List[str] = [norm] + [normalize_locale(f) for f in fallbacks if f is not None]
    seen: set = set()
    unique_order: List[str] = []
    for loc in order:
        if loc not in seen:
            seen.add(loc)
            unique_order.append(loc)

    for loc in unique_order:
        v = mapping.get(loc)
        if v is not None and str(v).strip():
            return I18nPick(
                value=str(v).strip(),
                hit_locale=loc,
                fallback_used=loc != norm,
            )

    base = (legacy_default or "").strip()
    return I18nPick(value=base, hit_locale=norm, fallback_used=True)


def _graph_account_language(
    db_session: Any,
    user_id: Optional[str],
    username: Optional[str],
) -> Optional[str]:
    if db_session is None:
        return None
    try:
        from app.models.graph import Node

        if user_id is not None:
            try:
                row = (
                    db_session.query(Node)
                    .filter(
                        Node.id == int(user_id),
                        Node.type_code == "account",
                    )
                    .first()
                )
                if row is not None and isinstance(row.attributes, dict):
                    return row.attributes.get("language")
            except (TypeError, ValueError):
                pass
        if username:
            row = (
                db_session.query(Node)
                .filter(
                    Node.type_code == "account",
                    Node.name == str(username),
                    Node.is_active == True,  # noqa: E712
                )
                .first()
            )
            if row is not None and isinstance(row.attributes, dict):
                return row.attributes.get("language")
    except Exception:
        return None
    return None


def resolve_locale(
    context: "CommandContext",
) -> str:
    """
    Effective locale: metadata override, then account node language, then default.
    """
    md: Optional[Dict] = getattr(context, "metadata", None)
    if (
        isinstance(md, dict)
        and md.get("locale") is not None
        and str(md.get("locale", "")).strip()
    ):
        return normalize_locale(str(md.get("locale")))

    lang = _graph_account_language(
        getattr(context, "db_session", None),
        getattr(context, "user_id", None),
        getattr(context, "username", None),
    )
    if lang and str(lang).strip():
        return normalize_locale(str(lang))
    return DEFAULT_LOCALE


def tool_manifest_locale(explicit: Optional[str] = None) -> str:
    """
    Locale for AICO/LLM tool manifest rows: system default from config, not per-user ``help``.

    Non-empty ``explicit`` is normalized and returned. Otherwise uses ``AppConfig.default_locale``
    from config, then :data:`DEFAULT_LOCALE` if config is unavailable.
    """
    if explicit is not None and str(explicit).strip():
        return normalize_locale(str(explicit))
    try:
        from app.core.config_manager import get_config

        raw = getattr(get_config().app, "default_locale", None)
        if raw is not None and str(raw).strip():
            return normalize_locale(str(raw))
    except Exception:
        pass
    return DEFAULT_LOCALE


def help_shell_for_locale(locale: str) -> Dict[str, str]:
    """Labels for the help / detailed-help shell."""
    loc = normalize_locale(locale)
    if loc.startswith("en"):
        return {
            "title_list": "Available Commands",
            "title_detail": "Command Help: {name}",
            "line_usage": "Usage: {text}",
            "line_aliases": "Aliases: {items}",
            "line_type": "Type: {text}",
            "line_description": "Description: {text}",
            "footer": "Type 'help <command>' for more.",
            "err_not_found": "Command not found: {name}",
        }
    return {
        "title_list": "可用命令",
        "title_detail": "命令帮助: {name}",
        "line_usage": "用法: {text}",
        "line_aliases": "别名: {items}",
        "line_type": "类型: {text}",
        "line_description": "描述: {text}",
        "footer": "使用 'help <command>' 查看单条命令帮助。",
        "err_not_found": "未找到命令: {name}",
    }


def initial_metadata_for_session(
    *,
    db_session: Optional[Any],
    user_id: Optional[str],
    username: Optional[str],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build ``metadata`` for a new :class:`CommandContext` (e.g. protocol entry)."""
    ex = dict(extra or {})
    if "locale" in ex and ex.get("locale") is not None and str(ex.get("locale", "")).strip():
        ex["locale"] = normalize_locale(str(ex["locale"]))
    else:
        lang = _graph_account_language(db_session, user_id, username) if db_session is not None else None
        ex["locale"] = normalize_locale(str(lang)) if lang and str(lang).strip() else DEFAULT_LOCALE
    return ex
