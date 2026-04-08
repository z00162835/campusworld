"""Warn-only checks: node attributes vs node_types.schema_definition (T6)."""

from __future__ import annotations

import logging
from typing import Any, FrozenSet, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)


def declared_schema_property_keys(schema_definition: Mapping[str, Any]) -> FrozenSet[str]:
    """
    Return declared attribute keys for a schema_definition.

    Supports JSON Schema object with ``properties``, or legacy flat maps where
    values are type hint strings (e.g. ``{"name": "string"}``).
    """
    if not isinstance(schema_definition, Mapping) or not schema_definition:
        return frozenset()
    if str(schema_definition.get("type") or "") == "object" and isinstance(schema_definition.get("properties"), Mapping):
        return frozenset(schema_definition["properties"].keys())  # type: ignore[arg-type]
    vals = list(schema_definition.values())
    if vals and all(isinstance(v, str) for v in vals):
        return frozenset(schema_definition.keys())
    return frozenset()


def warn_extra_attributes_vs_schema(
    attributes: Mapping[str, Any],
    schema_definition: Mapping[str, Any],
    *,
    log: Optional[logging.Logger] = None,
    context: str = "",
) -> Sequence[str]:
    """
    If schema declares property names, log a warning for each attribute key not declared.

    Does not warn on empty schema (nothing declared). Returns the list of extra keys.
    """
    declared = declared_schema_property_keys(schema_definition)
    if not declared:
        return ()
    extras = [k for k in attributes.keys() if k not in declared]
    if not extras:
        return ()
    lg = log or logger
    if context:
        lg.warning(
            "[%s] attributes contain keys not in schema_definition properties: %s",
            context,
            extras,
        )
    else:
        lg.warning("attributes contain keys not in schema_definition properties: %s", extras)
    return tuple(extras)
