"""Smoke tests for graph-aligned thing typeclasses."""

import pytest

from app.models.things.agents import NpcAgent
from app.models.things.furniture import Furniture
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
def test_models_package_reexports_things():
    from app.models import AccessTerminal as AT2

    assert AT2 is AccessTerminal
