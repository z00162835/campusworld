"""Level-3 typeclass base for graph-seeded world entities (Evennia-style).

See HiCampus SPEC (features/) entity type registry for type_code ↔ ontology mapping.
"""

from app.models.base import DefaultObject


class WorldThing(DefaultObject):
    """Shared base for HiCampus entity node typeclasses; thin hooks only."""
