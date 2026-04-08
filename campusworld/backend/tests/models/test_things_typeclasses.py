"""Smoke tests for graph-aligned thing typeclasses."""

import pytest

from app.models.things.agents import NpcAgent
from app.models.things.devices import AvDisplay, LightingFixture, NetworkAccessPoint
from app.models.things.furniture import Furniture
from app.models.things.seating import ConferenceSeating, LoungeFurniture
from app.models.things.terminals import AccessTerminal
from app.models.things.zones import LogicalZone


@pytest.mark.unit
@pytest.mark.models
def test_access_terminal_type_code_and_import_path():
    o = AccessTerminal("t1", disable_auto_sync=True)
    assert o.get_node_type() == "access_terminal"
    assert o.get_node_typeclass() == "app.models.things.terminals.AccessTerminal"


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_smoke():
    o = NpcAgent("npc1", disable_auto_sync=True)
    assert o.get_node_type() == "npc_agent"


@pytest.mark.unit
@pytest.mark.models
def test_logical_zone_smoke():
    o = LogicalZone("z1", disable_auto_sync=True)
    assert o.get_node_type() == "logical_zone"


@pytest.mark.unit
@pytest.mark.models
def test_furniture_smoke():
    o = Furniture("bench", disable_auto_sync=True)
    assert o.get_node_type() == "furniture"


@pytest.mark.unit
@pytest.mark.models
def test_network_access_point_type_code():
    o = NetworkAccessPoint("ap1", disable_auto_sync=True)
    assert o.get_node_type() == "network_access_point"


@pytest.mark.unit
@pytest.mark.models
def test_network_access_point_build_synthetic_look_desc():
    from db.ontology.load import clear_graph_seed_node_type_cache

    clear_graph_seed_node_type_cache()
    o = NetworkAccessPoint(
        "ap1",
        disable_auto_sync=True,
        attributes={
            "item_kind": "device",
            "device_role": "wifi_ap",
            "status": "on",
            "network": {"mode": "ap", "ssid": "X", "bands": ["2.4g"], "encryption": "wpa2"},
            "telemetry": {"clients": 0},
        },
    )
    d = o.build_synthetic_look_desc()
    assert "无线接入点" in d
    assert "X" in d
    assert "0" in d
    assert "设备状态" in d
    assert "网络 · SSID：X" in d


@pytest.mark.unit
@pytest.mark.models
def test_worldthing_build_synthetic_default_empty():
    from app.models.things.base import WorldThing

    o = WorldThing("w", disable_auto_sync=True)
    assert o.build_synthetic_look_desc() == ""


@pytest.mark.unit
@pytest.mark.models
def test_room_get_display_desc_uses_schema_when_no_explicit_text():
    """DefaultObject path: non-WorldThing types use the same schema fallback."""
    from app.models.room import Room

    from db.ontology.load import clear_graph_seed_node_type_cache

    clear_graph_seed_node_type_cache()
    r = Room("GateRoom", disable_auto_sync=True, room_type="gate")
    d = r.get_display_desc()
    assert "room_type：" in d and "gate" in d


@pytest.mark.unit
@pytest.mark.models
def test_av_display_type_code():
    o = AvDisplay("d1", disable_auto_sync=True)
    assert o.get_node_type() == "av_display"


@pytest.mark.unit
@pytest.mark.models
def test_lighting_fixture_type_code():
    o = LightingFixture("l1", disable_auto_sync=True)
    assert o.get_node_type() == "lighting_fixture"


@pytest.mark.unit
@pytest.mark.models
def test_conference_seating_type_code():
    o = ConferenceSeating("s1", disable_auto_sync=True)
    assert o.get_node_type() == "conference_seating"


@pytest.mark.unit
@pytest.mark.models
def test_lounge_furniture_type_code():
    o = LoungeFurniture("c1", disable_auto_sync=True)
    assert o.get_node_type() == "lounge_furniture"


@pytest.mark.unit
@pytest.mark.models
def test_models_package_reexports_things():
    from app.models import AccessTerminal as AT2

    assert AT2 is AccessTerminal
