"""CampusWorld world interaction HTTP adapters."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.dependencies import AuthenticatedUser, get_current_http_user
from app.core.database import get_db
from app.core.log import get_logger, LoggerNames
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


class MapQueryRequest(BaseModel):
    session_id: Optional[str] = None
    world_id: Optional[str] = None
    query: str
    mode: str = "auto"


class WorldSearchRequest(BaseModel):
    session_id: Optional[str] = None
    world_id: Optional[str] = None
    query: str
    types: Optional[list[str]] = None


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
    return world_interaction_service.query_decision_center(db, _actor(current_user), payload.query, payload.mode)


@semantic_map_router.post("/query")
def query_semantic_map(payload: MapQueryRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.query_semantic_map(db, _actor(current_user), payload.query, payload.mode)


@world_search_router.post("")
def search_world(payload: WorldSearchRequest, db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.search(db, _actor(current_user), payload.query)


@world_history_router.get("/summary")
def get_world_history_summary(db: Session = Depends(get_db), current_user: AuthenticatedUser = Depends(get_current_http_user)) -> Dict[str, Any]:
    return world_interaction_service.history_summary(db, _actor(current_user))
