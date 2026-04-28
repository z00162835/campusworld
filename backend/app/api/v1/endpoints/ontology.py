from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.v1.dependencies import APIPrincipal, require_api_permission
from app.core.database import get_db
from app.models.graph import NodeType, RelationshipType
from app.schemas.data_access import DataAccessV1
from app.schemas.graph_ontology import NodeTypeIn, RelationshipTypeIn
from app.services.data_access_policy import (
    apply_ontology_node_type_read_policy,
    apply_ontology_relationship_type_read_policy,
    load_policy,
    ontology_relationship_type_visible,
    ontology_type_visible,
)

router = APIRouter(prefix="/ontology", tags=["ontology"])


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


def _validate_query(name_like: Optional[str], tags_any: Optional[str], request: Request) -> Optional[JSONResponse]:
    if name_like is not None and not name_like.strip():
        return _problem(400, "Bad Request", "name_like must not be blank.", request)
    if tags_any is not None and not _split_tags(tags_any):
        return _problem(400, "Bad Request", "tags_any resolves to empty set.", request)
    return None


@router.get("/node-types")
def list_node_types(
    request: Request,
    type_code: Optional[str] = None,
    parent_type_code: Optional[str] = None,
    name_eq: Optional[str] = None,
    type_name_eq: Optional[str] = None,
    name_like: Optional[str] = None,
    tags_any: Optional[str] = None,
    trait_class: Optional[str] = None,
    is_active: Optional[bool] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    err = _validate_query(name_like, tags_any, request)
    if err:
        return err
    query = db.query(NodeType)
    query = apply_ontology_node_type_read_policy(query, policy, deny_all)
    if type_code:
        query = query.filter(NodeType.type_code == type_code)
    if parent_type_code:
        query = query.filter(NodeType.parent_type_code == parent_type_code)
    if name_eq:
        query = query.filter(NodeType.type_name == name_eq)
    if type_name_eq:
        query = query.filter(NodeType.type_name == type_name_eq)
    if name_like:
        query = query.filter(NodeType.type_name.ilike(f"%{name_like}%"))
    if trait_class:
        query = query.filter(NodeType.trait_class == trait_class)
    if is_active is not None:
        query = query.filter(NodeType.is_active == is_active)
    for tag in _split_tags(tags_any):
        query = query.filter(NodeType.tags.contains([tag]))

    total = query.count()
    items = [row.to_dict() for row in query.offset(offset).limit(limit).all()]
    return {"items": items, "page": {"total": total, "offset": offset, "limit": limit}}


@router.post("/node-types", status_code=status.HTTP_201_CREATED)
def create_node_type(
    payload: NodeTypeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    if not ontology_type_visible(payload.type_code, policy, deny_all):
        return _forbidden_data_access(request)
    exists = db.query(NodeType).filter(NodeType.type_code == payload.type_code).first()
    if exists:
        return _problem(409, "Conflict", f"node type `{payload.type_code}` already exists.", request)

    row = NodeType(
        type_code=payload.type_code,
        parent_type_code=payload.parent_type_code,
        type_name=payload.type_name,
        typeclass=payload.typeclass,
        status=0 if payload.is_active else 1,
        classname=payload.classname,
        module_path=payload.module_path,
        description=payload.description,
        schema_definition=payload.schema_definition,
        schema_default=payload.schema_default,
        inferred_rules=payload.inferred_rules,
        tags=payload.tags,
        ui_config=payload.ui_config,
        trait_class=payload.trait_class,
        trait_mask=payload.trait_mask,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.get("/node-types/{type_code}")
def get_node_type(
    type_code: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(NodeType).filter(NodeType.type_code == type_code).first()
    if not row:
        return _problem(404, "Not Found", f"node type `{type_code}` not found.", request)
    if not ontology_type_visible(type_code, policy, deny_all):
        return _problem(404, "Not Found", f"node type `{type_code}` not found.", request)
    return row.to_dict()


@router.patch("/node-types/{type_code}")
def patch_node_type(
    type_code: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(NodeType).filter(NodeType.type_code == type_code).first()
    if not row:
        return _problem(404, "Not Found", f"node type `{type_code}` not found.", request)
    if not ontology_type_visible(type_code, policy, deny_all):
        return _forbidden_data_access(request)
    if "graph_seed" in list(row.tags or []):
        if "trait_class" in payload or "trait_mask" in payload:
            return _problem(409, "Conflict", "graph_seed type is locked for trait mutation.", request)
    allowed = {
        "parent_type_code",
        "type_name",
        "typeclass",
        "classname",
        "module_path",
        "description",
        "schema_definition",
        "schema_default",
        "inferred_rules",
        "tags",
        "ui_config",
        "trait_class",
        "trait_mask",
        "is_active",
    }
    for k, v in payload.items():
        if k in allowed:
            if k == "is_active":
                row.status = 0 if bool(v) else 1
            else:
                setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/node-types/{type_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node_type(
    type_code: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(NodeType).filter(NodeType.type_code == type_code).first()
    if not row:
        return _problem(404, "Not Found", f"node type `{type_code}` not found.", request)
    if not ontology_type_visible(type_code, policy, deny_all):
        return _forbidden_data_access(request)
    if "graph_seed" in list(row.tags or []):
        return _problem(409, "Conflict", "graph_seed type cannot be deleted.", request)
    db.delete(row)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@router.get("/relationship-types")
def list_relationship_types(
    request: Request,
    type_code: Optional[str] = None,
    name_eq: Optional[str] = None,
    type_name_eq: Optional[str] = None,
    name_like: Optional[str] = None,
    tags_any: Optional[str] = None,
    trait_class: Optional[str] = None,
    is_active: Optional[bool] = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    err = _validate_query(name_like, tags_any, request)
    if err:
        return err
    query = db.query(RelationshipType)
    query = apply_ontology_relationship_type_read_policy(query, policy, deny_all)
    if type_code:
        query = query.filter(RelationshipType.type_code == type_code)
    if name_eq:
        query = query.filter(RelationshipType.type_name == name_eq)
    if type_name_eq:
        query = query.filter(RelationshipType.type_name == type_name_eq)
    if name_like:
        query = query.filter(RelationshipType.type_name.ilike(f"%{name_like}%"))
    if trait_class:
        query = query.filter(RelationshipType.trait_class == trait_class)
    if is_active is not None:
        query = query.filter(RelationshipType.is_active == is_active)
    for tag in _split_tags(tags_any):
        query = query.filter(RelationshipType.tags.contains([tag]))

    total = query.count()
    items = [row.to_dict() for row in query.offset(offset).limit(limit).all()]
    return {"items": items, "page": {"total": total, "offset": offset, "limit": limit}}


@router.post("/relationship-types", status_code=status.HTTP_201_CREATED)
def create_relationship_type(
    payload: RelationshipTypeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    if not ontology_relationship_type_visible(payload.type_code, policy, deny_all):
        return _forbidden_data_access(request)
    exists = db.query(RelationshipType).filter(RelationshipType.type_code == payload.type_code).first()
    if exists:
        return _problem(409, "Conflict", f"relationship type `{payload.type_code}` already exists.", request)

    row = RelationshipType(
        type_code=payload.type_code,
        type_name=payload.type_name,
        typeclass=payload.typeclass,
        status=0 if payload.is_active else 1,
        constraints=payload.constraints,
        description=payload.description,
        schema_definition=payload.schema_definition,
        inferred_rules=payload.inferred_rules,
        tags=payload.tags,
        ui_config=payload.ui_config,
        trait_class=payload.trait_class,
        trait_mask=payload.trait_mask,
        is_directed=payload.is_directed,
        is_symmetric=payload.is_symmetric,
        is_transitive=payload.is_transitive,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.get("/relationship-types/{type_code}")
def get_relationship_type(
    type_code: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.read")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(RelationshipType).filter(RelationshipType.type_code == type_code).first()
    if not row:
        return _problem(404, "Not Found", f"relationship type `{type_code}` not found.", request)
    if not ontology_relationship_type_visible(type_code, policy, deny_all):
        return _problem(404, "Not Found", f"relationship type `{type_code}` not found.", request)
    return row.to_dict()


@router.patch("/relationship-types/{type_code}")
def patch_relationship_type(
    type_code: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(RelationshipType).filter(RelationshipType.type_code == type_code).first()
    if not row:
        return _problem(404, "Not Found", f"relationship type `{type_code}` not found.", request)
    if not ontology_relationship_type_visible(type_code, policy, deny_all):
        return _forbidden_data_access(request)
    allowed = {
        "type_name",
        "typeclass",
        "constraints",
        "description",
        "schema_definition",
        "inferred_rules",
        "tags",
        "ui_config",
        "trait_class",
        "trait_mask",
        "is_directed",
        "is_symmetric",
        "is_transitive",
        "is_active",
    }
    for k, v in payload.items():
        if k in allowed:
            if k == "is_active":
                row.status = 0 if bool(v) else 1
            else:
                setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row.to_dict()


@router.delete("/relationship-types/{type_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_relationship_type(
    type_code: str,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("ontology.write")),
):
    policy, deny_all = _policy_from_principal(principal)
    row = db.query(RelationshipType).filter(RelationshipType.type_code == type_code).first()
    if not row:
        return _problem(404, "Not Found", f"relationship type `{type_code}` not found.", request)
    if not ontology_relationship_type_visible(type_code, policy, deny_all):
        return _forbidden_data_access(request)
    db.delete(row)
    db.commit()
    return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
