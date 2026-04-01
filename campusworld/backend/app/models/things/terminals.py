"""Terminal-shaped devices."""

from .base import WorldThing


class AccessTerminal(WorldThing):
    """Package ``type_code``: ``access_terminal``; see entity type registry in HiCampus SPEC."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "access_terminal"
        super().__init__(name=name, **kwargs)
