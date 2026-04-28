import sys
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.api import api_router
from app.api.v1.dependencies import APIPrincipal, get_api_principal
from app.constants.data_access_defaults import ADMIN_DATA_ACCESS
from app.core.database import get_db
from app.models.graph import Node, NodeType, Relationship, RelationshipType


class QueryStub:
    def __init__(self, *, items=None, first_item=None):
        self.items = items or []
        self.first_item = first_item
        self._offset = 0
        self._limit = None

    def filter(self, *args, **kwargs):
        return self

    def join(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def count(self):
        return len(self.items)

    def offset(self, n):
        self._offset = n
        return self

    def limit(self, n):
        self._limit = n
        return self

    def all(self):
        out = self.items[self._offset :]
        if self._limit is not None:
            out = out[: self._limit]
        return out

    def first(self):
        if self.first_item is not None:
            return self.first_item
        return self.items[0] if self.items else None


def _principal(perms):
    return APIPrincipal(
        subject="42",
        auth_type="jwt",
        roles=[],
        permissions=perms,
        user_attrs={"data_access": ADMIN_DATA_ACCESS},
        scopes=[],
        api_key_kid=None,
    )


def _build_client(mock_db, principal=None, with_auth=True):
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")

    def _mock_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = _mock_get_db
    if with_auth:
        async def _mock_principal():
            return principal or _principal(["ontology.read", "ontology.write", "graph.read", "graph.write"])
        app.dependency_overrides[get_api_principal] = _mock_principal

    return TestClient(app, raise_server_exceptions=False)


def _row(payload):
    obj = MagicMock()
    obj.to_dict.return_value = payload
    return obj


def test_ontology_node_types_get_and_post_conflict_problem_json():
    mock_db = MagicMock()
    list_rows = [_row({"id": 1, "type_code": "room"})]

    def _query(model):
        if model is NodeType:
            if _query.calls == 0:
                _query.calls += 1
                return QueryStub(items=list_rows)
            return QueryStub(first_item=MagicMock())  # conflict on create
        return QueryStub()

    _query.calls = 0
    mock_db.query.side_effect = _query
    client = _build_client(mock_db)

    r1 = client.get("/api/v1/ontology/node-types?name_like=ro&tags_any=a,b")
    assert r1.status_code == 200
    assert r1.json()["page"]["total"] == 1

    r2 = client.post(
        "/api/v1/ontology/node-types",
        json={
            "type_code": "room",
            "type_name": "Room",
            "typeclass": "x.y.Room",
            "classname": "Room",
            "module_path": "x.y",
        },
    )
    assert r2.status_code == 409
    assert r2.headers["content-type"].startswith("application/problem+json")
    assert r2.json()["status"] == 409


def test_ontology_relationship_types_get_and_post_create():
    mock_db = MagicMock()
    list_rows = [_row({"id": 10, "type_code": "connects_to"})]
    create_row = MagicMock()
    create_row.to_dict.return_value = {"id": 11, "type_code": "located_in"}

    def _query(model):
        if model is RelationshipType:
            if _query.calls == 0:
                _query.calls += 1
                return QueryStub(items=list_rows)
            return QueryStub(first_item=None)
        return QueryStub()

    _query.calls = 0
    mock_db.query.side_effect = _query
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "to_dict", create_row.to_dict)
    client = _build_client(mock_db)

    r1 = client.get("/api/v1/ontology/relationship-types?name_like=connect")
    assert r1.status_code == 200
    assert r1.json()["page"]["total"] == 1

    r2 = client.post(
        "/api/v1/ontology/relationship-types",
        json={
            "type_code": "located_in",
            "type_name": "Located In",
            "typeclass": "x.y.Rel",
        },
    )
    assert r2.status_code == 201
    assert r2.json()["type_code"] == "located_in"


def test_graph_nodes_get_post_patch_delete_and_not_found():
    mock_db = MagicMock()
    node_row = _row({"id": 100, "name": "R1"})
    stored_node = MagicMock()
    stored_node.to_dict.return_value = {"id": 200, "name": "created"}

    def _query(model):
        if model is Node:
            if _query.node_calls == 0:
                _query.node_calls += 1
                return QueryStub(items=[node_row])
            if _query.node_calls == 1:
                _query.node_calls += 1
                return QueryStub(first_item=stored_node)  # patch
            return QueryStub(first_item=None)  # delete not found
        if model is NodeType:
            return QueryStub(first_item=MagicMock(id=7, trait_class="ROOM", trait_mask=7))
        return QueryStub()

    _query.node_calls = 0
    mock_db.query.side_effect = _query
    client = _build_client(mock_db)

    r1 = client.get("/api/v1/graph/nodes?is_public=true&name_like=r")
    assert r1.status_code == 200
    assert r1.json()["page"]["total"] == 1

    r2 = client.post(
        "/api/v1/graph/nodes",
        json={
            "type_code": "room",
            "name": "R2",
            "trait_class": "SHOULD_BE_IGNORED",
            "trait_mask": 999,
            "attributes": {"world_id": "hicampus"},
        },
    )
    assert r2.status_code == 201
    added = mock_db.add.call_args[0][0]
    assert added.trait_class == "ROOM"
    assert int(added.trait_mask) == 7

    r3 = client.patch("/api/v1/graph/nodes/200", json={"name": "R2-updated", "unknown": "ignored"})
    assert r3.status_code == 200

    r4 = client.delete("/api/v1/graph/nodes/999")
    assert r4.status_code == 404
    assert r4.headers["content-type"].startswith("application/problem+json")


