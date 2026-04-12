from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, aliased

from app.api.v1.dependencies import APIPrincipal, require_api_permission
from app.core.database import get_db
from app.models.graph import Node, NodeType, Relationship, RelationshipType
from app.schemas.data_access import DataAccessV1
from app.schemas.graph_ontology import NodeIn, RelationshipIn
from app.services.data_access_policy import (
    apply_node_read_policy,
    apply_relationship_read_policy,
    apply_world_scoped_node_read_policy,
    load_policy,
    node_row_visible,
    proposed_node_visible,
    proposed_relationship_visible,
    relationship_row_visible,
)

router = APIRouter(prefix="/graph", tags=["graph"])


def _policy_from_principal(principal: APIPrincipal) -> Tuple[Optional[DataAccessV1], bool]:
    return load_policy(principal.user_attrs or {})


def _forbidden_data_access(request: Request) -> JSONResponse:
    return _problem(403, "Forbidden", "Data access policy denies this operation.", request)


def _problem(status_code: int, title: str, detail: str, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status_code,
            "detail": detail,
            "instance": str(request.url.path),
        },
    )


def _split_tags(tags_any: Optional[str]) -> List[str]:
    if not tags_any:
        return []
    tags = []
    for tag in tags_any.split(","):
        t = tag.strip()
        if t and t not in tags:
            tags.append(t)
    return tags


def _apply_tags_any_filter(query, tags_column, tags_any: Optional[str]):
    tags = _split_tags(tags_any)
    if not tags:
        return query
    # tags_any means OR semantics across candidate tags.
    return query.filter(or_(*[tags_column.contains([tag]) for tag in tags]))


def _validate_query(
    name_eq: Optional[str],
    name_like: Optional[str],
    tags_any: Optional[str],
    request: Request,
) -> Optional[JSONResponse]:
    if name_eq is not None and name_eq == "":
        return _problem(400, "Bad Request", "name_eq must not be empty.", request)
    if name_like is not None and not name_like.strip():
        return _problem(400, "Bad Request", "name_like must not be blank.", request)
    if tags_any is not None and not _split_tags(tags_any):
        return _problem(400, "Bad Request", "tags_any resolves to empty set.", request)
    return None


def _scope_node_world_conflict(attrs: Dict[str, Any], world_id: str) -> bool:
    current = (attrs or {}).get("world_id")
    return current is not None and str(current) != str(world_id)


