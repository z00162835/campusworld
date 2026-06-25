from unittest.mock import MagicMock, patch

from app.services.entity_inspect_service import (
    _actions_from_attributes,
    _entity_kind,
    _filter_inspect_appearance_lines,
    _resolve_node_id,
    build_entity_inspect_data,
)
from app.services.world_interaction.types import WorldActor


def _actor() -> WorldActor:
    return WorldActor(user_id="1", username="tester", permissions=["player.*"], roles=["player"])


def test_resolve_node_id_prefers_node_id():
    assert _resolve_node_id(node_id=42, agent_id="99") == 42


def test_resolve_node_id_from_agent_id():
    assert _resolve_node_id(node_id=None, agent_id="77") == 77


def test_entity_kind_mapping():
    node = MagicMock()
    node.type_code = "npc_agent"
    node.attributes = {}
    node.trait_class = "AGENT"
    assert _entity_kind(node, "agent") == "agent"

    node.type_code = "account"
    node.trait_class = "AGENT"
    assert _entity_kind(node, "service") == "person"

    node.type_code = "account"
    node.trait_class = "PERSON"
    assert _entity_kind(node, "service") == "person"

    node.type_code = "character"
    node.trait_class = ""
    assert _entity_kind(node, "object") == "person"


def test_filter_inspect_appearance_lines():
    lines = _filter_inspect_appearance_lines(
        [
            "*Lamp*",
            "Bright light.",
            "引用: lamp_ref",
            "包内节点: hicampus_lamp_01",
            "节点 id: 55",
            "类型: lighting_fixture",
        ]
    )
    assert lines == ["*Lamp*", "Bright light.", "类型: lighting_fixture"]


def test_actions_from_attributes_reads_capabilities():
    actions = _actions_from_attributes(
        {
            "capabilities": [
                {
                    "id": "switch_on",
                    "label": "Turn on",
                    "style": "primary",
                    "actionType": "execute_command",
                    "command": "switch on lamp",
                }
            ]
        }
    )
    assert len(actions) == 1
    assert actions[0]["id"] == "switch_on"
    assert actions[0]["command"] == "switch on lamp"


@patch("app.services.entity_inspect_service._node_space_trait", return_value=False)
@patch("app.services.entity_inspect_service.LookCommand")
def test_build_entity_inspect_data_returns_payload(mock_look_cls, _space_trait):
    session = MagicMock()
    user_node = MagicMock()
    user_node.id = 1
    user_node.location_id = 10
    user_node.type_code = "account"
    user_node.is_active = True

    target = MagicMock()
    target.id = 55
    target.type_code = "item"
    target.trait_class = "DEVICE"
    target.attributes = {"capabilities": []}
    target.location_id = 10
    target.name = "Lamp"
    target.description = "A lamp"
    target.is_active = True

    loc_node = MagicMock()
    loc_node.id = 10
    loc_node.name = "Room"
    loc_node.is_active = True
    session.query.return_value.filter.return_value.first.side_effect = [target, user_node, loc_node]

    look_cmd = mock_look_cls.return_value
    look_cmd._graph_object_dict_by_node_id.return_value = {"node_id": 55, "name": "Lamp"}
    look_cmd._build_object_description.return_value = (
        "*Lamp*\nBright light.\n引用: lamp_ref\n包内节点: hicampus_lamp_01\n节点 id: 55"
    )

    payload = build_entity_inspect_data(session, _actor(), node_id=55)
    assert payload is not None
    assert payload["entity"]["id"] == "55"
    assert payload["entity_kind"] == "device"
    assert payload["appearance"]["lines"] == ["*Lamp*", "Bright light."]
    assert payload["source"] == "look"


@patch("app.services.entity_inspect_service._node_space_trait", return_value=False)
def test_build_entity_inspect_data_denies_invisible_node(_space_trait):
    session = MagicMock()
    user_node = MagicMock()
    user_node.id = 1
    user_node.location_id = 10
    user_node.type_code = "account"
    user_node.is_active = True

    target = MagicMock()
    target.id = 99
    target.type_code = "item"
    target.trait_class = "ITEM"
    target.attributes = {}
    target.location_id = 77
    target.is_active = True

    session.query.return_value.filter.return_value.first.side_effect = [target, user_node]

    assert build_entity_inspect_data(session, _actor(), node_id=99, visible_node_ids={55}) is None


@patch("app.services.entity_inspect_service._node_space_trait", return_value=True)
def test_build_entity_inspect_data_returns_none_for_space(_space_trait):
    session = MagicMock()
    node = MagicMock()
    node.id = 10
    node.is_active = True
    session.query.return_value.filter.return_value.first.return_value = node
    assert build_entity_inspect_data(session, _actor(), node_id=10) is None
