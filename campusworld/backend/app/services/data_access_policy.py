"""
Data access policy: parse account attributes and build SQLAlchemy filters.

No admin short-circuit: callers pass policy derived only from `user_attrs`;
wide access is achieved via permissive templates in seed data, not role checks.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, false, not_, or_
from sqlalchemy.orm import Query
from sqlalchemy.sql import ColumnElement

from app.models.graph import Node, NodeType, Relationship, RelationshipType
from app.schemas.data_access import DataAccessV1, data_access_from_user_attrs


def load_policy(user_attrs: Dict[str, Any]) -> Tuple[Optional[DataAccessV1], bool]:
    """
    Returns (policy, deny_all).
    deny_all True if missing/invalid data_access or wrong version.
    """
    pol = data_access_from_user_attrs(user_attrs or {})
    if pol is None:
        return None, True
    if pol.version != 1:
        return pol, True
    return pol, False


def node_policy_sql(node_column, policy: DataAccessV1) -> ColumnElement:
    """Boolean SQL expression for a single Node row (used for Node and aliased Node)."""
    pt = policy.permission_template
    parts: List[ColumnElement] = []

    wid = node_column.attributes["world_id"].astext

    # Layer 1: denied worlds
    if policy.denied_world_ids:
        denied_ws = [str(x) for x in policy.denied_world_ids]
        # Reject only when world_id is set and matches a denied id; NULL is not "in" denied.
        parts.append(or_(wid.is_(None), not_(wid.in_(denied_ws))))

    # Layer 1: allow world_ids
    if pt.world_ids is not None and len(pt.world_ids) > 0:
        allow_ws = [str(x) for x in pt.world_ids]
        parts.append(wid.in_(allow_ws))

    if pt.exclude_nodes_without_world_id:
        parts.append(and_(wid.isnot(None), wid != ""))

    # Layer 2: type allowlist
    if pt.type_codes is not None and len(pt.type_codes) > 0:
        parts.append(node_column.type_code.in_(pt.type_codes))

    if policy.denied_type_codes:
        parts.append(not_(node_column.type_code.in_(policy.denied_type_codes)))

    # Layer 3: node allowlist (rare)
    if pt.node_ids is not None and len(pt.node_ids) > 0:
        parts.append(node_column.id.in_(pt.node_ids))

    if policy.denied_nodes:
        parts.append(not_(node_column.id.in_(policy.denied_nodes)))

    if not parts:
        return true_expr()
    return and_(*parts)


def true_expr() -> ColumnElement:
    from sqlalchemy import true

    return true()


def apply_node_read_policy(query: Query, policy: Optional[DataAccessV1], deny_all: bool) -> Query:
    if deny_all or policy is None:
        return query.filter(false())
    return query.filter(node_policy_sql(Node, policy))


def apply_world_scoped_node_read_policy(
    query: Query,
    policy: Optional[DataAccessV1],
    deny_all: bool,
    world_id_path: str,
) -> Query:
    """Apply data_access policy on top of an existing world-scoped node query."""
    if deny_all or policy is None:
        return query.filter(false())
    # Path world must be allowed when template restricts world_ids
    pt = policy.permission_template
    if pt.world_ids is not None and len(pt.world_ids) > 0:
        if str(world_id_path) not in [str(x) for x in pt.world_ids]:
            return query.filter(false())
    if str(world_id_path) in [str(x) for x in policy.denied_world_ids]:
        return query.filter(false())
    return query.filter(node_policy_sql(Node, policy))


def relationship_policy_sql(
    rel_column,
    source_node_column,
    target_node_column,
    policy: DataAccessV1,
) -> ColumnElement:
    parts: List[ColumnElement] = []

    pt = policy.permission_template
    if pt.relationships_codes is not None and len(pt.relationships_codes) > 0:
        parts.append(rel_column.type_code.in_(pt.relationships_codes))
    if policy.denied_relationships_codes:
        parts.append(not_(rel_column.type_code.in_(policy.denied_relationships_codes)))

    parts.append(node_policy_sql(source_node_column, policy))
    parts.append(node_policy_sql(target_node_column, policy))
    return and_(*parts)


def apply_relationship_read_policy(
    query: Query,
    policy: Optional[DataAccessV1],
    deny_all: bool,
    source_alias: Any,
    target_alias: Any,
) -> Query:
    if deny_all or policy is None:
        return query.filter(false())
    return query.filter(
        relationship_policy_sql(Relationship, source_alias, target_alias, policy)
    )


def node_row_visible(node: Node, policy: Optional[DataAccessV1], deny_all: bool) -> bool:
    if deny_all or policy is None:
        return False
    # Mirror node_policy_sql in Python for writes and single-row checks.
    pt = policy.permission_template
    attrs = dict(node.attributes or {})
    wid = attrs.get("world_id")
    wid_s = None if wid is None else str(wid)

    if policy.denied_world_ids and wid_s is not None:
        try:
            if int(wid_s) in policy.denied_world_ids:
                return False
        except ValueError:
            pass

    if pt.world_ids is not None and len(pt.world_ids) > 0:
        if wid_s is None or wid_s not in [str(x) for x in pt.world_ids]:
            return False

    if pt.exclude_nodes_without_world_id:
        if wid_s is None or wid_s == "":
            return False

    if pt.type_codes is not None and len(pt.type_codes) > 0:
        if node.type_code not in pt.type_codes:
            return False

    if policy.denied_type_codes and node.type_code in policy.denied_type_codes:
        return False

    if pt.node_ids is not None and len(pt.node_ids) > 0:
        if node.id not in pt.node_ids:
            return False

    if policy.denied_nodes and node.id in policy.denied_nodes:
        return False

    return True


def relationship_row_visible(
    rel: Relationship,
    source: Node,
    target: Node,
    policy: Optional[DataAccessV1],
    deny_all: bool,
) -> bool:
    if deny_all or policy is None:
        return False
    pt = policy.permission_template
    if pt.relationships_codes is not None and len(pt.relationships_codes) > 0:
        if rel.type_code not in pt.relationships_codes:
            return False
    if policy.denied_relationships_codes and rel.type_code in policy.denied_relationships_codes:
        return False
    return node_row_visible(source, policy, False) and node_row_visible(target, policy, False)


def proposed_node_visible(
    type_code: str,
    attributes: Optional[Dict[str, Any]],
    policy: Optional[DataAccessV1],
    deny_all: bool,
    node_id: Optional[int] = None,
) -> bool:
    """Validate a would-be node (POST body) against policy; node_id None on create."""
    if deny_all or policy is None:
        return False
    pt = policy.permission_template
    attrs = dict(attributes or {})
    wid = attrs.get("world_id")
    wid_s = None if wid is None else str(wid)

    if policy.denied_world_ids and wid_s is not None:
        try:
            if int(wid_s) in policy.denied_world_ids:
                return False
        except ValueError:
            pass

    if pt.world_ids is not None and len(pt.world_ids) > 0:
        if wid_s is None or wid_s not in [str(x) for x in pt.world_ids]:
            return False

    if pt.exclude_nodes_without_world_id:
        if wid_s is None or wid_s == "":
            return False

    if pt.type_codes is not None and len(pt.type_codes) > 0:
        if type_code not in pt.type_codes:
            return False

    if policy.denied_type_codes and type_code in policy.denied_type_codes:
        return False

    if node_id is not None:
        if pt.node_ids is not None and len(pt.node_ids) > 0:
            if node_id not in pt.node_ids:
                return False
        if policy.denied_nodes and node_id in policy.denied_nodes:
            return False

    return True


def proposed_relationship_visible(
    type_code: str,
    source: Node,
    target: Node,
    policy: Optional[DataAccessV1],
    deny_all: bool,
) -> bool:
    if deny_all or policy is None:
        return False
    pt = policy.permission_template
    if pt.relationships_codes is not None and len(pt.relationships_codes) > 0:
        if type_code not in pt.relationships_codes:
            return False
    if policy.denied_relationships_codes and type_code in policy.denied_relationships_codes:
        return False
    return node_row_visible(source, policy, False) and node_row_visible(target, policy, False)


def ontology_type_visible(type_code: str, policy: Optional[DataAccessV1], deny_all: bool) -> bool:
    """Hide ontology rows for denied node or relationship type codes when policy applies."""
    if deny_all or policy is None:
        return False
    if policy.denied_type_codes and type_code in policy.denied_type_codes:
        return False
    return True


def ontology_relationship_type_visible(type_code: str, policy: Optional[DataAccessV1], deny_all: bool) -> bool:
    if deny_all or policy is None:
        return False
    if policy.denied_relationships_codes and type_code in policy.denied_relationships_codes:
        return False
    return True


def apply_ontology_node_type_read_policy(query: Query, policy: Optional[DataAccessV1], deny_all: bool) -> Query:
    if deny_all or policy is None:
        return query.filter(false())
    if policy.denied_type_codes:
        return query.filter(not_(NodeType.type_code.in_(policy.denied_type_codes)))
    return query


def apply_ontology_relationship_type_read_policy(
    query: Query, policy: Optional[DataAccessV1], deny_all: bool
) -> Query:
    if deny_all or policy is None:
        return query.filter(false())
    if policy.denied_relationships_codes:
        return query.filter(not_(RelationshipType.type_code.in_(policy.denied_relationships_codes)))
    return query
