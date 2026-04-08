"""T6: warn-only attributes vs schema_definition."""

from __future__ import annotations

import logging

import pytest

from db.ontology.attribute_schema_warn import (
    declared_schema_property_keys,
    warn_extra_attributes_vs_schema,
)


@pytest.mark.unit
def test_declared_keys_json_schema_object():
    sd = {"type": "object", "properties": {"a": {"type": "string"}, "b": {}}}
    assert declared_schema_property_keys(sd) == frozenset({"a", "b"})


@pytest.mark.unit
def test_declared_keys_legacy_flat():
    assert declared_schema_property_keys({"name": "string", "age": "integer"}) == frozenset({"name", "age"})


@pytest.mark.unit
def test_warn_extra_attributes_logs_and_returns(caplog):
    caplog.set_level(logging.WARNING)
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    extras = warn_extra_attributes_vs_schema({"a": 1, "orphan": True}, schema, context="node-1")
    assert extras == ("orphan",)
    assert any("orphan" in r.message for r in caplog.records)


@pytest.mark.unit
def test_warn_skips_when_schema_has_no_properties():
    assert warn_extra_attributes_vs_schema({"x": 1}, {}) == ()
    assert warn_extra_attributes_vs_schema({"x": 1}, {"type": "object", "properties": {}}) == ()
