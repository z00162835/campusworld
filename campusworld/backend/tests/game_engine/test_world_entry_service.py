import sys
from pathlib import Path
from types import SimpleNamespace

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.game_engine.world_entry_service import WorldEntryService


def test_build_entry_request_uses_portal_spawn(monkeypatch):
    svc = WorldEntryService()
    monkeypatch.setattr(
        svc,
        "resolve_portal",
        lambda world_id, caller_context=None: SimpleNamespace(
            ok=True, world_id=world_id, spawn_key="hicampus_gate", error_code=None, message=None
        ),
    )
    out = svc.build_entry_request("hicampus")
    assert out.ok
    assert out.spawn_key == "hicampus_gate"


def test_build_entry_request_allows_spawn_override(monkeypatch):
    svc = WorldEntryService()
    monkeypatch.setattr(
        svc,
        "resolve_portal",
        lambda world_id, caller_context=None: SimpleNamespace(
            ok=True, world_id=world_id, spawn_key="hicampus_gate", error_code=None, message=None
        ),
    )
    out = svc.build_entry_request("hicampus", "hicampus_bridge")
    assert out.ok
    assert out.spawn_key == "hicampus_bridge"


def test_authorize_entry_denies_when_interact_policy_denied():
    svc = WorldEntryService()
    decision = SimpleNamespace(
        ok=True,
        world_id="hicampus",
        spawn_key="hicampus_gate",
        metadata={"attributes": {"access_locks": {"interact": "perm(world.enter)"}}},
    )
    user = SimpleNamespace(permissions=[], roles=[])
    out = svc.authorize_entry(decision, user=user)
    assert not out.ok
    assert out.error_code == "WORLD_ENTRY_FORBIDDEN"

