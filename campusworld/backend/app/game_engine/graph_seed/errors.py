"""Graph seed pipeline errors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GraphSeedError(Exception):
    error_code: str
    message: str

    def __str__(self) -> str:
        return f"{self.error_code}: {self.message}"
