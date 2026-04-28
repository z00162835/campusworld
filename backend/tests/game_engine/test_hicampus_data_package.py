from pathlib import Path
import shutil

import pytest

from app.game_engine.loader import GameLoader
from app.game_engine.runtime_store import WorldErrorCode
from app.game_engine.world_data_validate import validate_world_data_package
from app.games.hicampus.package.contracts import (
    DataPackageError,
    ERROR_WORLD_DATA_SCHEMA_UNSUPPORTED,
    ERROR_WORLD_DATA_SEMANTIC_CONFLICT,
)
from app.games.hicampus.package.loader import load_package_snapshot
from app.games.hicampus.package.migrator import build_migration_plan, migration_dry_run
from app.games.hicampus.package.validator import validate_data_package


DATA_ROOT = Path(__file__).resolve().parents[2] / "app" / "games" / "hicampus" / "data"


@pytest.mark.game
@pytest.mark.unit
def test_hicampus_exports_get_graph_profile():
    from app.games.hicampus import get_graph_profile

    p = get_graph_profile({})
    assert p.world_package_id == "hicampus"


@pytest.mark.game
@pytest.mark.unit
def test_validate_data_package_success():
    payload = validate_data_package(DATA_ROOT)
    assert payload["world"]["world_id"] == "hicampus"
    assert len(payload["spatial"]["buildings"]) >= 6
    assert len(payload["entities"]["npcs"]) >= 1
    assert len(payload["concepts"]["rules"]) >= 1


@pytest.mark.game
@pytest.mark.unit
def test_validate_relationship_may_reference_entity_id():
    payload = validate_data_package(DATA_ROOT)
    rels = payload["relationships"]
    npc_gate = [r for r in rels if r.get("id") == "rel_npc_located_in_gate"]
    assert len(npc_gate) == 1
    assert npc_gate[0]["source_id"] == "hicampus_npc_security_01"


@pytest.mark.game
@pytest.mark.unit
def test_load_package_snapshot_v2_shape():
    snapshot = load_package_snapshot(DATA_ROOT)
    assert snapshot.world["world_id"] == "hicampus"
    assert "buildings" in snapshot.spatial
    assert "npcs" in snapshot.entities
    assert "rules" in snapshot.concepts


@pytest.mark.game
@pytest.mark.unit
def test_build_migration_plan_has_operations():
    plan = build_migration_plan(DATA_ROOT, from_version="0.0.0", to_version="1.0.0")
    assert len(plan) >= 1
    assert "operations" in plan[0]


@pytest.mark.game
@pytest.mark.unit
def test_migration_dry_run_includes_preview_and_post_validate():
    report = migration_dry_run(DATA_ROOT, "0.0.0", "1.0.0", post_validate=True)
    assert report["current_package_valid"] is True
    assert isinstance(report["operation_preview"], list)


@pytest.mark.game
@pytest.mark.unit
def test_validate_rejects_unsupported_schema_version(tmp_path: Path):
    dst = tmp_path / "data"
    shutil.copytree(DATA_ROOT, dst)
    meta = dst / "package_meta.yaml"
    text = meta.read_text(encoding="utf-8").replace("schema_version: 2", "schema_version: 99")
    meta.write_text(text, encoding="utf-8")
    with pytest.raises(DataPackageError) as exc:
        validate_data_package(dst)
    assert exc.value.error_code == ERROR_WORLD_DATA_SCHEMA_UNSUPPORTED


@pytest.mark.game
@pytest.mark.unit
def test_validate_rejects_unknown_rel_type(tmp_path: Path):
    dst = tmp_path / "data"
    shutil.copytree(DATA_ROOT, dst)
    rel_path = dst / "relationships.yaml"
    text = rel_path.read_text(encoding="utf-8")
    text = text.replace("rel_type_code: located_in", "rel_type_code: not_a_real_rel", 1)
    rel_path.write_text(text, encoding="utf-8")
    with pytest.raises(DataPackageError) as exc:
        validate_data_package(dst)
    assert exc.value.error_code == ERROR_WORLD_DATA_SEMANTIC_CONFLICT


