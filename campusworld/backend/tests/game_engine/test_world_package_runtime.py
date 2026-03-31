import contextlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.game_engine.loader import GameLoader
from app.game_engine.runtime_store import (
    OperationResult,
    WorldErrorCode,
    WorldInstallerService,
    WorldRuntimeStatus,
)


@pytest.mark.game
@pytest.mark.unit
def test_operation_result_to_dict_contract():
    result = OperationResult(
        ok=True,
        world_id="hicampus",
        job_id="job-1",
        status_before=WorldRuntimeStatus.NOT_INSTALLED.value,
        status_after=WorldRuntimeStatus.INSTALLED.value,
        error_code=None,
        message="world loaded",
        details={"version": "0.1.0"},
    )

    data = result.to_dict()
    assert set(data.keys()) == {
        "ok",
        "world_id",
        "job_id",
        "status_before",
        "status_after",
        "error_code",
        "message",
        "details",
    }
    assert data["world_id"] == "hicampus"
    assert data["status_after"] == WorldRuntimeStatus.INSTALLED.value


def _build_loader_with_stubbed_service():
    engine = MagicMock()
    loader = GameLoader(engine)
    loader.repository = MagicMock()
    loader.repository.get_state.return_value = {
        "status": WorldRuntimeStatus.NOT_INSTALLED.value
    }
    loader.service = MagicMock()
    loader.service.run_with_job.side_effect = (
        lambda world_id, action, status_before, enter_status, exec_fn, requested_by="system": exec_fn("job-1")
    )
    return loader, engine


@pytest.mark.game
@pytest.mark.unit
def test_discover_games_filters_invalid_manifest(tmp_path: Path):
    loader, _engine = _build_loader_with_stubbed_service()
    loader.search_paths = [tmp_path]

    valid = tmp_path / "hicampus"
    valid.mkdir()
    (valid / "__init__.py").write_text("", encoding="utf-8")
    (valid / "game.py").write_text("", encoding="utf-8")
    (valid / "manifest.yaml").write_text(
        "world_id: hicampus\nversion: 0.1.0\napi_version: v1\ndata_dir: data\n",
        encoding="utf-8",
    )

    no_manifest = tmp_path / "bad_world_a"
    no_manifest.mkdir()
    (no_manifest / "__init__.py").write_text("", encoding="utf-8")
    (no_manifest / "game.py").write_text("", encoding="utf-8")

    invalid_manifest = tmp_path / "bad_world_b"
    invalid_manifest.mkdir()
    (invalid_manifest / "__init__.py").write_text("", encoding="utf-8")
    (invalid_manifest / "game.py").write_text("", encoding="utf-8")
    (invalid_manifest / "manifest.yaml").write_text(
        "world_id: bad_world_b\nversion: 0.1.0\n",
        encoding="utf-8",
    )

    discovered = loader.discover_games()
    assert "hicampus" in discovered
    assert "bad_world_a" not in discovered
    assert "bad_world_b" not in discovered


@pytest.mark.game
@pytest.mark.unit
def test_load_game_manifest_invalid_returns_error(tmp_path: Path):
    loader, _engine = _build_loader_with_stubbed_service()
    loader.search_paths = [tmp_path]

    broken = tmp_path / "hicampus"
    broken.mkdir()
    (broken / "__init__.py").write_text("", encoding="utf-8")
    (broken / "game.py").write_text("", encoding="utf-8")
    (broken / "manifest.yaml").write_text("world_id: hicampus\n", encoding="utf-8")

    result = loader.load_game("hicampus")
    assert result["ok"] is False
    assert result["error_code"] == WorldErrorCode.WORLD_MANIFEST_INVALID.value


