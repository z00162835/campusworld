"""
Dual-model (entity + concept) contracts for HiCampus world data package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


class DataPackageError(Exception):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


ERROR_WORLD_DATA_UNAVAILABLE = "WORLD_DATA_UNAVAILABLE"
ERROR_WORLD_DATA_INVALID = "WORLD_DATA_INVALID"
ERROR_WORLD_DATA_SCHEMA_UNSUPPORTED = "WORLD_DATA_SCHEMA_UNSUPPORTED"
ERROR_WORLD_DATA_REFERENCE_BROKEN = "WORLD_DATA_REFERENCE_BROKEN"
ERROR_WORLD_DATA_BASELINE_MISMATCH = "WORLD_DATA_BASELINE_MISMATCH"
ERROR_WORLD_DATA_SEMANTIC_CONFLICT = "WORLD_DATA_SEMANTIC_CONFLICT"


@dataclass
class PackageSnapshotV2:
    world: Dict[str, Any]
    spatial: Dict[str, List[Dict[str, Any]]]
    entities: Dict[str, List[Dict[str, Any]]]
    concepts: Dict[str, List[Dict[str, Any]]]
    relationships: List[Dict[str, Any]]
    meta: Dict[str, Any] = field(default_factory=dict)

