"""World-level macro environment nodes (weather, outdoor baseline)."""
from .base import WorldThing


class WorldEnvironment(WorldThing):
    """Package ``type_code``: ``world_environment``; one instance per world (trait_class ENV)."""

    def __init__(self, name: str, **kwargs):
        self._node_type = 'world_environment'
        super().__init__(name=name, **kwargs)
