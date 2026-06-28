from pathlib import Path
import sys
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.api.v1.dependencies import AuthenticatedUser, get_current_http_user
from app.api.v1.endpoints import world_interaction
from app.core.database import get_db


def _test_user():
    return AuthenticatedUser(
        user_id="1",
        username="tester",
        email="tester@example.com",
        roles=["player"],
        permissions=["player.*"],
        user_attrs={},
    )


def _app():
    app = FastAPI()
    app.include_router(world_interaction.world_sessions_router, prefix="/api/v1")
    app.include_router(world_interaction.worlds_router, prefix="/api/v1")
    app.include_router(world_interaction.decision_center_router, prefix="/api/v1")
    app.include_router(world_interaction.semantic_map_router, prefix="/api/v1")
    app.include_router(world_interaction.world_search_router, prefix="/api/v1")
    app.include_router(world_interaction.world_history_router, prefix="/api/v1")
    app.dependency_overrides[get_current_http_user] = _test_user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return app


def test_world_interaction_routes_do_not_use_stage_names():
    app = _app()
    paths = {route.path for route in app.routes}
    assert "/api/v1/world-sessions/current" in paths
    assert "/api/v1/world-sessions/enter-world" in paths
    assert "/api/v1/decision-center/actions" in paths
    assert not any("mvp" in path or "phase" in path or "nextui" in path.lower() for path in paths)


