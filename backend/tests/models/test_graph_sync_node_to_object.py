"""GraphSynchronizer.sync_node_to_object: DB→memory hydrate must not auto-insert nodes."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models.base import DefaultObject
from app.models.exit import Exit
from app.models.graph_sync import GraphSynchronizer
from app.models.room import Room
from app.models.user import User


@pytest.mark.unit
def test_sync_node_to_object_user_one_way_hydrate():
    """Account-like classes: disable_auto_sync, uuid from node, column fields applied."""
    node = MagicMock()
    node.name = "admin"
    node.attributes = {"username": "admin", "email": "a@b.com", "roles": ["admin"]}
    node.location_id = 10
    node.home_id = 11
    node.description = None
    node.is_active = True
    node.is_public = False
    node.access_level = "admin"
    node.tags = ["system"]
    uid = uuid.uuid4()
    node.uuid = uid
    node.created_at = None
    node.updated_at = None

    obj = GraphSynchronizer().sync_node_to_object(node, User)
    assert obj is not None
    assert obj.get_node_uuid() == str(uid)
    assert getattr(obj, "_disable_auto_sync", False) is True
    assert obj.get_node_location_id() == 10
    assert obj.get_node_home_id() == 11


@pytest.mark.unit
def test_sync_node_to_object_username_fallback_to_node_name():
    node = MagicMock()
    node.name = "campus"
    node.attributes = {"email": "c@b.com"}
    node.location_id = None
    node.home_id = None
    node.description = ""
    node.is_active = True
    node.is_public = True
    node.access_level = "normal"
    node.tags = []
    uid = uuid.uuid4()
    node.uuid = uid
    node.created_at = None
    node.updated_at = None

    obj = GraphSynchronizer().sync_node_to_object(node, User)
    assert obj is not None
    assert obj.username == "campus"


@pytest.mark.unit
def test_sync_node_to_object_does_not_call_defaultobject_sync_to_node():
    node = MagicMock()
    node.name = "admin"
    node.attributes = {"username": "admin", "email": "a@b.com"}
    node.location_id = None
    node.home_id = None
    node.description = None
    node.is_active = True
    node.is_public = True
    node.access_level = "normal"
    node.tags = []
    node.uuid = uuid.uuid4()
    node.created_at = None
    node.updated_at = None

    with patch.object(DefaultObject, "sync_to_node") as sync_mock:
        obj = GraphSynchronizer().sync_node_to_object(node, User)
    assert obj is not None
    sync_mock.assert_not_called()


@pytest.mark.unit
def test_sync_node_to_object_room_hydrate():
    node = MagicMock()
    node.name = "Lobby"
    node.attributes = {"room_type": "office"}
    node.location_id = 99
    node.home_id = 99
    node.description = "d"
    node.is_active = True
    node.is_public = True
    node.access_level = "normal"
    node.tags = ["room", "hicampus"]
    uid = uuid.uuid4()
    node.uuid = uid
    node.created_at = None
    node.updated_at = None

    obj = GraphSynchronizer().sync_node_to_object(node, Room)
    assert obj is not None
    assert getattr(obj, "_disable_auto_sync", False) is True
    assert obj.get_node_uuid() == str(uid)
    assert obj.get_node_location_id() == 99
    assert obj._node_tags == ["room", "hicampus"]


@pytest.mark.unit
def test_sync_node_to_object_exit_hydrate():
    node = MagicMock()
    node.name = "north"
    node.attributes = {"source_room_id": 1, "destination_room_id": 2, "exit_type": "door"}
    node.location_id = 1
    node.home_id = None
    node.description = None
    node.is_active = True
    node.is_public = True
    node.access_level = "normal"
    node.tags = ["exit"]
    uid = uuid.uuid4()
    node.uuid = uid
    node.created_at = None
    node.updated_at = None

    obj = GraphSynchronizer().sync_node_to_object(node, Exit)
    assert obj is not None
    assert isinstance(obj, Exit)
    assert getattr(obj, "_disable_auto_sync", False) is True
    assert obj.get_node_uuid() == str(uid)
    assert obj.get_node_location_id() == 1


@pytest.mark.unit
def test_model_manager_node_to_object_delegates_to_synchronizer():
    from app.models.model_manager import ModelManager

    mm = ModelManager()
    node = MagicMock()
    node.type_code = "room"
    fake_room = MagicMock()

    with patch.object(mm, "_get_node_type_class", return_value=Room), patch.object(
        mm.synchronizer, "sync_node_to_object", return_value=fake_room
    ) as m:
        out = mm._node_to_object(node)

    assert out is fake_room
    m.assert_called_once_with(node, Room)
