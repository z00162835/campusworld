"""
Runtime persistence contracts for world packages (status, jobs, structured errors).

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
from typing import Any, Callable, Dict, List, Optional
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
    WORLD_DATA_UNAVAILABLE = "WORLD_DATA_UNAVAILABLE"
    WORLD_DATA_INVALID = "WORLD_DATA_INVALID"
    WORLD_DATA_SCHEMA_UNSUPPORTED = "WORLD_DATA_SCHEMA_UNSUPPORTED"
    WORLD_DATA_REFERENCE_BROKEN = "WORLD_DATA_REFERENCE_BROKEN"
    WORLD_DATA_BASELINE_MISMATCH = "WORLD_DATA_BASELINE_MISMATCH"
    WORLD_DATA_SEMANTIC_CONFLICT = "WORLD_DATA_SEMANTIC_CONFLICT"
    WORLD_BUSY = "WORLD_BUSY"
    WORLD_INTERNAL_ERROR = "WORLD_INTERNAL_ERROR"
    # Graph seed / ontology alignment (GameLoader, pipeline, world graph_profile)
    GRAPH_SEED_REFERENCE_BROKEN = "GRAPH_SEED_REFERENCE_BROKEN"
    GRAPH_SEED_TYPE_UNKNOWN = "GRAPH_SEED_TYPE_UNKNOWN"
    GRAPH_SEED_RELATIONSHIP_UNSUPPORTED = "GRAPH_SEED_RELATIONSHIP_UNSUPPORTED"
    GRAPH_SEED_FAILED = "GRAPH_SEED_FAILED"


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

    def list_world_ids_with_status(self, status: str) -> List[str]:
        """Return world_id values whose control-plane row matches ``status`` (e.g. ``installed``)."""
        with db_session_context() as session:
            rows = (
                session.query(WorldRuntimeState.world_id)
                .filter(WorldRuntimeState.status == status)
                .order_by(WorldRuntimeState.world_id)
                .all()
            )
            return [r[0] for r in rows]

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
                "metadata": row.state_metadata or {},
                "updated_at": row.updated_at,
            }

    def get_state_for_update(self, session: Session, world_id: str) -> Dict[str, Any]:
        # Stable lock order if the query ever returns multiple rows (defensive).
        row = (
            session.query(WorldRuntimeState)
            .filter(WorldRuntimeState.world_id == world_id)
            .order_by(WorldRuntimeState.world_id)
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
            "metadata": row.state_metadata or {},
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _execute_upsert_state(
        session: Session,
        world_id: str,
        status: str,
        version: Optional[str],
        last_error_code: Optional[str],
        last_error_message: Optional[str],
        payload: Dict[str, Any],
        updated_by: str,
    ) -> None:
        # Core Table + physical column name "metadata" so ON CONFLICT excluded.* matches INSERT (ORM insert + state_metadata broke excluded.state_metadata).
        tbl = WorldRuntimeState.__table__
        ins = pg_insert(tbl).values(
            world_id=world_id,
            status=status,
            version=version,
            last_error_code=last_error_code,
            last_error_message=last_error_message,
            metadata=payload,
            updated_by=updated_by,
        )
        stmt = ins.on_conflict_do_update(
            index_elements=[tbl.c.world_id],
            set_={
                tbl.c.status: ins.excluded.status,
                tbl.c.version: ins.excluded.version,
                tbl.c.last_error_code: ins.excluded.last_error_code,
                tbl.c.last_error_message: ins.excluded.last_error_message,
                tbl.c["metadata"]: ins.excluded["metadata"],
                tbl.c.updated_by: ins.excluded.updated_by,
                tbl.c.updated_at: func.now(),
            },
        )
        session.execute(stmt)

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
        if session is None:
            with db_session_context() as s:
                self._execute_upsert_state(
                    s,
                    world_id,
                    status,
                    version,
                    last_error_code,
                    last_error_message,
                    payload,
                    updated_by,
                )
                s.commit()
        else:
            self._execute_upsert_state(
                session,
                world_id,
                status,
                version,
                last_error_code,
                last_error_message,
                payload,
                updated_by,
            )

    def create_job(
        self,
        world_id: str,
        action: str,
        requested_by: str = "system",
        request_fingerprint: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> str:
        def _add_and_persist(s: Session, commit: bool) -> str:
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
            s.add(row)
            if commit:
                s.commit()
            else:
                s.flush()
            s.refresh(row)
            return str(row.job_id)

        if session is None:
            with db_session_context() as s:
                return _add_and_persist(s, commit=True)
        return _add_and_persist(session, commit=False)

    def append_job_event(
        self, job_id: str, stage: str, payload: Dict[str, Any], session: Optional[Session] = None
    ) -> None:
        parsed_job_id = self._parse_job_id(job_id)
        if parsed_job_id is None:
            return

        def _append_on(s: Session) -> bool:
            row = s.query(WorldInstallJob).filter(WorldInstallJob.job_id == parsed_job_id).first()
            if row is None:
                return False
            current = list(row.event_log or [])
            current.append({"stage": stage, "payload": payload, "ts": datetime.utcnow().isoformat()})
            row.event_log = current
            row.updated_at = datetime.utcnow()
            return True

        if session is None:
            with db_session_context() as s:
                if _append_on(s):
                    s.commit()
        else:
            _append_on(session)

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

        def _finish(s: Session, commit: bool) -> None:
            row = s.query(WorldInstallJob).filter(WorldInstallJob.job_id == parsed_job_id).first()
            if row is None:
                return
            row.status = "success" if success else "failed"
            row.error_code = error_code
            row.summary = summary or {}
            row.finished_at = datetime.utcnow()
            row.updated_at = datetime.utcnow()
            if commit:
                s.commit()

        if session is None:
            with db_session_context() as s:
                _finish(s, commit=True)
        else:
            _finish(session, commit=False)


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