@pytest.mark.game
@pytest.mark.unit
def test_unload_game_executes_stop_unregister_and_cleanup():
    loader, engine = _build_loader_with_stubbed_service()
    engine.unregister_game.return_value = True

    game = MagicMock()
    game.stop.return_value = True
    loader.loaded_games["hicampus"] = game
    loader.game_modules["hicampus"] = object()

    result = loader.unload_game("hicampus")

    game.stop.assert_called_once()
    engine.unregister_game.assert_called_once_with("hicampus")
    assert "hicampus" not in loader.loaded_games
    assert "hicampus" not in loader.game_modules
    assert result["ok"] is True
    assert result["status_after"] == WorldRuntimeStatus.NOT_INSTALLED.value


@pytest.mark.game
@pytest.mark.unit
def test_run_with_job_failure_flow_marks_broken(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.committed = False
            self.rolled_back = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    fake_session = FakeSession()

    @contextlib.contextmanager
    def fake_db_session_context():
        yield fake_session

    class FakeRepo:
        def __init__(self):
            self.states = []
            self.finished = []

        def get_state_for_update(self, session, world_id):
            return {"world_id": world_id, "status": "not_installed"}

        def create_job(self, world_id, action, requested_by="system", session=None):
            return "job-1"

        def upsert_state(self, world_id, status, **kwargs):
            self.states.append(status)

        def append_job_event(self, job_id, stage, payload, session=None):
            return None

        def finish_job(self, job_id, success, error_code, summary, session=None):
            self.finished.append((success, error_code))

    import app.game_engine.runtime_store as runtime_store_module

    monkeypatch.setattr(runtime_store_module, "db_session_context", fake_db_session_context)
    repo = FakeRepo()
    service = WorldInstallerService(repo)

    def fail_exec(_job_id):
        return OperationResult(
            ok=False,
            world_id="hicampus",
            status_before=WorldRuntimeStatus.LOADING.value,
            status_after=WorldRuntimeStatus.FAILED.value,
            message="load failed",
            error_code=WorldErrorCode.WORLD_LOAD_FAILED.value,
            details={},
        )

    result = service.run_with_job(
        world_id="hicampus",
        action="load",
        status_before=WorldRuntimeStatus.NOT_INSTALLED.value,
        enter_status=WorldRuntimeStatus.LOADING.value,
        exec_fn=fail_exec,
    )

    assert result.ok is False
    assert result.status_after == WorldRuntimeStatus.BROKEN.value
    assert WorldRuntimeStatus.FAILED.value in repo.states
    assert WorldRuntimeStatus.BROKEN.value in repo.states
    assert repo.finished[-1] == (False, WorldErrorCode.WORLD_LOAD_FAILED.value)
    assert fake_session.committed is True


@pytest.mark.game
@pytest.mark.unit
def test_run_with_job_integrity_error_returns_world_busy(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.committed = False
            self.rolled_back = False

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    fake_session = FakeSession()

    @contextlib.contextmanager
    def fake_db_session_context():
        yield fake_session

    class BusyRepo:
        def get_state_for_update(self, session, world_id):
            return {"world_id": world_id, "status": "loading"}

        def create_job(self, world_id, action, requested_by="system", session=None):
            raise IntegrityError("insert", {"world_id": world_id}, Exception("duplicate key"))

    import app.game_engine.runtime_store as runtime_store_module

    monkeypatch.setattr(runtime_store_module, "db_session_context", fake_db_session_context)
    service = WorldInstallerService(BusyRepo())

    result = service.run_with_job(
        world_id="hicampus",
        action="load",
        status_before=WorldRuntimeStatus.LOADING.value,
        enter_status=WorldRuntimeStatus.LOADING.value,
        exec_fn=lambda _job_id: OperationResult(
            ok=True,
            world_id="hicampus",
            status_before=WorldRuntimeStatus.LOADING.value,
            status_after=WorldRuntimeStatus.INSTALLED.value,
            message="ok",
        ),
    )

    assert result.ok is False
    assert result.error_code == WorldErrorCode.WORLD_BUSY.value
    assert fake_session.rolled_back is True
