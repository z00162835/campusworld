"""Small helpers for ``agents.llm`` YAML ``extra`` and related blobs."""

from __future__ import annotations

from typing import Any, Mapping, Optional


def parse_bool_extra(
    extra: Optional[Mapping[str, Any]],
    key: str,
    default: bool = True,
) -> bool:
    """Parse a boolean-ish value from ``agents.llm.*.extra`` (YAML may use str or bool)."""
    if not extra:
        return default
    raw = extra.get(key, None)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(int(raw))
    s = str(raw).strip().lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return default
