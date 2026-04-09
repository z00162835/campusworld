import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.api import api_router


def _param_names(operation: dict) -> set[str]:
    return {param["name"] for param in operation.get("parameters", [])}


def test_f10_routes_registered_in_openapi():
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    client = TestClient(app)

    spec = client.get("/openapi.json").json()
    paths = spec.get("paths", {})

    assert "/api/v1/ontology/node-types" in paths
    assert "/api/v1/ontology/relationship-types" in paths
    assert "/api/v1/graph/nodes" in paths
    assert "/api/v1/graph/relationships" in paths
    assert "/api/v1/graph/worlds/{world_id}/nodes" in paths
    assert "/api/v1/graph/worlds/{world_id}/relationships" in paths
    assert "/api/v1/worlds/{world_id}/nodes" in paths
    assert "/api/v1/worlds/{world_id}/relationships" in paths


def test_graph_nodes_filter_params_in_openapi():
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    client = TestClient(app)

    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/api/v1/graph/nodes"]["get"]
    params = _param_names(operation)

    assert "name_like" in params
    assert "tags_any" in params
    assert "is_public" in params


def test_ontology_types_filter_params_in_openapi():
    app = FastAPI()
    app.include_router(api_router, prefix="/api/v1")
    client = TestClient(app)

    spec = client.get("/openapi.json").json()
    node_type_params = _param_names(spec["paths"]["/api/v1/ontology/node-types"]["get"])
    rel_type_params = _param_names(spec["paths"]["/api/v1/ontology/relationship-types"]["get"])

    assert "name_like" in node_type_params
    assert "tags_any" in node_type_params
    assert "name_like" in rel_type_params
    assert "tags_any" in rel_type_params
