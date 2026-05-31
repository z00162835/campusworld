"""Merge graph-seed node attributes respecting schema mutability."""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Mapping, Optional, Set

# Reload update path: only these mutability labels keep DB values on non-env types.
_PRESERVE_ON_RELOAD_MUTABILITIES: FrozenSet[str] = frozenset({'runtime', 'instance_managed'})


def attribute_keys_by_mutability(
    schema_definition: Optional[Mapping[str, Any]],
    mutabilities: FrozenSet[str],
) -> Set[str]:
    props = (schema_definition or {}).get('properties') if isinstance(schema_definition, Mapping) else None
    if not isinstance(props, Mapping):
        return set()
    keys: Set[str] = set()
    for key, spec in props.items():
        if isinstance(spec, Mapping) and str(spec.get('mutability') or '') in mutabilities:
            keys.add(str(key))
    return keys


def runtime_attribute_keys(schema_definition: Optional[Mapping[str, Any]]) -> Set[str]:
    return attribute_keys_by_mutability(schema_definition, frozenset({'runtime'}))


def merge_attributes_by_mutability(
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
    schema_definition: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    """``world_environment`` update: ``runtime`` keys stay from *existing*; other keys from *incoming*."""
    out = dict(incoming)
    for key in runtime_attribute_keys(schema_definition):
        if key in existing:
            out[key] = existing[key]
    return out


def merge_attributes_on_seed_update(
    existing: Mapping[str, Any],
    incoming: Mapping[str, Any],
    schema_definition: Optional[Mapping[str, Any]],
    *,
    type_code: str,
) -> Dict[str, Any]:
    """
    Update-path attribute merge for graph seed upsert.

    - ``world_environment``: full mutability merge (runtime preserved; package_seed from YAML).
    - All other types: shallow overlay (legacy) plus preserve ``runtime`` / ``instance_managed``
      keys declared in schema so agent/device/portal instance state is not wiped on reload.
    """
    if str(type_code or '') == 'world_environment':
        return merge_attributes_by_mutability(existing, incoming, schema_definition)
    out = {**dict(existing), **dict(incoming)}
    for key in attribute_keys_by_mutability(schema_definition, _PRESERVE_ON_RELOAD_MUTABILITIES):
        if key in existing:
            out[key] = existing[key]
    return out
