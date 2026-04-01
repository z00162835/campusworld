"""
World-scoped migration utilities for F02 data package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .contracts import DataPackageError, ERROR_WORLD_DATA_INVALID
from .validator import validate_data_package


def list_migration_files(migrations_dir: Path) -> List[Path]:
    if not migrations_dir.exists():
        return []
    return sorted([p for p in migrations_dir.iterdir() if p.is_file() and p.suffix in {".yaml", ".yml"}])


def load_migration(path: Path) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"invalid migration file: {path.name}") from exc
    if not isinstance(data, dict):
        raise DataPackageError(ERROR_WORLD_DATA_INVALID, f"invalid migration body: {path.name}")
    return data


def _semver_tuple(version: str) -> tuple:
    s = str(version).strip().lstrip("vV")
    parts = s.split(".")
    nums: List[int] = []
    for p in parts[:4]:
        if p.isdigit():
            nums.append(int(p))
        else:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])


def _filter_migrations_by_range(
    migrations: List[Dict[str, Any]], from_version: str, to_version: str
) -> List[Dict[str, Any]]:
    lo = _semver_tuple(from_version)
    hi = _semver_tuple(to_version)
    if hi < lo:
        return []
    selected: List[Dict[str, Any]] = []
    for m in migrations:
        mf = _semver_tuple(str(m.get("from_version", "0.0.0")))
        mt = _semver_tuple(str(m.get("to_version", "0.0.0")))
        if lo <= mf and mt <= hi:
            selected.append(m)
    return sorted(selected, key=lambda x: _semver_tuple(str(x.get("to_version", "0.0.0"))))


def build_migration_plan(
    data_root: Path,
    from_version: Optional[str] = None,
    to_version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List parsed migrations; optionally restrict to [from_version, to_version] semver window on
    migration from_version/to_version fields.
    """
    migrations_dir = data_root / "migrations"
    result: List[Dict[str, Any]] = []
    for path in list_migration_files(migrations_dir):
        m = load_migration(path)
        result.append(
            {
                "name": path.name,
                "from_version": m.get("from_version"),
                "to_version": m.get("to_version"),
                "operations": m.get("operations", []),
                "rollback": m.get("rollback", []),
            }
        )
    result.sort(key=lambda x: _semver_tuple(str(x.get("to_version", "0.0.0"))))
    if from_version is not None and to_version is not None:
        result = _filter_migrations_by_range(result, from_version, to_version)
    return result


def migration_dry_run(
    data_root: Path,
    from_version: str,
    to_version: str,
    *,
    post_validate: bool = True,
) -> Dict[str, Any]:
    """
    Preview operations for migrations in range without mutating files or DB.
    Optionally runs validate_data_package on the current tree (post-validate hook for baseline).
    """
    plan = build_migration_plan(data_root, from_version=from_version, to_version=to_version)
    preview: List[Dict[str, Any]] = []
    for m in plan:
        for op in m.get("operations", []) or []:
            preview.append({"migration": m["name"], "operation": op})
    report: Dict[str, Any] = {
        "from_version": from_version,
        "to_version": to_version,
        "selected_migrations": [m["name"] for m in plan],
        "operation_preview": preview,
    }
    if post_validate:
        try:
            validate_data_package(data_root)
            report["current_package_valid"] = True
        except DataPackageError as e:
            report["current_package_valid"] = False
            report["current_package_error_code"] = e.error_code
            report["current_package_error_message"] = e.message
    return report
