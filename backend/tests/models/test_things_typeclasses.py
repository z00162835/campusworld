"""Smoke tests for graph-aligned thing typeclasses."""

import pytest

from app.models.things.agents import NpcAgent
from app.models.things.devices import AvDisplay, LightingFixture, NetworkAccessPoint
from app.models.things.furniture import Furniture
from app.models.things.seating import ConferenceSeating, LoungeFurniture
from app.models.things.terminals import AccessTerminal
from app.models.things.zones import LogicalZone
from app.models.things.environments import WorldEnvironment


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
    assert o.get_node_typeclass() == "app.models.things.agents.NpcAgent"


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_inherits_character_and_keeps_type_code():
    from app.models.character import Character
    from app.models.base import DefaultObject

    o = NpcAgent("npc1", disable_auto_sync=True)
    assert isinstance(o, Character)
    assert isinstance(o, DefaultObject)
    # Character.__init__ writes _node_type='character'; NpcAgent must restore it.
    assert o.get_node_type() == "npc_agent"
    assert o._node_type == "npc_agent"
    assert o._node_type_code == "npc_agent"


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_defaults_is_npc_and_is_ai():
    o = NpcAgent("npc1", disable_auto_sync=True)
    assert o.is_npc is True
    assert o._node_attributes.get("is_ai") is True
    tags = o._node_tags
    assert "npc" in tags
    assert "ai" in tags


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_disable_auto_sync_not_leaked_into_attributes():
    o = NpcAgent("npc1", disable_auto_sync=True)
    assert "disable_auto_sync" not in o._node_attributes


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_sync_observes_npc_agent_type_code(monkeypatch):
    """sync_to_node runs inside super().__init__ via at_object_creation; the
    type_code must already be 'npc_agent' at that moment, not 'character'
    (F02 §6.1 invariant #1). Patch sync_to_node to capture the value without DB.
    """
    captured = {}

    def fake_sync(self):
        captured["type_code"] = self.get_node_type()

    monkeypatch.setattr(NpcAgent, "sync_to_node", fake_sync)
    # Construct WITHOUT disable_auto_sync so at_object_creation reaches sync.
    NpcAgent("sync_probe")
    assert captured.get("type_code") == "npc_agent"


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_cmdset_branch_by_agent_role():
    from app.commands.cmdset import CharacterCmdSet, NPCCmdSet

    # Unspecified role defaults to the narrative_npc branch (NPCCmdSet only).
    o_default = NpcAgent("a", disable_auto_sync=True)
    stack_default = o_default.get_cmdset_manager().cmdset_stack
    assert len(stack_default) == 1
    assert isinstance(stack_default[0], NPCCmdSet)
    assert not any(isinstance(c, CharacterCmdSet) for c in stack_default)

    o_npc = NpcAgent("b", disable_auto_sync=True, agent_role="narrative_npc")
    stack_npc = o_npc.get_cmdset_manager().cmdset_stack
    assert len(stack_npc) == 1
    assert isinstance(stack_npc[0], NPCCmdSet)
    assert not any(isinstance(c, CharacterCmdSet) for c in stack_npc)

    o_worker = NpcAgent("c", disable_auto_sync=True, agent_role="sys_worker")
    assert o_worker.get_cmdset_manager().cmdset_stack == []


@pytest.mark.unit
@pytest.mark.models
def test_npc_agent_rpg_hooks_are_noop():
    o = NpcAgent("npc1", disable_auto_sync=True)
    # _initialize_base_stats must not mutate stats based on character_type.
    o._node_attributes["character_type"] = "athlete"
    o._initialize_base_stats()
    assert o._node_attributes.get("agility") == 10  # unchanged from Character default
    assert o._node_attributes.get("max_energy") == 100

    cost = o.at_action_cost("run")
    assert cost == {"success": True, "energy_cost": 0}
    res = o.at_action_result("run")
    assert res == {"success": True}


@pytest.mark.unit
@pytest.mark.models
def test_logical_zone_smoke():
    o = LogicalZone("z1", disable_auto_sync=True)
    assert o.get_node_type() == "logical_zone"


@pytest.mark.unit
@pytest.mark.models
def test_world_environment_smoke():
    o = WorldEnvironment("env1", disable_auto_sync=True)
    assert o.get_node_type() == "world_environment"


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
