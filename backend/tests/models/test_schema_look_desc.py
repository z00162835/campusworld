"""Schema-driven examine text (graph-seed schema_definition)."""

from __future__ import annotations

import pytest

from app.models.things.schema_look_desc import format_attributes_from_schema_definition


@pytest.mark.unit
@pytest.mark.models
def test_format_attributes_uses_title_and_nested_labels():
    schema = {
        "description": "Lead.",
        "type": "object",
        "properties": {
            "item_kind": {"type": "string"},
            "status": {"type": "string", "title": "设备状态"},
            "network": {
                "type": "object",
                "title": "网络",
                "properties": {"ssid": {"type": "string"}},
            },
        },
    }
    attrs = {"item_kind": "device", "status": "on", "network": {"ssid": "Lab-WiFi"}}
    text = format_attributes_from_schema_definition(attrs, schema, skip_keys=("item_kind",))
    assert text.startswith("Lead.")
    assert "设备状态：on" in text
    assert "网络 · ssid：Lab-WiFi" in text


@pytest.mark.unit
@pytest.mark.models
def test_x_look_omit_skips_property():
    schema = {
        "type": "object",
        "properties": {
            "secret": {"type": "string", "x_look": "omit"},
            "visible": {"type": "string"},
        },
    }
    text = format_attributes_from_schema_definition(
        {"secret": "no", "visible": "yes"},
        schema,
        skip_keys=(),
    )
    assert "secret" not in text
    assert "visible：yes" in text
