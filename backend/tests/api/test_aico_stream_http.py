"""HTTP SSE streaming behavior for AICO decision-center queries."""
from __future__ import annotations

import json
import threading
import time
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
    app.include_router(world_interaction.decision_center_router, prefix="/api/v1")
    app.dependency_overrides[get_current_http_user] = _test_user
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return app


def test_stream_yields_delta_before_worker_finishes(monkeypatch):
    """First body delta should arrive while the tick worker is still running."""
    gate = threading.Event()
    deltas_seen: list[str] = []

    def fake_stream(actor, query):
        line_queue: list[str] = []

        def worker():
            time.sleep(0.05)
            line_queue.append(json.dumps({"kind": "delta", "text": "early"}, ensure_ascii=False))
            gate.wait(timeout=2.0)
            line_queue.append(None)

        threading.Thread(target=worker, daemon=True).start()
        yield 'data: {"kind":"meta","scope":"stream","stream_id":"t1"}\n\n'
        while True:
            if line_queue:
                item = line_queue.pop(0)
                if item is None:
                    break
                yield f"data: {item}\n\n"
            else:
                time.sleep(0.01)

    monkeypatch.setattr(world_interaction.world_interaction_service, "stream_aico_query", fake_stream)
    client = TestClient(_app())

    with client.stream(
        "POST",
        "/api/v1/decision-center/query/stream",
        json={"session_id": "world_1", "query": "hello", "mode": "aico"},
    ) as response:
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "no-cache"
        buffer = ""
        for chunk in response.iter_text():
            buffer += chunk
            if '"kind": "delta"' in buffer or '"kind":"delta"' in buffer:
                deltas_seen.append("delta")
                gate.set()
                break
        gate.set()

    assert deltas_seen, "expected a delta event before stream closed"
