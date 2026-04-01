"""Logical zones / geofences."""

from .base import WorldThing


class LogicalZone(WorldThing):
    """Package ``type_code``: ``logical_zone``; see entity type registry in HiCampus SPEC."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "logical_zone"
        super().__init__(name=name, **kwargs)
