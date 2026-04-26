"""
Command UI strings: load per-locale YAML under ``locales/`` (single source of truth).

File layout::

    locales/
      zh-CN.yaml
      en-US.yaml

Schema (per file)::

    commands:
      <command_name>:
        description: "one line for help list and derived surfaces"
        # optional later: usage, detail
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

from app.commands.i18n.locale_text import FALLBACK_CHAIN, normalize_locale, pick_i18n

# Files expected: ``<tag>.yaml`` in this package's ``locales`` directory
_LOCALE_FILES: Tuple[str, ...] = ("zh-CN", "en-US")

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCALES_DIR = os.path.join(_PKG_DIR, "locales")

def clear_command_resource_cache() -> None:
    """Call after editing locale files in tests or hot-reload experiments."""
    get_bundle_by_tag.cache_clear()


@lru_cache(maxsize=16)
def get_bundle_by_tag(tag: str) -> Dict[str, Any]:
    """Load and parse one locale file; empty dict if missing or error."""
    if yaml is None:
        return {}
    if not tag or not str(tag).strip():
        return {}
    fn = f"{str(tag).strip()}.yaml"
    path = os.path.join(_LOCALES_DIR, fn)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def get_command_i18n_map(
    command_name: str, field: str = "description"
) -> Dict[str, str]:
    """Collect ``field`` for ``command_name`` across all known locale files."""
    out: Dict[str, str] = {}
    for tag in _LOCALE_FILES:
        b = get_bundle_by_tag(tag)
        cmds = b.get("commands")
        if not isinstance(cmds, dict):
            continue
        ent = cmds.get(command_name)
        if not isinstance(ent, dict):
            continue
        v = ent.get(field)
        if v is None or not str(v).strip():
            continue
        out[tag] = str(v).strip()
    return out


def get_localized_string_from_resource(
    command_name: str,
    field: str,
    requested_locale: str,
) -> str:
    m = get_command_i18n_map(command_name, field=field)
    if not m:
        return ""
    p = pick_i18n(
        m,
        requested_locale,
        fallbacks=FALLBACK_CHAIN,
        legacy_default=None,
    )
    return (p.value or "").strip()


def get_command_i18n_text(
    command_name: str,
    key_path: str,
    locale: str,
    default: str,
) -> str:
    """Resolve ``commands.<command_name>.<key_path>`` text from locale YAMLs.

    Walks the requested locale first, then ``FALLBACK_CHAIN``; returns ``default`` if no
    bundle yields a non-empty string. Nested key paths use ``.`` separators
    (e.g. ``"goodbye"`` or ``"error.unavailable"``).
    """

    def _dig(node: Any, path: List[str]) -> Optional[str]:
        cur = node
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        if cur is None:
            return None
        txt = str(cur).strip()
        return txt if txt else None

    loc = normalize_locale(locale)
    order: List[str] = [loc] + [normalize_locale(x) for x in FALLBACK_CHAIN if x]
    seen: set = set()
    unique: List[str] = []
    for tag in order:
        if tag not in seen:
            seen.add(tag)
            unique.append(tag)

    parts = ["commands", str(command_name)] + [p for p in str(key_path).split(".") if p]
    for tag in unique:
        bundle = get_bundle_by_tag(tag)
        val = _dig(bundle, parts)
        if val is not None:
            return val
    return default


def merge_description_i18n_for_ability(
    command_name: str, legacy: Optional[Dict[str, str]]
) -> Dict[str, str]:
    """For graph ``llm_hint_i18n``: resource wins; merge with legacy in-code table if any."""
    m = dict(get_command_i18n_map(command_name, "description"))
    if isinstance(legacy, dict) and legacy:
        for k, v in legacy.items():
            if k and str(v).strip() and k not in m:
                m[k] = str(v).strip()
    return m