def test_decision_action_adapter_passes_generated_ids(monkeypatch):
    seen = {}

    def fake_execute(db, actor, decision_event_id, option_id):
        seen["actor"] = actor
        seen["decision_event_id"] = decision_event_id
        seen["option_id"] = option_id
        return {"success": True, "result": {"summary": "ok", "status": "completed"}, "state_patch": {}}

    monkeypatch.setattr(world_interaction.world_interaction_service, "execute_decision_action", fake_execute)
    client = TestClient(_app())

    response = client.post(
        "/api/v1/decision-center/actions",
        json={"session_id": "world_1", "decision_event_id": "next_navigation", "option_id": "go_next"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert seen["actor"].user_id == "1"
    assert seen["decision_event_id"] == "next_navigation"
    assert seen["option_id"] == "go_next"


def _phase1_aggregate_payload() -> dict:
    return {
        "session": {
            "id": "world_1",
            "currentWorldId": None,
            "currentSpaceId": "10",
            "currentSpaceKey": "singularity",
            "updatedAt": "2026-05-31T00:00:00Z",
        },
        "interaction_state": {
            "session": {
                "id": "world_1",
                "currentWorldId": None,
                "currentSpaceId": "10",
                "updatedAt": "2026-05-31T00:00:00Z",
            },
            "decision_center": {
                "focus": {"title": "Singularity Room", "summary": "1 task(s) need your attention.", "severity": "warning"},
                "decisionEvents": [
                    {
                        "id": "task_42",
                        "title": "Explore CampusWorld",
                        "type": "task",
                        "options": [{"id": "task_start_42", "command": "task start 42"}],
                    }
                ],
                "activeTask": {"id": "task_42", "title": "Explore CampusWorld", "status": "active"},
                "nextBestAction": {"id": "task_start_42", "label": "Start task", "command": "task start 42"},
                "quickQueries": [],
                "loading": False,
                "error": None,
            },
            "focus_map": {"mode": "focus", "nodes": [{"id": "10", "name": "Singularity Room"}], "currentSpaceId": "10"},
            "context_summary": {
                "currentSpace": {"id": "10", "name": "Singularity Room", "oneLineSummary": "CampusWorld hub"},
                "pendingDecisionCount": 1,
                "lastHandledTask": {
                    "id": "41",
                    "title": "Previous task",
                    "status": "done",
                    "handledAt": "2026-05-30T12:00:00Z",
                },
                "nearbyAgents": {"total": 0, "highlighted": []},
                "suggestedQueries": [],
            },
            "quick_queries": [],
        },
        "display_policy": {
            "maxDecisionEventsVisible": 2,
            "maxActionsPerCard": 3,
            "maxMapNodesVisible": 7,
            "maxAgentsHighlighted": 3,
            "contextDefaultCollapsed": True,
            "mapDefaultCollapsed": True,
            "historyDefaultCollapsed": True,
        },
        "available_worlds": [{"world_id": "hicampus", "name": "HiCampus", "is_recommended": True}],
    }


def test_current_world_session_returns_phase1_aggregate_fields(monkeypatch):
    payload = _phase1_aggregate_payload()
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "get_current_state",
        lambda db, actor: payload,
    )
    client = TestClient(_app())
    response = client.get("/api/v1/world-sessions/current")
    assert response.status_code == 200
    body = response.json()

    assert body["display_policy"]["mapDefaultCollapsed"] is True
    assert body["display_policy"]["contextDefaultCollapsed"] is True

    interaction = body["interaction_state"]
    assert interaction["decision_center"]["decisionEvents"][0]["id"] == "task_42"
    assert interaction["decision_center"]["decisionEvents"][0]["type"] == "task"
    assert interaction["context_summary"]["lastHandledTask"]["title"] == "Previous task"
    assert interaction["context_summary"]["pendingDecisionCount"] == 1
    assert interaction["focus_map"]["currentSpaceId"] == "10"


def test_aico_sync_query_returns_400():
    client = TestClient(_app())
    response = client.post(
        "/api/v1/decision-center/query",
        json={"session_id": "world_1", "query": "hello", "mode": "aico"},
    )
    assert response.status_code == 400


def test_command_query_returns_state_patch(monkeypatch):
    def fake_query(db, actor, query):
        return {
            "answer": "You see the room.",
            "mode": "command",
            "command_result": {"success": True, "message": "You see the room.", "data": None, "error": None},
            "suggested_actions": [],
            "state_patch": {"currentSpaceId": "10"},
        }

    monkeypatch.setattr(world_interaction.world_interaction_service, "run_command_query", fake_query)
    client = TestClient(_app())
    response = client.post(
        "/api/v1/decision-center/query",
        json={"session_id": "world_1", "query": "/look", "mode": "command"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state_patch"]["currentSpaceId"] == "10"
    assert body["command_result"]["message"] == "You see the room."


def test_archive_conversations_and_history_summary(monkeypatch):
    stored_archives = []

    def fake_append(session, user, entry):
        stored_archives.append(entry)
        return entry

    def fake_list(session, account_node_id, *, limit=50, offset=0):
        page = stored_archives[offset: offset + limit]
        return page, len(stored_archives)

    monkeypatch.setattr(
        world_interaction.world_interaction_service._archive_repo,
        "append_for_account",
        fake_append,
    )
    monkeypatch.setattr(
        world_interaction.world_interaction_service._archive_repo,
        "list_summaries_for_account",
        fake_list,
    )

    client = TestClient(_app())
    archive = client.post(
        "/api/v1/world-history/conversations/archive",
        json={
            "aico_threads": [{"id": "t1", "title": "Test", "messages": [{"id": "m1", "role": "user", "mode": "aico", "answer": "hi"}], "updatedAt": "2026-05-31T00:00:00Z"}],
            "command_conversation": [],
        },
    )
    assert archive.status_code == 200
    assert archive.json()["archived"] is True

    summary = client.get("/api/v1/world-history/summary")
    assert summary.status_code == 200
    groups = {group["id"]: group for group in summary.json()["groups"]}
    assert "aico_conversations" in groups
    aico_item = groups["aico_conversations"]["items"][0]
    assert aico_item["title"] == "Test"
    assert aico_item["messageCount"] == 1
    assert "preview" in aico_item
    assert summary.json()["pagination"]["total"] == 1


def test_archive_conversations_rejects_oversized_batch(monkeypatch):
    from app.repositories.world_conversation_archive import WorldHistoryArchiveLimitError

    def fake_append(session, user, entry):
        raise WorldHistoryArchiveLimitError("Archive batch exceeds size limit (512000 bytes)")

    monkeypatch.setattr(
        world_interaction.world_interaction_service._archive_repo,
        "append_for_account",
        fake_append,
    )

    client = TestClient(_app())
    response = client.post(
        "/api/v1/world-history/conversations/archive",
        json={
            "aico_threads": [],
            "command_conversation": [{"id": "m1", "role": "user", "mode": "command", "answer": "look"}],
        },
    )
    assert response.status_code == 422
    assert "size limit" in response.json()["detail"]


def test_archive_conversations_rejects_oversized_command_payload():
    client = TestClient(_app())
    response = client.post(
        "/api/v1/world-history/conversations/archive",
        json={
            "aico_threads": [],
            "command_conversation": [
                {"id": f"m{i}", "role": "user", "mode": "command", "answer": f"msg {i}"}
                for i in range(51)
            ],
        },
    )
    assert response.status_code == 422


def test_archive_conversations_rejects_oversized_aico_thread():
    client = TestClient(_app())
    response = client.post(
        "/api/v1/world-history/conversations/archive",
        json={
            "aico_threads": [
                {
                    "id": "t1",
                    "title": "Test",
                    "messages": [
                        {"id": f"m{i}", "role": "user", "mode": "aico", "answer": f"msg {i}"}
                        for i in range(51)
                    ],
                    "updatedAt": "2026-05-31T00:00:00Z",
                }
            ],
            "command_conversation": [],
        },
    )
    assert response.status_code == 422


def test_archive_conversations_rejects_unknown_fields():
    client = TestClient(_app())
    response = client.post(
        "/api/v1/world-history/conversations/archive",
        json={
            "aico_threads": [],
            "command_conversation": [],
            "extra_field": True,
        },
    )
    assert response.status_code == 422


def test_archive_conversations_rejects_archive_batch_limit(monkeypatch):
    from app.repositories.world_conversation_archive import WorldHistoryArchiveLimitError

    def fake_append(session, user, entry):
        raise WorldHistoryArchiveLimitError("Archive limit reached (100 batches per account)")

    monkeypatch.setattr(
        world_interaction.world_interaction_service._archive_repo,
        "append_for_account",
        fake_append,
    )

    client = TestClient(_app())
    response = client.post(
        "/api/v1/world-history/conversations/archive",
        json={
            "aico_threads": [],
            "command_conversation": [{"id": "m1", "role": "user", "mode": "command", "answer": "look"}],
        },
    )
    assert response.status_code == 422
    assert "Archive limit reached" in response.json()["detail"]


def test_aico_stream_response_has_anti_buffer_headers(monkeypatch):
    def fake_stream(actor, query, *, thread_id=None):
        yield 'data: {"kind":"meta","scope":"stream","stream_id":"x"}\n\n'

    monkeypatch.setattr(world_interaction.world_interaction_service, 'stream_aico_query', fake_stream)
    client = TestClient(_app())
    response = client.post(
        '/api/v1/decision-center/query/stream',
        json={'session_id': 'world_1', 'query': 'hello', 'mode': 'aico'},
    )
    assert response.status_code == 200
    assert response.headers.get('cache-control') == 'no-cache'
    assert response.headers.get('x-accel-buffering') == 'no'


def test_stream_cancel_endpoint(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "cancel_stream",
        lambda stream_id: {"ok": True, "stream_id": stream_id},
    )
    client = TestClient(_app())
    response = client.post(
        "/api/v1/decision-center/query/stream/cancel",
        json={"stream_id": "abc123"},
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_decision_action_adapter_accepts_task_queue_ids(monkeypatch):
    seen = {}

    def fake_execute(db, actor, decision_event_id, option_id):
        seen["decision_event_id"] = decision_event_id
        seen["option_id"] = option_id
        return {"success": True, "result": {"summary": "ok", "status": "completed"}, "state_patch": {}}

    monkeypatch.setattr(world_interaction.world_interaction_service, "execute_decision_action", fake_execute)
    client = TestClient(_app())
    response = client.post(
        "/api/v1/decision-center/actions",
        json={"session_id": "world_1", "decision_event_id": "task_42", "option_id": "task_start_42"},
    )
    assert response.status_code == 200
    assert seen["decision_event_id"] == "task_42"
    assert seen["option_id"] == "task_start_42"


def test_semantic_map_focus_route_registered():
    paths = {route.path for route in _app().routes}
    assert "/api/v1/semantic-map/focus" in paths
    assert "/api/v1/semantic-map/space-summary" in paths
    assert "/api/v1/semantic-map/entity-inspect" in paths
    assert "/api/v1/semantic-map/actions" in paths


def test_get_semantic_map_focus_returns_focus_map(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "get_semantic_map_focus",
        lambda db, actor, **kwargs: {
            "focus_map": {"viewLayer": "room", "orientation": "north-up", "nodes": [], "edges": []},
        },
    )
    client = TestClient(_app())
    response = client.get("/api/v1/semantic-map/focus?view_layer=room")
    assert response.status_code == 200
    body = response.json()
    assert body["focus_map"]["viewLayer"] == "room"


def test_post_semantic_map_select_returns_summary(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "execute_semantic_map_action",
        lambda db, actor, **kwargs: {
            "focus_map": {"viewLayer": "room", "selectedEntityId": "2", "nodes": [], "edges": []},
            "space_summary": {"space_node": {"id": 2, "name": "North Room"}},
        },
    )
    client = TestClient(_app())
    response = client.post(
        "/api/v1/semantic-map/actions",
        json={"action_type": "select", "selected_entity_id": "2"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["focus_map"]["selectedEntityId"] == "2"
    assert body["space_summary"]["space_node"]["id"] == 2


def test_post_semantic_map_drill_returns_focus_map(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "execute_semantic_map_action",
        lambda db, actor, **kwargs: {
            "focus_map": {"viewLayer": "building", "nodes": [{"id": "20", "type": "floor"}], "edges": []},
        },
    )
    client = TestClient(_app())
    response = client.post(
        "/api/v1/semantic-map/actions",
        json={"action_type": "drill", "view_layer": "building", "anchor_id": "20"},
    )
    assert response.status_code == 200
    assert response.json()["focus_map"]["viewLayer"] == "building"




def test_get_entity_inspect_returns_payload(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "get_entity_inspect",
        lambda db, actor, **kwargs: {
            "ok": True,
            "inspect": {"entity": {"id": "5", "name": "Lamp"}, "entity_kind": "device", "actions": []},
        },
    )
    client = TestClient(_app())
    response = client.get("/api/v1/semantic-map/entity-inspect?node_id=5")
    assert response.status_code == 200
    assert response.json()["inspect"]["entity_kind"] == "device"


def test_post_semantic_map_select_returns_entity_inspect(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "execute_semantic_map_action",
        lambda db, actor, **kwargs: {
            "focus_map": {"viewLayer": "room", "selectedEntityId": "9", "nodes": [], "edges": []},
            "space_summary": None,
            "entity_inspect": {"entity": {"id": "9", "name": "NPC"}, "entity_kind": "agent", "actions": []},
        },
    )
    client = TestClient(_app())
    response = client.post(
        "/api/v1/semantic-map/actions",
        json={"action_type": "select", "selected_entity_id": "9"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["entity_inspect"]["entity_kind"] == "agent"

def test_post_semantic_map_unsupported_action(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "execute_semantic_map_action",
        lambda db, actor, **kwargs: {"ok": False, "error": "Unsupported map action: move"},
    )
    client = TestClient(_app())
    response = client.post("/api/v1/semantic-map/actions", json={"action_type": "move"})
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_semantic_map_query_returns_map_patch(monkeypatch):
    monkeypatch.setattr(
        world_interaction.world_interaction_service,
        "query_semantic_map",
        lambda db, actor, query, mode="auto": {
            "mode": "focus",
            "answer": "Found 1 result(s) for F3.",
            "map_patch": {
                "mode": "focus",
                "viewLayer": "campus",
                "highlightedNodeIds": ["20"],
                "focus_map": {"viewLayer": "campus", "nodes": [], "edges": []},
            },
        },
    )
    client = TestClient(_app())
    response = client.post("/api/v1/semantic-map/query", json={"query": "F3"})
    assert response.status_code == 200
    body = response.json()
    assert body["map_patch"]["viewLayer"] == "campus"
    assert body["map_patch"]["highlightedNodeIds"] == ["20"]
