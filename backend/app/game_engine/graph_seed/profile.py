"""World-specific mapping: declarative package type_code -> DB node_types / relationship filter."""

from __future__ import annotations

from typing import FrozenSet, Protocol


class WorldGraphProfile(Protocol):
    """Maps package `type_code` strings to persisted `node_types.type_code` and filters edges."""

    @property
    def world_package_id(self) -> str:
        """Logical world id (e.g. manifest world_id)."""
        ...

    def map_node_type(self, package_type_code: str) -> str:
        """Return DB `node_types.type_code`; raise GraphSeedError if unknown."""
        ...

    @property
    def allowed_relationship_type_codes(self) -> FrozenSet[str]:
        """Relationship `type_code` values this world may instantiate during seed."""
        ...

    @property
    def strict_relationships(self) -> bool:
        """When True, rows outside allowed_relationship_type_codes raise (default False via getattr)."""
        ...