@pytest.mark.game
@pytest.mark.unit
def test_validate_rejects_direction_conflict(tmp_path: Path):
    dst = tmp_path / "data"
    shutil.copytree(DATA_ROOT, dst)
    rel_path = dst / "relationships.yaml"
    text = rel_path.read_text(encoding="utf-8")
    # Create same-source same-direction ambiguity on purpose.
    text = text.replace("direction: southeast", "direction: east", 1)
    rel_path.write_text(text, encoding="utf-8")
    with pytest.raises(DataPackageError) as exc:
        validate_data_package(dst)
    assert exc.value.error_code == ERROR_WORLD_DATA_SEMANTIC_CONFLICT
    assert "direction conflict" in exc.value.message


def _build_loader_with_stubbed_service():
    from unittest.mock import MagicMock

    engine = MagicMock()
    loader = GameLoader(engine)
    loader.repository = MagicMock()
    loader.repository.get_state.return_value = {"status": "not_installed"}
    loader.service = MagicMock()
    loader.service.run_with_job.side_effect = (
        lambda world_id, action, status_before, enter_status, exec_fn, requested_by="system": exec_fn("job-1")
    )
    return loader


@pytest.mark.game
@pytest.mark.unit
def test_loader_load_hicampus_includes_package_snapshot_details():
    loader = _build_loader_with_stubbed_service()
    result = loader.load_game("hicampus")
    assert result["ok"] is True
    package = result["details"].get("package", {})
    assert package.get("world_data_validated") is True
    assert package.get("snapshot_loaded") is True
    assert package.get("snapshot_counts", {}).get("entities", {}).get("npcs", 0) >= 1


@pytest.mark.game
@pytest.mark.unit
def test_loader_returns_schema_unsupported_from_package(tmp_path: Path):
    game_dir = tmp_path / "hicampus"
    shutil.copytree(
        Path(__file__).resolve().parents[2] / "app" / "games" / "hicampus",
        game_dir,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    meta = game_dir / "data" / "package_meta.yaml"
    meta.write_text(
        meta.read_text(encoding="utf-8").replace("schema_version: 2", "schema_version: 99"),
        encoding="utf-8",
    )
    loader = _build_loader_with_stubbed_service()
    loader.search_paths = [tmp_path]
    result = loader.load_game("hicampus")
    assert result["ok"] is False
    assert result["error_code"] == WorldErrorCode.WORLD_DATA_SCHEMA_UNSUPPORTED.value


@pytest.mark.game
@pytest.mark.unit
def test_loader_returns_data_unavailable_when_missing_required_file(tmp_path: Path):
    game_dir = tmp_path / "hicampus"
    game_dir.mkdir()
    (game_dir / "__init__.py").write_text(
        "from .game import Game\n\ndef get_game_instance():\n    return Game()\n",
        encoding="utf-8",
    )
    (game_dir / "game.py").write_text(
        "from app.game_engine.base import BaseGame\nclass Game(BaseGame):\n"
        "    def __init__(self):\n        super().__init__(name='hicampus', version='1.0.0')\n"
        "    def initialize_game(self):\n        return True\n",
        encoding="utf-8",
    )
    (game_dir / "manifest.yaml").write_text(
        "world_id: hicampus\nversion: 1.0.0\napi_version: v2\ndata_dir: data\n",
        encoding="utf-8",
    )
    (game_dir / "data").mkdir()
    (game_dir / "data" / "world.yaml").write_text("world: {id: hicampus_world, world_id: hicampus}\n", encoding="utf-8")

    loader = _build_loader_with_stubbed_service()
    loader.search_paths = [tmp_path]
    result = loader.load_game("hicampus")
    assert result["ok"] is False
    assert result["error_code"] == WorldErrorCode.WORLD_DATA_UNAVAILABLE.value


@pytest.mark.game
@pytest.mark.unit
def test_validate_world_data_package_resolves_hicampus_module():
    out = validate_world_data_package("hicampus", DATA_ROOT)
    assert out is not None
    assert out["world"]["world_id"] == "hicampus"
