"""CampusWorld world interaction HTTP adapters."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.dependencies import AuthenticatedUser, get_current_http_user
from app.core.database import get_db
from app.core.log import get_logger, LoggerNames
from app.repositories.world_conversation_archive import WorldHistoryArchiveLimitError
from app.schemas.world_history import (
    ConversationArchiveRequest,
    DEFAULT_HISTORY_SUMMARY_LIMIT,
    MAX_HISTORY_SUMMARY_LIMIT,
)
from app.services.world_interaction import WorldActor, world_interaction_service

logger = get_logger(LoggerNames.API)


world_sessions_router = APIRouter(prefix="/world-sessions", tags=["world-sessions"])
worlds_router = APIRouter(prefix="/worlds", tags=["worlds"])
decision_center_router = APIRouter(prefix="/decision-center", tags=["decision-center"])
semantic_map_router = APIRouter(prefix="/semantic-map", tags=["semantic-map"])
world_search_router = APIRouter(prefix="/world-search", tags=["world-search"])
world_history_router = APIRouter(prefix="/world-history", tags=["world-history"])


class EnterWorldRequest(BaseModel):
    world_id: str = Field(..., min_length=1)


class DecisionActionRequest(BaseModel):
    session_id: str
    decision_event_id: str
    option_id: str


class DecisionQueryRequest(BaseModel):
    session_id: Optional[str] = None
    query: str
    mode: str = "command"
    thread_id: Optional[str] = None


class MapQueryRequest(BaseModel):
    session_id: Optional[str] = None
    world_id: Optional[str] = None
    query: str
    mode: str = "auto"


class SemanticMapActionRequest(BaseModel):
    action_type: str = Field(..., min_length=1)
    view_layer: Optional[str] = None
    anchor_id: Optional[str] = None
    mode: str = "focus"
    selected_entity_id: Optional[str] = None


class WorldSearchRequest(BaseModel):
    session_id: Optional[str] = None
    world_id: Optional[str] = None
    query: str
    types: Optional[list[str]] = None


class StreamCancelRequest(BaseModel):
    stream_id: str = Field(..., min_length=1)


def _actor(user: AuthenticatedUser) -> WorldActor:
    return WorldActor(user_id=user.user_id, username=user.username, permissions=list(user.permissions or []), roles=list(user.roles or []))


@world_sessions_router.get("/current")
def get_current_world_session(db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    actor = _actor(current_user)
    try:
        return world_interaction_service.get_current_state(db, actor)
    except ValueError as exc:
        detail = str(exc)
        logger.warning(
            "world-sessions/current failed for user_id=%s username=%s: %s",
            actor.user_id,
            actor.username,
            detail,
        )
        raise HTTPException(status_code=404, detail=detail) from exc


@world_sessions_router.get("/{session_id}/interaction-state")
def get_world_interaction_state(session_id: str, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.refresh_interaction_state(db, _actor(current_user))


@world_sessions_router.post("/enter-world")
def enter_world(payload: EnterWorldRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.enter_world(db, _actor(current_user), payload.world_id)


@world_sessions_router.post("/leave-world")
def leave_world(db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.leave_world(db, _actor(current_user))


@worlds_router.get("/available")
def list_available_worlds(db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    state = world_interaction_service.get_current_state(db, _actor(current_user))
    return {"items": state["available_worlds"]}


@decision_center_router.post("/actions")
def execute_decision_action(payload: DecisionActionRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.execute_decision_action(db, _actor(current_user), payload.decision_event_id, payload.option_id)


@decision_center_router.post("/query")
def query_decision_center(payload: DecisionQueryRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    if payload.mode == "aico":
        raise HTTPException(
            status_code=400,
            detail="AICO queries must use POST /decision-center/query/stream",
        )
    return world_interaction_service.run_command_query(db, _actor(current_user), payload.query)


@decision_center_router.post("/query/stream")
def stream_decision_query(payload: DecisionQueryRequest, current_user: AuthenticatedUser = Depends(get_current_http_user)):
    if payload.mode != "aico":
        raise HTTPException(status_code=400, detail="Only mode=aico is supported for streaming queries")
    actor = _actor(current_user)
    generator = world_interaction_service.stream_aico_query(actor, payload.query, thread_id=payload.thread_id)
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@decision_center_router.post("/query/stream/cancel")
def cancel_stream_query(payload: StreamCancelRequest, current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.cancel_stream(payload.stream_id)


@semantic_map_router.get("/focus")
def get_semantic_map_focus(
    view_layer: str = "room",
    anchor_id: Optional[str] = None,
    mode: str = "focus",
    selected_entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_http_user),
) -> Dict[str, Any]:
    return world_interaction_service.get_semantic_map_focus(
        db,
        _actor(current_user),
        view_layer=view_layer,
        anchor_id=anchor_id,
        mode=mode,
        selected_entity_id=selected_entity_id,
    )


@semantic_map_router.get("/space-summary")
def get_semantic_map_space_summary(
    node_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_http_user),
) -> Dict[str, Any]:
    return world_interaction_service.get_space_summary(db, _actor(current_user), node_id)


@semantic_map_router.get("/entity-inspect")
def get_semantic_map_entity_inspect(
    node_id: Optional[int] = None,
    agent_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_http_user),
) -> Dict[str, Any]:
    if node_id is None and not agent_id:
        raise HTTPException(status_code=400, detail="node_id or agent_id is required")
    return world_interaction_service.get_entity_inspect(
        db,
        _actor(current_user),
        node_id=node_id,
        agent_id=agent_id,
    )


@semantic_map_router.post("/actions")
def execute_semantic_map_action(
    payload: SemanticMapActionRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_http_user),
) -> Dict[str, Any]:
    return world_interaction_service.execute_semantic_map_action(
        db,
        _actor(current_user),
        action_type=payload.action_type,
        view_layer=payload.view_layer,
        anchor_id=payload.anchor_id,
        mode=payload.mode,
        selected_entity_id=payload.selected_entity_id,
    )


@semantic_map_router.post("/query")
def query_semantic_map(payload: MapQueryRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.query_semantic_map(db, _actor(current_user), payload.query, payload.mode)


@world_search_router.post("")
def search_world(payload: WorldSearchRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.search(db, _actor(current_user), payload.query)


@world_history_router.get("/summary")
def get_world_history_summary(
    limit: int = Query(DEFAULT_HISTORY_SUMMARY_LIMIT, ge=1, le=MAX_HISTORY_SUMMARY_LIMIT),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_http_user),
) -> Dict[str, Any]:
    return world_interaction_service.history_summary(
        db,
        _actor(current_user),
        limit=limit,
        offset=offset,
    )


@world_history_router.post("/conversations/archive")
def archive_conversations(
    payload: ConversationArchiveRequest,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(get_current_http_user),
) -> Dict[str, Any]:
    try:
        return world_interaction_service.archive_conversations(db, _actor(current_user), payload)
    except WorldHistoryArchiveLimitError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