def test_graph_relationships_get_post_and_validation_problem_json():
    mock_db = MagicMock()
    rel_row = _row({"id": 1, "type_code": "located_in"})
    saved = MagicMock()
    saved.to_dict.return_value = {"id": 2, "type_code": "located_in"}

    def _query(model):
        if model is Relationship:
            return QueryStub(items=[rel_row])
        if model is RelationshipType:
            return QueryStub(first_item=MagicMock(id=8))
        if model is Node:
            if _query.node_hits == 0:
                _query.node_hits += 1
                return QueryStub(first_item=MagicMock(id=10))
            _query.node_hits += 1
            return QueryStub(first_item=None)  # missing target
        return QueryStub()

    _query.node_hits = 0
    mock_db.query.side_effect = _query
    mock_db.refresh.side_effect = lambda obj: setattr(obj, "to_dict", saved.to_dict)
    client = _build_client(mock_db)

    r1 = client.get("/api/v1/graph/relationships?type_code=located_in")
    assert r1.status_code == 200
    assert r1.json()["page"]["total"] == 1

    r2 = client.post(
        "/api/v1/graph/relationships",
        json={"type_code": "located_in", "source_id": 1, "target_id": 2},
    )
    assert r2.status_code == 400
    assert r2.headers["content-type"].startswith("application/problem+json")


def test_world_scope_nodes_and_relationships_list():
    mock_db = MagicMock()
    wn = _row({"id": 12, "name": "Room-A", "attributes": {"world_id": "hicampus"}})
    wr = _row({"id": 33, "type_code": "connects_to"})

    def _query(model):
        if model is Node:
            return QueryStub(items=[wn])
        if model is Relationship:
            return QueryStub(items=[wr])
        return QueryStub()

    mock_db.query.side_effect = _query
    client = _build_client(mock_db)

    r1 = client.get("/api/v1/graph/worlds/hicampus/nodes?is_public=true&tags_any=a,b")
    assert r1.status_code == 200
    assert r1.json()["page"]["total"] == 1

    r2 = client.get("/api/v1/graph/worlds/hicampus/relationships?type_code=connects_to&source_id=1&target_id=2")
    assert r2.status_code == 200
    assert r2.json()["page"]["total"] == 1

    # alias routes required by SPEC
    r3 = client.get("/api/v1/worlds/hicampus/nodes?is_public=true")
    assert r3.status_code == 200
    r4 = client.get("/api/v1/worlds/hicampus/relationships?type_code=connects_to&source_id=1&target_id=2")
    assert r4.status_code == 200


def test_f10_permission_denied_returns_403():
    mock_db = MagicMock()
    mock_db.query.return_value = QueryStub(items=[])
    client = _build_client(mock_db, principal=_principal(["graph.read"]))

    r = client.post(
        "/api/v1/ontology/node-types",
        json={
            "type_code": "x",
            "type_name": "X",
            "typeclass": "a.b.X",
            "classname": "X",
            "module_path": "a.b",
        },
    )
    assert r.status_code == 403


def test_f10_missing_credentials_returns_401():
    mock_db = MagicMock()
    mock_db.query.return_value = QueryStub(items=[])
    client = _build_client(mock_db, with_auth=False)
    r = client.get("/api/v1/graph/nodes")
    assert r.status_code == 401


def test_spec_query_validation_blank_name_like_and_empty_tags_any():
    mock_db = MagicMock()
    mock_db.query.return_value = QueryStub(items=[])
    client = _build_client(mock_db)

    r1 = client.get("/api/v1/ontology/node-types?name_like=%20%20")
    assert r1.status_code == 400
    assert r1.headers["content-type"].startswith("application/problem+json")

    r2 = client.get("/api/v1/graph/nodes?tags_any=,%20")
    assert r2.status_code == 400
    assert r2.headers["content-type"].startswith("application/problem+json")

    r3 = client.get("/api/v1/graph/relationships?name_eq=")
    assert r3.status_code == 400
    assert r3.headers["content-type"].startswith("application/problem+json")
