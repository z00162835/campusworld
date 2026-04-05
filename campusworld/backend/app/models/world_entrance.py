"""
Evennia-style world exit: a Node in the singularity room whose description is the world's facade.

type_code ``world_entrance`` — distinct from graph-seeded ``world`` metadata nodes.
"""

from .base import DefaultObject


class WorldEntrance(DefaultObject):
    """
    Portal from SingularityRoom into a world's gate room.

    Attributes (JSONB) typically include:
    - portal_world_id, portal_spawn_key, portal_enabled
    - destination_node_id: int room Node id of gate (when resolved)
    - access_locks: view / interact
    """

    def __init__(self, name: str, **kwargs):
        self._node_type = "world_entrance"
        super().__init__(name=name, **kwargs)

