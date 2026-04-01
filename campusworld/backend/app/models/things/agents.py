"""NPC / agent nodes."""

from .base import WorldThing


class NpcAgent(WorldThing):
    """Package ``type_code``: ``npc_agent``; see entity type registry in HiCampus SPEC."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "npc_agent"
        super().__init__(name=name, **kwargs)
