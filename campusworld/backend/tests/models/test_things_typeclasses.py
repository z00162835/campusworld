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
