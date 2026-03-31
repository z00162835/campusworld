"""
F01 V2 runtime persistence contracts for world packages.

This module provides:
- Runtime status and error code constants
- Structured operation result model
- Repository for runtime state/job persistence
- Service facade for install/uninstall/reload orchestration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.core.database import db_session_context
from app.models.system.world_runtime import WorldInstallJob, WorldRuntimeState


class WorldRuntimeStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLING = "installing"
    LOADING = "loading"
    INSTALLED = "installed"
    UNLOADING = "unloading"
    RELOADING = "reloading"
    FAILED = "failed"
    BROKEN = "broken"


class WorldErrorCode(str, Enum):
    WORLD_NOT_FOUND = "WORLD_NOT_FOUND"
    WORLD_NOT_INSTALLED = "WORLD_NOT_INSTALLED"
    WORLD_MANIFEST_INVALID = "WORLD_MANIFEST_INVALID"
    WORLD_STATE_CONFLICT = "WORLD_STATE_CONFLICT"
    WORLD_DB_WRITE_FAILED = "WORLD_DB_WRITE_FAILED"
    WORLD_DB_ROLLBACK_FAILED = "WORLD_DB_ROLLBACK_FAILED"
    WORLD_LOAD_FAILED = "WORLD_LOAD_FAILED"
    WORLD_UNLOAD_FAILED = "WORLD_UNLOAD_FAILED"
    WORLD_RELOAD_FAILED = "WORLD_RELOAD_FAILED"
    WORLD_BUSY = "WORLD_BUSY"
    WORLD_INTERNAL_ERROR = "WORLD_INTERNAL_ERROR"


@dataclass
class OperationResult:
    ok: bool
    world_id: str
    status_before: str
    status_after: str
    message: str
    job_id: Optional[str] = None
    error_code: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "world_id": self.world_id,
            "job_id": self.job_id,
            "status_before": self.status_before,
            "status_after": self.status_after,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class WorldRuntimeRepository:
    """Persistence APIs for world runtime state and install jobs."""

    @staticmethod
    def _parse_job_id(job_id: str) -> Optional[UUID]:
        try:
            return UUID(str(job_id))
        except Exception:
            return None

    def get_state(self, world_id: str) -> Dict[str, Any]:
        with db_session_context() as session:
            row = session.query(WorldRuntimeState).filter(WorldRuntimeState.world_id == world_id).first()
            if row is None:
                return {
                    "world_id": world_id,
                    "status": WorldRuntimeStatus.NOT_INSTALLED.value,
                    "version": None,
                    "last_error_code": None,
                    "last_error_message": None,
                    "metadata": {},
                }
            return {
                "world_id": row.world_id,
                "status": row.status,
                "version": row.version,
                "last_error_code": row.last_error_code,
                "last_error_message": row.last_error_message,
                "metadata": row.metadata or {},
                "updated_at": row.updated_at,
            }

    def get_state_for_update(self, session: Session, world_id: str) -> Dict[str, Any]:
        row = (
            session.query(WorldRuntimeState)
            .filter(WorldRuntimeState.world_id == world_id)
            .with_for_update(read=True)
            .first()
        )
        if row is None:
            return {
                "world_id": world_id,
                "status": WorldRuntimeStatus.NOT_INSTALLED.value,
                "version": None,
                "last_error_code": None,
                "last_error_message": None,
                "metadata": {},
            }
        return {
            "world_id": row.world_id,
            "status": row.status,
            "version": row.version,
            "last_error_code": row.last_error_code,
            "last_error_message": row.last_error_message,
            "metadata": row.metadata or {},
            "updated_at": row.updated_at,
        }

    def upsert_state(
        self,
        world_id: str,
        status: str,
        version: Optional[str] = None,
        last_error_code: Optional[str] = None,
        last_error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        updated_by: str = "system",
        session: Optional[Session] = None,
    ) -> None:
        payload = metadata or {}
        owns_session = session is None
        if session is None:
            session_ctx = db_session_context()
            session = session_ctx.__enter__()
        try:
            stmt = pg_insert(WorldRuntimeState).values(
                world_id=world_id,
                status=status,
                version=version,
                last_error_code=last_error_code,
                last_error_message=last_error_message,
                metadata=payload,
                updated_by=updated_by,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[WorldRuntimeState.world_id],
                set_={
                    "status": stmt.excluded.status,
                    "version": stmt.excluded.version,
                    "last_error_code": stmt.excluded.last_error_code,
                    "last_error_message": stmt.excluded.last_error_message,
                    "metadata": stmt.excluded.metadata,
                    "updated_by": stmt.excluded.updated_by,
                    "updated_at": func.now(),
                },
            )
            session.execute(stmt)
            if owns_session:
                session.commit()
        finally:
            if owns_session:
                session_ctx.__exit__(None, None, None)

    def create_job(
        self,
        world_id: str,
        action: str,
        requested_by: str = "system",
        request_fingerprint: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> str:
        owns_session = session is None
        if session is None:
            session_ctx = db_session_context()
            session = session_ctx.__enter__()
        try:
            row = WorldInstallJob(
                world_id=world_id,
                action=action,
                status="running",
                requested_by=requested_by,
                request_fingerprint=request_fingerprint,
                started_at=datetime.utcnow(),
                event_log=[],
                summary={},
            )
            session.add(row)
            if owns_session:
                session.commit()
            else:
                session.flush()
            session.refresh(row)
            return str(row.job_id)
        finally:
            if owns_session:
                session_ctx.__exit__(None, None, None)

    def append_job_event(
        self, job_id: str, stage: str, payload: Dict[str, Any], session: Optional[Session] = None
    ) -> None:
        parsed_job_id = self._parse_job_id(job_id)
        if parsed_job_id is None:
            return
        owns_session = session is None
        if session is None:
            session_ctx = db_session_context()
            session = session_ctx.__enter__()
        try:
            row = session.query(WorldInstallJob).filter(WorldInstallJob.job_id == parsed_job_id).first()
            if row is None:
                return
            current = list(row.event_log or [])
            current.append({"stage": stage, "payload": payload, "ts": datetime.utcnow().isoformat()})
            row.event_log = current
            row.updated_at = datetime.utcnow()
            if owns_session:
                session.commit()
        finally:
            if owns_session:
                session_ctx.__exit__(None, None, None)

    def finish_job(
        self,
        job_id: str,
        success: bool,
        error_code: Optional[str],
        summary: Dict[str, Any],
        session: Optional[Session] = None,
    ) -> None:
        parsed_job_id = self._parse_job_id(job_id)
        if parsed_job_id is None:
            return
        owns_session = session is None
        if session is None:
            session_ctx = db_session_context()
            session = session_ctx.__enter__()
        try:
            row = session.query(WorldInstallJob).filter(WorldInstallJob.job_id == parsed_job_id).first()
            if row is None:
                return
            row.status = "success" if success else "failed"
            row.error_code = error_code
            row.summary = summary or {}
            row.finished_at = datetime.utcnow()
            row.updated_at = datetime.utcnow()
            if owns_session:
                session.commit()
        finally:
            if owns_session:
                session_ctx.__exit__(None, None, None)


class WorldInstallerService:
    """Service wrapper for world runtime operations with job/state persistence."""

    def __init__(self, repository: WorldRuntimeRepository):
        self.repository = repository

    def run_with_job(
        self,
        world_id: str,
        action: str,
        status_before: str,
        enter_status: str,
        exec_fn: Callable[[str], OperationResult],
        requested_by: str = "system",
    ) -> OperationResult:
        with db_session_context() as session:
            # lock current state row when exists, to reduce concurrent state races.
            self.repository.get_state_for_update(session, world_id)

            try:
                job_id = self.repository.create_job(
                    world_id, action, requested_by=requested_by, session=session
                )
            except IntegrityError:
                session.rollback()
                return OperationResult(
                    ok=False,
                    world_id=world_id,
                    status_before=status_before,
                    status_after=status_before,
                    error_code=WorldErrorCode.WORLD_BUSY.value,
                    message=f"world action '{action}' is already running",
                    details={"action": action},
                )

            self.repository.upsert_state(
                world_id, enter_status, updated_by=requested_by, session=session
            )
            self.repository.append_job_event(
                job_id,
                "start",
                {"action": action, "status_before": status_before},
                session=session,
            )

            result: OperationResult = exec_fn(job_id)
            result.job_id = job_id

            if result.ok:
                self.repository.upsert_state(
                    world_id,
                    result.status_after,
                    version=result.details.get("version"),
                    metadata=result.details,
                    updated_by=requested_by,
                    session=session,
                )
                self.repository.finish_job(
                    job_id, True, None, result.details, session=session
                )
                session.commit()
                return result

            self.repository.upsert_state(
                world_id,
                WorldRuntimeStatus.FAILED.value,
                last_error_code=result.error_code,
                last_error_message=result.message,
                metadata=result.details,
                updated_by=requested_by,
                session=session,
            )
            self.repository.upsert_state(
                world_id,
                WorldRuntimeStatus.BROKEN.value,
                last_error_code=result.error_code,
                last_error_message=result.message,
                metadata=result.details,
                updated_by=requested_by,
                session=session,
            )
            self.repository.finish_job(
                job_id, False, result.error_code, result.details, session=session
            )
            result.status_after = WorldRuntimeStatus.BROKEN.value
            session.commit()
            return result
