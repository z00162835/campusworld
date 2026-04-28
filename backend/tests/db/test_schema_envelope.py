"""JSON Schema object envelope helpers (T5)."""

from __future__ import annotations

import pytest

from db.ontology.schema_envelope import (
    account_node_type_schema_definition,
    flat_field_types_to_json_schema_object,
    is_json_schema_object_envelope,
    property_fragments_to_json_schema_object,
    system_command_ability_node_type_schema_definition,
    system_notice_node_type_schema_definition,
)


@pytest.mark.unit
def test_flat_field_types_to_json_schema_object():
    out = flat_field_types_to_json_schema_object({"name": "string", "body": "text", "ok": "boolean"})
    assert out["type"] == "object"
    assert out["properties"]["name"] == {"type": "string"}
    assert out["properties"]["body"] == {"type": "string"}
    assert out["properties"]["ok"] == {"type": "boolean"}


@pytest.mark.unit
def test_flat_field_json_maps_to_empty_property_schema():
    out = flat_field_types_to_json_schema_object({"payload": "json"})
    assert out["properties"]["payload"] == {}


@pytest.mark.unit
def test_property_fragments_required_and_datetime():
    out = property_fragments_to_json_schema_object(
        {"a": {"type": "string", "required": True}, "b": {"type": "datetime"}}
    )
    assert out["type"] == "object"
    assert set(out["required"]) == {"a"}
    assert out["properties"]["a"] == {"type": "string"}
    assert out["properties"]["b"] == {"type": "string", "format": "date-time"}


@pytest.mark.unit
def test_is_json_schema_object_envelope():
    assert is_json_schema_object_envelope({"type": "object", "properties": {}})
    assert not is_json_schema_object_envelope({"username": {"type": "string"}})
    assert not is_json_schema_object_envelope({})


@pytest.mark.unit
def test_account_node_type_schema_definition_envelope():
    sd = account_node_type_schema_definition()
    assert sd["type"] == "object"
    assert "username" in sd["properties"]
    assert set(sd.get("required", [])) >= {"username", "email", "hashed_password"}
    assert sd["properties"]["last_login"] == {"type": "string", "format": "date-time"}


@pytest.mark.unit
def test_builtin_system_schemas_envelope():
    ca = system_command_ability_node_type_schema_definition()
    assert ca["type"] == "object"
    assert ca["properties"]["aliases"] == {}
    sn = system_notice_node_type_schema_definition()
    assert sn["properties"]["content_md"] == {"type": "string"}
