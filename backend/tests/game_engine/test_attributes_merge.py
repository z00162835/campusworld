"""Unit tests for graph-seed attribute mutability merge."""

from __future__ import annotations

import pytest

from app.game_engine.graph_seed.attributes_merge import (
    merge_attributes_by_mutability,
    merge_attributes_on_seed_update,
)


@pytest.mark.unit
def test_merge_attributes_preserves_runtime_on_update():
    schema = {
        "properties": {
            "climate_profile": {"mutability": "package_seed"},
            "weather_code": {"mutability": "runtime"},
            "temperature_c": {"mutability": "runtime"},
        }
    }
    existing = {
        "climate_profile": "subtropical_humid",
        "weather_code": "rain",
        "temperature_c": 18,
        "world_id": "hicampus",
    }
    incoming = {
        "climate_profile": "temperate",
        "weather_code": "clear",
        "temperature_c": 26,
        "world_id": "hicampus",
    }
    merged = merge_attributes_by_mutability(existing, incoming, schema)
    assert merged["climate_profile"] == "temperate"
    assert merged["weather_code"] == "rain"
    assert merged["temperature_c"] == 18


@pytest.mark.unit
def test_merge_attributes_create_uses_incoming_when_no_existing_runtime():
    schema = {"properties": {"weather_code": {"mutability": "runtime"}}}
    merged = merge_attributes_by_mutability({}, {"weather_code": "clear"}, schema)
    assert merged["weather_code"] == "clear"


@pytest.mark.unit
def test_merge_on_update_world_environment_delegates_to_mutability_merge():
    schema = {
        "properties": {
            "weather_code": {"mutability": "runtime"},
            "climate_profile": {"mutability": "package_seed"},
        }
    }
    existing = {"weather_code": "rain", "climate_profile": "old"}
    incoming = {"weather_code": "clear", "climate_profile": "new"}
    merged = merge_attributes_on_seed_update(
        existing, incoming, schema, type_code="world_environment"
    )
    assert merged["weather_code"] == "rain"
    assert merged["climate_profile"] == "new"


@pytest.mark.unit
def test_merge_on_update_non_env_preserves_instance_managed_and_shallow_extra_keys():
    schema = {
        "properties": {
            "enabled": {"mutability": "instance_managed"},
            "service_id": {"mutability": "instance_managed"},
            "display_name": {"mutability": "package_seed"},
        }
    }
    existing = {
        "enabled": False,
        "service_id": "runtime-bound-id",
        "display_name": "Old",
        "agent_only_key": "survives",
    }
    incoming = {
        "enabled": True,
        "service_id": "yaml-id",
        "display_name": "New",
    }
    merged = merge_attributes_on_seed_update(
        existing, incoming, schema, type_code="npc_agent"
    )
    assert merged["enabled"] is False
    assert merged["service_id"] == "runtime-bound-id"
    assert merged["display_name"] == "New"
    assert merged["agent_only_key"] == "survives"
