"""Placeable furniture items."""

from .base import WorldThing


class Furniture(WorldThing):
    """Package ``type_code``: ``furniture``; ontology parent ``world_object``."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "furniture"
        super().__init__(name=name, **kwargs)
