"""Level-3 typeclass base for graph-seeded world entities (Evennia-style).

See HiCampus SPEC (features/) entity type registry for type_code ↔ ontology mapping.

Examine / ``get_display_desc`` uses the same schema-driven fallback as all
``DefaultObject`` subclasses (see ``DefaultObject.build_synthetic_look_desc``).
"""

from __future__ import annotations

from app.models.base import DefaultObject


class WorldThing(DefaultObject):
    """Shared base for HiCampus entity node typeclasses; room-list hooks, etc."""
