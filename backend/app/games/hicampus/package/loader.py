"""
PackageSnapshotV2 loader for HiCampus declarative data package.
"""

from __future__ import annotations

from pathlib import Path

from .contracts import PackageSnapshotV2
from .validator import validate_data_package


def load_package_snapshot(data_root: Path) -> PackageSnapshotV2:
    payload = validate_data_package(data_root)
    return PackageSnapshotV2(
        world=payload["world"],
        spatial=payload["spatial"],
        entities=payload["entities"],
        concepts=payload["concepts"],
        relationships=payload["relationships"],
        meta=payload["meta"],
    )

