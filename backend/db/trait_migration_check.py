"""
Trait migration pre/post checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from sqlalchemy import text

from app.core.database import db_session_context


@dataclass
class TraitCheckReport:
    total_nodes: int
    total_relationships: int
    node_type_mismatch: int
    relationship_type_mismatch: int
    null_or_negative_masks: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_nodes": self.total_nodes,
            "total_relationships": self.total_relationships,
            "node_type_mismatch": self.node_type_mismatch,
            "relationship_type_mismatch": self.relationship_type_mismatch,
            "null_or_negative_masks": self.null_or_negative_masks,
        }


def run_trait_migration_checks() -> TraitCheckReport:
    with db_session_context() as session:
        total_nodes = int(session.execute(text("SELECT COUNT(*) FROM nodes")).scalar() or 0)
        total_relationships = int(session.execute(text("SELECT COUNT(*) FROM relationships")).scalar() or 0)
        node_type_mismatch = int(
            session.execute(
                text(
                    """
SELECT COUNT(*)
FROM nodes n
JOIN node_types nt ON nt.type_code = n.type_code
WHERE n.trait_class IS DISTINCT FROM nt.trait_class
   OR n.trait_mask IS DISTINCT FROM nt.trait_mask
                    """
                )
            ).scalar()
            or 0
        )
        relationship_type_mismatch = int(
            session.execute(
                text(
                    """
SELECT COUNT(*)
FROM relationships r
JOIN relationship_types rt ON rt.type_code = r.type_code
WHERE r.trait_class IS DISTINCT FROM rt.trait_class
   OR r.trait_mask IS DISTINCT FROM rt.trait_mask
                    """
                )
            ).scalar()
            or 0
        )
        null_or_negative_masks = int(
            session.execute(
                text(
                    """
SELECT
    (SELECT COUNT(*) FROM node_types WHERE trait_mask IS NULL OR trait_mask < 0) +
    (SELECT COUNT(*) FROM nodes WHERE trait_mask IS NULL OR trait_mask < 0) +
    (SELECT COUNT(*) FROM relationship_types WHERE trait_mask IS NULL OR trait_mask < 0) +
    (SELECT COUNT(*) FROM relationships WHERE trait_mask IS NULL OR trait_mask < 0)
                    """
                )
            ).scalar()
            or 0
        )
        return TraitCheckReport(
            total_nodes=total_nodes,
            total_relationships=total_relationships,
            node_type_mismatch=node_type_mismatch,
            relationship_type_mismatch=relationship_type_mismatch,
            null_or_negative_masks=null_or_negative_masks,
        )
