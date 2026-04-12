from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.v1.dependencies import APIPrincipal, require_api_permission
from app.core.database import get_db
from app.schemas.graph_ontology import NodeIn, RelationshipIn
from app.api.v1.endpoints import graph as graph_endpoints

router = APIRouter(prefix="/worlds", tags=["graph-world-scope"])


@router.get("/{world_id}/nodes")
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
    return graph_endpoints.list_world_nodes(
        world_id=world_id,
        request=request,
        type_code=type_code,
        name_eq=name_eq,
        name_like=name_like,
        tags_any=tags_any,
        trait_class=trait_class,
        required_any_mask=required_any_mask,
        required_all_mask=required_all_mask,
        is_active=is_active,
        is_public=is_public,
        offset=offset,
        limit=limit,
        db=db,
        principal=principal,
    )


@router.get("/{world_id}/nodes/{node_id}")
def get_world_node(
    world_id: str,
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    return graph_endpoints.get_world_node(world_id, node_id, request, db, principal)


@router.post("/{world_id}/nodes", status_code=status.HTTP_201_CREATED)
def create_world_node(
    world_id: str,
    payload: NodeIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    return graph_endpoints.create_world_node(world_id, payload, request, db, principal)


@router.patch("/{world_id}/nodes/{node_id}")
def patch_world_node(
    world_id: str,
    node_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    return graph_endpoints.patch_world_node(world_id, node_id, payload, request, db, principal)


@router.delete("/{world_id}/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world_node(
    world_id: str,
    node_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    return graph_endpoints.delete_world_node(world_id, node_id, request, db, principal)


@router.get("/{world_id}/relationships")
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
    return graph_endpoints.list_world_relationships(
        world_id=world_id,
        request=request,
        type_code=type_code,
        name_eq=name_eq,
        name_like=name_like,
        tags_any=tags_any,
        trait_class=trait_class,
        is_active=is_active,
        source_id=source_id,
        target_id=target_id,
        offset=offset,
        limit=limit,
        db=db,
        principal=principal,
    )


@router.get("/{world_id}/relationships/{relationship_id}")
def get_world_relationship(
    world_id: str,
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.read")),
):
    return graph_endpoints.get_world_relationship(world_id, relationship_id, request, db, principal)


@router.post("/{world_id}/relationships", status_code=status.HTTP_201_CREATED)
def create_world_relationship(
    world_id: str,
    payload: RelationshipIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    return graph_endpoints.create_world_relationship(world_id, payload, request, db, principal)


@router.patch("/{world_id}/relationships/{relationship_id}")
def patch_world_relationship(
    world_id: str,
    relationship_id: int,
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    return graph_endpoints.patch_world_relationship(world_id, relationship_id, payload, request, db, principal)


@router.delete("/{world_id}/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_world_relationship(
    world_id: str,
    relationship_id: int,
    request: Request,
    db: Session = Depends(get_db),
    principal: APIPrincipal = Depends(require_api_permission("graph.write")),
):
    return graph_endpoints.delete_world_relationship(world_id, relationship_id, request, db, principal)