@router.get("/nodes")
def list_nodes(
    request: Request,
    type_code: Optional[str] = None,
    name_eq: Optional[str] = None,
    name_like: Optional[str] = None,
    tags_any: Optional[str] = None,
    trait_class: Optional[str] = None,
    required_any_mask: int = 0,
    required_all_mask: int = 0,
    is_active: Optional[bool] = None,
    is_public: Optional[bool] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    err = _validate_query(name_eq, name_like, tags_any, request)
    if err:
        return err
    query = db.query(Node)
    query = apply_node_read_policy(query, policy, deny_all)
    if type_code:
        query = query.filter(Node.type_code == type_code)
    if name_eq:
        query = query.filter(Node.name == name_eq)
    if name_like:
        query = query.filter(Node.name.ilike(f"%{name_like}%"))
    if trait_class:
        query = query.filter(Node.trait_class == trait_class)
    query = Node.filter_by_trait_any(query, required_any_mask)
    query = Node.filter_by_trait_all(query, required_all_mask)
    if is_active is not None:
        query = query.filter(Node.is_active == is_active)
    if is_public is not None:
        query = query.filter(Node.is_public == is_public)
    query = _apply_tags_any_filter(query, Node.tags, tags_any)

    total = query.count()
    items = [row.to_dict() for row in query.offset(offset).limit(limit).all()]
    return {"items": items, "page": {"total": total, "offset": offset, "limit": limit}}


@router.post("/nodes", status_code=status.HTTP_201_CREATED)
def create_node(
    payload: NodeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    node_type = db.query(NodeType).filter(NodeType.type_code == payload.type_code).first()
    if not node_type:
        return _problem(400, "Bad Request", f"unknown node type `{payload.type_code}`.", request)

    if not proposed_node_visible(payload.type_code, payload.attributes, policy, deny_all):
        return _forbidden_data_access(request)

    row = Node(
        type_id=node_type.id,
        type_code=payload.type_code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        is_public=payload.is_public,
        access_level=payload.access_level,
        # Instance trait fields are derived from type_code (F01/F10 contract).
        trait_class=node_type.trait_class,
        trait_mask=int(node_type.trait_mask or 0),
        location_id=payload.location_id,
        home_id=payload.home_id,
        attributes=payload.attributes,
        tags=payload.tags,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.get("/nodes/{node_id}")
def get_node(
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Node).filter(Node.id == node_id).first()
    if not row:
        return _problem(404, "Not Found", f"node `{node_id}` not found.", request)
    if not node_row_visible(row, policy, deny_all):
        return _problem(404, "Not Found", f"node `{node_id}` not found.", request)
    return row.to_dict()


@router.patch("/nodes/{node_id}")
def patch_node(
    node_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Node).filter(Node.id == node_id).first()
    if not row:
        return _problem(404, "Not Found", f"node `{node_id}` not found.", request)
    if not node_row_visible(row, policy, deny_all):
        return _forbidden_data_access(request)

    allowed_fields = {
        "name",
        "description",
        "is_active",
        "is_public",
        "access_level",
        "location_id",
        "home_id",
        "attributes",
        "tags",
    }
    for key, value in payload.items():
        if key in allowed_fields:
            setattr(row, key, value)
    # Re-evaluate after patch (attributes/type may change)
    db.flush()
    if not node_row_visible(row, policy, deny_all):
        db.rollback()
        return _forbidden_data_access(request)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Node).filter(Node.id == node_id).first()
    if not row:
        return _problem(404, "Not Found", f"node `{node_id}` not found.", request)
    if not node_row_visible(row, policy, deny_all):
        return _forbidden_data_access(request)
    db.delete(row)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@router.get("/relationships")
def list_relationships(
    request: Request,
    type_code: Optional[str] = None,
    name_eq: Optional[str] = None,
    name_like: Optional[str] = None,
    tags_any: Optional[str] = None,
    trait_class: Optional[str] = None,
    is_active: Optional[bool] = None,
    source_id: Optional[int] = None,
    target_id: Optional[int] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    err = _validate_query(name_eq, name_like, tags_any, request)
    if err:
        return err
    source_n = aliased(Node)
    target_n = aliased(Node)
    query = (
        db.query(Relationship)
        .join(RelationshipType, RelationshipType.type_code == Relationship.type_code)
        .join(source_n, source_n.id == Relationship.source_id)
        .join(target_n, target_n.id == Relationship.target_id)
    )
    query = apply_relationship_read_policy(query, policy, deny_all, source_n, target_n)
    if type_code:
        query = query.filter(Relationship.type_code == type_code)
    if name_eq:
        query = query.filter(RelationshipType.type_name == name_eq)
    if name_like:
        query = query.filter(RelationshipType.type_name.ilike(f"%{name_like}%"))
    if trait_class:
        query = query.filter(Relationship.trait_class == trait_class)
    if is_active is not None:
        query = query.filter(Relationship.is_active == is_active)
    if source_id is not None:
        query = query.filter(Relationship.source_id == source_id)
    if target_id is not None:
        query = query.filter(Relationship.target_id == target_id)
    query = _apply_tags_any_filter(query, Relationship.tags, tags_any)

    total = query.count()
    items = [row.to_dict() for row in query.offset(offset).limit(limit).all()]
    return {"items": items, "page": {"total": total, "offset": offset, "limit": limit}}


@router.get("/relationships/{relationship_id}")
def get_relationship(
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Relationship).filter(Relationship.id == relationship_id).first()
    if not row:
        return _problem(404, "Not Found", f"relationship `{relationship_id}` not found.", request)
    source = db.query(Node).filter(Node.id == row.source_id).first()
    target = db.query(Node).filter(Node.id == row.target_id).first()
    if not source or not target:
        return _problem(404, "Not Found", f"relationship `{relationship_id}` not found.", request)
    if not relationship_row_visible(row, source, target, policy, deny_all):
        return _problem(404, "Not Found", f"relationship `{relationship_id}` not found.", request)
    return row.to_dict()


@router.post("/relationships", status_code=status.HTTP_201_CREATED)
def create_relationship(
    payload: RelationshipIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    rel_type = db.query(RelationshipType).filter(RelationshipType.type_code == payload.type_code).first()
    if not rel_type:
        return _problem(400, "Bad Request", f"unknown relationship type `{payload.type_code}`.", request)

    source = db.query(Node).filter(Node.id == payload.source_id).first()
    target = db.query(Node).filter(Node.id == payload.target_id).first()
    if not source or not target:
        return _problem(400, "Bad Request", "source_id or target_id does not exist.", request)
    if not proposed_relationship_visible(payload.type_code, source, target, policy, deny_all):
        return _forbidden_data_access(request)

    row = Relationship(
        type_id=rel_type.id,
        type_code=payload.type_code,
        source_id=payload.source_id,
        target_id=payload.target_id,
        source_role=payload.source_role,
        target_role=payload.target_role,
        attributes=payload.attributes,
        tags=payload.tags,
        is_active=payload.is_active,
        weight=payload.weight,
        # Instance trait fields are derived from type_code (F01/F10 contract).
        trait_class=rel_type.trait_class,
        trait_mask=int(rel_type.trait_mask or 0),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.patch("/relationships/{relationship_id}")
def patch_relationship(
    relationship_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Relationship).filter(Relationship.id == relationship_id).first()
    if not row:
        return _problem(404, "Not Found", f"relationship `{relationship_id}` not found.", request)
    source = db.query(Node).filter(Node.id == row.source_id).first()
    target = db.query(Node).filter(Node.id == row.target_id).first()
    if not source or not target or not relationship_row_visible(row, source, target, policy, deny_all):
        return _forbidden_data_access(request)
    allowed = {
        "source_role",
        "target_role",
        "attributes",
        "tags",
        "is_active",
        "weight",
    }
    for k, v in payload.items():
        if k in allowed:
            setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship(
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Relationship).filter(Relationship.id == relationship_id).first()
    if not row:
        return _problem(404, "Not Found", f"relationship `{relationship_id}` not found.", request)
    source = db.query(Node).filter(Node.id == row.source_id).first()
    target = db.query(Node).filter(Node.id == row.target_id).first()
    if not source or not target or not relationship_row_visible(row, source, target, policy, deny_all):
        return _forbidden_data_access(request)
    db.delete(row)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@router.get("/worlds/{world_id}/nodes")
def list_world_nodes(
    world_id: str,
    request: Request,
    type_code: Optional[str] = None,
    name_eq: Optional[str] = None,
    name_like: Optional[str] = None,
    tags_any: Optional[str] = None,
    trait_class: Optional[str] = None,
    required_any_mask: int = 0,
    required_all_mask: int = 0,
    is_active: Optional[bool] = None,
    is_public: Optional[bool] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    err = _validate_query(name_eq, name_like, tags_any, request)
    if err:
        return err
    query = db.query(Node).filter(Node.attributes["world_id"].astext == world_id)
    query = apply_world_scoped_node_read_policy(query, policy, deny_all, world_id)
    if type_code:
        query = query.filter(Node.type_code == type_code)
    if name_eq:
        query = query.filter(Node.name == name_eq)
    if name_like:
        query = query.filter(Node.name.ilike(f"%{name_like}%"))
    if trait_class:
        query = query.filter(Node.trait_class == trait_class)
    query = Node.filter_by_trait_any(query, required_any_mask)
    query = Node.filter_by_trait_all(query, required_all_mask)
    if is_active is not None:
        query = query.filter(Node.is_active == is_active)
    if is_public is not None:
        query = query.filter(Node.is_public == is_public)
    query = _apply_tags_any_filter(query, Node.tags, tags_any)

    total = query.count()
    items = [row.to_dict() for row in query.offset(offset).limit(limit).all()]
    return {"items": items, "page": {"total": total, "offset": offset, "limit": limit}}


@router.get("/worlds/{world_id}/nodes/{node_id}")
def get_world_node(
    world_id: str,
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Node).filter(Node.id == node_id).first()
    if not row or (row.attributes or {}).get("world_id") != world_id:
        return _problem(404, "Not Found", f"node is not in world scope: {world_id}", request)
    if not node_row_visible(row, policy, deny_all):
        return _problem(404, "Not Found", f"node is not in world scope: {world_id}", request)
    return row.to_dict()


@router.post("/worlds/{world_id}/nodes", status_code=status.HTTP_201_CREATED)
def create_world_node(
    world_id: str,
    payload: NodeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    attrs = dict(payload.attributes or {})
    if _scope_node_world_conflict(attrs, world_id):
        return _problem(409, "Conflict", "world_id path conflicts with body attributes.world_id.", request)
    attrs["world_id"] = world_id

    if not proposed_node_visible(payload.type_code, attrs, policy, deny_all):
        return _forbidden_data_access(request)

    node_type = db.query(NodeType).filter(NodeType.type_code == payload.type_code).first()
    if not node_type:
        return _problem(400, "Bad Request", f"unknown node type `{payload.type_code}`.", request)
    row = Node(
        type_id=node_type.id,
        type_code=payload.type_code,
        name=payload.name,
        description=payload.description,
        is_active=payload.is_active,
        is_public=payload.is_public,
        access_level=payload.access_level,
        trait_class=node_type.trait_class,
        trait_mask=int(node_type.trait_mask or 0),
        location_id=payload.location_id,
        home_id=payload.home_id,
        attributes=attrs,
        tags=payload.tags,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.patch("/worlds/{world_id}/nodes/{node_id}")
def patch_world_node(
    world_id: str,
    node_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Node).filter(Node.id == node_id).first()
    if not row or (row.attributes or {}).get("world_id") != world_id:
        return _problem(404, "Not Found", f"node is not in world scope: {world_id}", request)
    if not node_row_visible(row, policy, deny_all):
        return _forbidden_data_access(request)
    if "attributes" in payload and _scope_node_world_conflict(payload.get("attributes", {}), world_id):
        return _problem(409, "Conflict", "world_id path conflicts with body attributes.world_id.", request)
    for k in {"name", "description", "is_active", "is_public", "access_level", "location_id", "home_id", "attributes", "tags"}:
        if k in payload:
            if k == "attributes":
                attrs = dict(payload["attributes"] or {})
                attrs["world_id"] = world_id
                setattr(row, "attributes", attrs)
            else:
                setattr(row, k, payload[k])
    db.flush()
    if not node_row_visible(row, policy, deny_all):
        db.rollback()
        return _forbidden_data_access(request)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/worlds/{world_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world_node(
    world_id: str,
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(Node).filter(Node.id == node_id).first()
    if not row or (row.attributes or {}).get("world_id") != world_id:
        return _problem(404, "Not Found", f"node is not in world scope: {world_id}", request)
    if not node_row_visible(row, policy, deny_all):
        return _forbidden_data_access(request)
    db.delete(row)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@router.get("/worlds/{world_id}/relationships")
def list_world_relationships(
    world_id: str,
    request: Request,
    type_code: Optional[str] = None,
    name_eq: Optional[str] = None,
    name_like: Optional[str] = None,
    tags_any: Optional[str] = None,
    trait_class: Optional[str] = None,
    is_active: Optional[bool] = None,
    source_id: Optional[int] = None,
    target_id: Optional[int] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    err = _validate_query(name_eq, name_like, tags_any, request)
    if err:
        return err
    source_node = aliased(Node)
    target_node = aliased(Node)
    query = (
        db.query(Relationship)
        .join(RelationshipType, RelationshipType.type_code == Relationship.type_code)
        .join(source_node, source_node.id == Relationship.source_id)
        .join(target_node, target_node.id == Relationship.target_id)
        .filter(
            and_(
                source_node.attributes["world_id"].astext == world_id,
                target_node.attributes["world_id"].astext == world_id,
            )
        )
    )
    query = apply_relationship_read_policy(query, policy, deny_all, source_node, target_node)
    if type_code:
        query = query.filter(Relationship.type_code == type_code)
    if name_eq:
        query = query.filter(RelationshipType.type_name == name_eq)
    if name_like:
        query = query.filter(RelationshipType.type_name.ilike(f"%{name_like}%"))
    if trait_class:
        query = query.filter(Relationship.trait_class == trait_class)
    if is_active is not None:
        query = query.filter(Relationship.is_active == is_active)
    if source_id is not None:
        query = query.filter(Relationship.source_id == source_id)
    if target_id is not None:
        query = query.filter(Relationship.target_id == target_id)
    query = _apply_tags_any_filter(query, Relationship.tags, tags_any)

    total = query.count()
    items = [row.to_dict() for row in query.offset(offset).limit(limit).all()]
    return {"items": items, "page": {"total": total, "offset": offset, "limit": limit}}


@router.get("/worlds/{world_id}/relationships/{relationship_id}")
def get_world_relationship(
    world_id: str,
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    source_node = aliased(Node)
    target_node = aliased(Node)
    row = (
        db.query(Relationship)
        .join(source_node, source_node.id == Relationship.source_id)
        .join(target_node, target_node.id == Relationship.target_id)
        .filter(
            Relationship.id == relationship_id,
            source_node.attributes["world_id"].astext == world_id,
            target_node.attributes["world_id"].astext == world_id,
        )
        .first()
    )
    if not row:
        return _problem(404, "Not Found", f"relationship is not in world scope: {world_id}", request)
    src = db.query(Node).filter(Node.id == row.source_id).first()
    tgt = db.query(Node).filter(Node.id == row.target_id).first()
    if not src or not tgt or not relationship_row_visible(row, src, tgt, policy, deny_all):
        return _problem(404, "Not Found", f"relationship is not in world scope: {world_id}", request)
    return row.to_dict()


@router.post("/worlds/{world_id}/relationships", status_code=status.HTTP_201_CREATED)
def create_world_relationship(
    world_id: str,
    payload: RelationshipIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    rel_type = db.query(RelationshipType).filter(RelationshipType.type_code == payload.type_code).first()
    if not rel_type:
        return _problem(400, "Bad Request", f"unknown relationship type `{payload.type_code}`.", request)
    source = db.query(Node).filter(Node.id == payload.source_id).first()
    target = db.query(Node).filter(Node.id == payload.target_id).first()
    if not source or not target:
        return _problem(400, "Bad Request", "source_id or target_id does not exist.", request)
    if (source.attributes or {}).get("world_id") != world_id or (target.attributes or {}).get("world_id") != world_id:
        return _problem(404, "Not Found", f"source/target is not in world scope: {world_id}", request)
    if not proposed_relationship_visible(payload.type_code, source, target, policy, deny_all):
        return _forbidden_data_access(request)
    row = Relationship(
        type_id=rel_type.id,
        type_code=payload.type_code,
        source_id=payload.source_id,
        target_id=payload.target_id,
        source_role=payload.source_role,
        target_role=payload.target_role,
        attributes=payload.attributes,
        tags=payload.tags,
        is_active=payload.is_active,
        weight=payload.weight,
        trait_class=rel_type.trait_class,
        trait_mask=int(rel_type.trait_mask or 0),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.patch("/worlds/{world_id}/relationships/{relationship_id}")
def patch_world_relationship(
    world_id: str,
    relationship_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    source_node = aliased(Node)
    target_node = aliased(Node)
    row = (
        db.query(Relationship)
        .join(source_node, source_node.id == Relationship.source_id)
        .join(target_node, target_node.id == Relationship.target_id)
        .filter(
            Relationship.id == relationship_id,
            source_node.attributes["world_id"].astext == world_id,
            target_node.attributes["world_id"].astext == world_id,
        )
        .first()
    )
    if not row:
        return _problem(404, "Not Found", f"relationship is not in world scope: {world_id}", request)
    src = db.query(Node).filter(Node.id == row.source_id).first()
    tgt = db.query(Node).filter(Node.id == row.target_id).first()
    if not src or not tgt or not relationship_row_visible(row, src, tgt, policy, deny_all):
        return _forbidden_data_access(request)
    for k in {"source_role", "target_role", "attributes", "tags", "is_active", "weight"}:
        if k in payload:
            setattr(row, k, payload[k])
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/worlds/{world_id}/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world_relationship(
    world_id: str,
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    source_node = aliased(Node)
    target_node = aliased(Node)
    row = (
        db.query(Relationship)
        .join(source_node, source_node.id == Relationship.source_id)
        .join(target_node, target_node.id == Relationship.target_id)
        .filter(
            Relationship.id == relationship_id,
            source_node.attributes["world_id"].astext == world_id,
            target_node.attributes["world_id"].astext == world_id,
        )
        .first()
    )
    if not row:
        return _problem(404, "Not Found", f"relationship is not in world scope: {world_id}", request)
    src = db.query(Node).filter(Node.id == row.source_id).first()
    tgt = db.query(Node).filter(Node.id == row.target_id).first()
    if not src or not tgt or not relationship_row_visible(row, src, tgt, policy, deny_all):
        return _forbidden_data_access(request)
    db.delete(row)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
