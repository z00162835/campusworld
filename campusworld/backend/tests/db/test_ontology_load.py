"""Unit tests for graph-seed node_types ontology YAML loader."""

from __future__ import annotations

import json

import pytest
import yaml

from db.ontology.load import (
    default_graph_seed_node_types_path,
    load_graph_seed_node_type_overrides,
    node_type_jsonb_params,
)


@pytest.mark.unit
def test_default_yaml_path_exists():
    p = default_graph_seed_node_types_path()
    assert p.name == "graph_seed_node_types.yaml"
    assert p.parent.name == "ontology"


@pytest.mark.unit
def test_load_overrides_covers_graph_seed_types():
    ov = load_graph_seed_node_type_overrides()
    for code in (
        "network_access_point",
        "access_terminal",
        "lighting_fixture",
        "av_display",
        "furniture",
        "room",
        "building",
        "world",
    ):
        assert code in ov, f"missing {code}"
    sd = ov["network_access_point"]["schema_definition"]
    assert sd.get("type") == "object"
    assert "properties" in sd
    assert sd["properties"]["status"]["value_kind"] == "dynamic_snapshot"
    assert ov["room"]["schema_definition"]["properties"]["room_type"]["value_kind"] == "static"


@pytest.mark.unit
def test_load_overrides_missing_file_returns_empty(tmp_path):
    assert load_graph_seed_node_type_overrides(tmp_path / "nope.yaml") == {}


@pytest.mark.unit
def test_node_type_jsonb_params_roundtrip():
    jb = node_type_jsonb_params({"schema_definition": {"type": "object"}, "tags": ["a"]})
    assert json.loads(jb["schema_definition"]) == {"type": "object"}
    assert json.loads(jb["tags"]) == ["a"]


@pytest.mark.unit
def test_custom_yaml_overlay(tmp_path):
    p = tmp_path / "t.yaml"
    p.write_text(
        yaml.safe_dump(
            {"node_types": {"room": {"tags": ["x"], "schema_definition": {"type": "object", "properties": {}}}}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    ov = load_graph_seed_node_type_overrides(p)
    assert ov["room"]["tags"] == ["x"]
