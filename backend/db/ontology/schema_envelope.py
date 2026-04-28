"""Helpers to wrap legacy node_types.schema_definition in JSON Schema object form (T5)."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional

_SQLISH_TO_JSON_TYPE = {
    "string": "string",
    "text": "string",
    "integer": "integer",
    "int": "integer",
    "boolean": "boolean",
    "bool": "boolean",
    "number": "number",
    "float": "number",
}


def _normalize_fragment_type(spec: MutableMapping[str, Any]) -> None:
    """Normalize non-JSON-Schema types (e.g. datetime) in-place."""
    t = spec.get("type")
    if t == "datetime":
        spec["type"] = "string"
        spec.setdefault("format", "date-time")


def property_fragments_to_json_schema_object(fragments: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Convert legacy { key: { type, required?, default?, ... } } to JSON Schema object.

    Pulls per-property ``required: True`` into root ``required`` array.
    """
    properties: Dict[str, Any] = {}
    required_list: List[str] = []
    for key, raw in fragments.items():
        if not isinstance(raw, Mapping):
            continue
        spec = dict(raw)
        if spec.pop("required", False) is True:
            required_list.append(str(key))
        _normalize_fragment_type(spec)
        properties[str(key)] = spec
    out: Dict[str, Any] = {"type": "object", "properties": properties}
    if required_list:
        out["required"] = required_list
    return out


def flat_field_types_to_json_schema_object(flat: Dict[str, str]) -> Dict[str, Any]:
    """
    Convert {"field": "string", ...} to {"type": "object", "properties": {...}}.

    ``json`` maps to an unconstrained property schema ``{}`` (arbitrary JSON).
    """
    props: Dict[str, Any] = {}
    for key, sqlish in flat.items():
        sk = str(sqlish).lower().strip()
        if sk == "json":
            props[key] = {}
            continue
        jt = _SQLISH_TO_JSON_TYPE.get(sk, "string")
        props[key] = {"type": jt}
    return {"type": "object", "properties": props}


# --- Canonical builtin node_types.schema_definition (single source of truth) ---

ACCOUNT_NODE_TYPE_PROPERTY_FRAGMENTS: Dict[str, Dict[str, Any]] = {
    "username": {"type": "string", "required": True},
    "email": {"type": "string", "required": True},
    "hashed_password": {"type": "string", "required": True},
    "roles": {"type": "array", "default": ["user"]},
    "permissions": {"type": "array", "default": []},
    "is_verified": {"type": "boolean", "default": False},
    "is_locked": {"type": "boolean", "default": False},
    "is_suspended": {"type": "boolean", "default": False},
    "login_count": {"type": "integer", "default": 0},
    "failed_login_attempts": {"type": "integer", "default": 0},
    "max_failed_attempts": {"type": "integer", "default": 5},
    "last_login": {"type": "datetime"},
    "last_activity": {"type": "datetime"},
    "lock_reason": {"type": "string"},
    "suspension_reason": {"type": "string"},
    "suspension_until": {"type": "datetime"},
    "created_by": {"type": "string", "default": "system"},
    "access_level": {"type": "string", "default": "normal"},
}


def account_node_type_schema_definition() -> Dict[str, Any]:
    """Full account node_types.schema_definition (envelope)."""
    return property_fragments_to_json_schema_object(ACCOUNT_NODE_TYPE_PROPERTY_FRAGMENTS)


_SYSTEM_COMMAND_ABILITY_FLAT: Dict[str, str] = {
    "command_name": "string",
    "aliases": "json",
    "command_type": "string",
    "help_category": "string",
    "stability": "string",
    "input_schema": "json",
    "output_schema": "json",
    "updated_at": "string",
}


def system_command_ability_node_type_schema_definition() -> Dict[str, Any]:
    return flat_field_types_to_json_schema_object(_SYSTEM_COMMAND_ABILITY_FLAT)


_SYSTEM_NOTICE_FLAT: Dict[str, str] = {
    "title": "string",
    "content_md": "text",
    "status": "string",
    "is_active": "boolean",
    "published_at": "string",
}


def system_notice_node_type_schema_definition() -> Dict[str, Any]:
    return flat_field_types_to_json_schema_object(_SYSTEM_NOTICE_FLAT)


def is_json_schema_object_envelope(schema_definition: Optional[Mapping[str, Any]]) -> bool:
    """True if root looks like our JSON Schema object convention."""
    if not isinstance(schema_definition, Mapping):
        return False
    return str(schema_definition.get("type") or "") == "object" and isinstance(
        schema_definition.get("properties"), Mapping
    )
