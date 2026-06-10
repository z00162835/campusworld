"""HiCampus world_environment validator tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.games.hicampus.package.contracts import DataPackageError
from app.games.hicampus.package.validator import validate_data_package


def _write_minimal_hicampus_tree(data: Path, *, world_yaml: str) -> None:
    data.mkdir(parents=True, exist_ok=True)
    (data / "world.yaml").write_text(world_yaml, encoding="utf-8")
    (data / "buildings.yaml").write_text("buildings: []\n", encoding="utf-8")
    (data / "floors.yaml").write_text("floors: []\n", encoding="utf-8")
    (data / "rooms.yaml").write_text("rooms: []\n", encoding="utf-8")
    (data / "relationships.yaml").write_text("relationships: []\n", encoding="utf-8")
    (data / "package_meta.yaml").write_text(
        "package_version: 0.0.0-test\nschema_version: 2\n", encoding="utf-8"
    )
    (data / "entities").mkdir(exist_ok=True)
    (data / "concepts").mkdir(exist_ok=True)
    for rel in (
        "entities/npcs.yaml",
        "entities/items.yaml",
        "entities/zones.yaml",
        "concepts/goals.yaml",
        "concepts/processes.yaml",
        "concepts/rules.yaml",
        "concepts/behaviors.yaml",
        "concepts/skills.yaml",
    ):
        key = rel.split("/")[-1].replace(".yaml", "")
        (data / rel).write_text(f"{key}: []\n", encoding="utf-8")


@pytest.mark.unit
def test_hicampus_package_includes_world_environment():
    root = Path(__file__).resolve().parents[3] / "app" / "games" / "hicampus" / "data"
    snap = validate_data_package(root)
    env = snap.get("world_environment")
    assert isinstance(env, dict)
    assert env.get("id") == "hicampus_environment"
    assert env.get("world_ref") == snap["world"]["id"]
    assert snap.get("warnings") == []


@pytest.mark.unit
def test_validator_rejects_missing_world_environment(tmp_path: Path):
    data = tmp_path / "data"
    _write_minimal_hicampus_tree(
        data,
        world_yaml=(
            "world:\n  id: w1\n  world_id: test\n  type_code: world\n  display_name: T\n"
        ),
    )
    with pytest.raises(DataPackageError) as exc:
        validate_data_package(data)
    assert "world_environment" in str(exc.value.message)


@pytest.mark.unit
def test_validator_rejects_broken_world_ref(tmp_path: Path):
    data = tmp_path / "data"
    _write_minimal_hicampus_tree(
        data,
        world_yaml="""world:
  id: w1
  world_id: test
  type_code: world
  display_name: T
world_environment:
  id: env1
  type_code: world_environment
  display_name: Env
  world_ref: wrong_world
  attributes: {}
  tags: []
""",
    )
    with pytest.raises(DataPackageError) as exc:
        validate_data_package(data)
    assert "world_ref" in str(exc.value.message)
