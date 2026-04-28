from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol

from sqlalchemy.orm import Session

from app.models.system import AgentMemoryEntry, AgentRunRecord


class MemoryPort(Protocol):
    """Abstract memory access for ThinkingFramework (tests may use fakes)."""

    def start_run(
        self,
        run_id: uuid.UUID,
        correlation_id: Optional[str],
        phase: str,
        command_trace: List[Dict[str, Any]],
        status: str,
    ) -> None:
        ...

    def update_run(
        self,
        run_id: uuid.UUID,
        phase: str,
        command_trace: List[Dict[str, Any]],
        status: str,
        graph_ops_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        ...

    def finish_run(
        self,
        run_id: uuid.UUID,
        phase: str,
        command_trace: List[Dict[str, Any]],
        status: str,
        graph_ops_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        ...

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> None:
        ...


class SqlAlchemyMemoryPort:
    """MemoryPort backed by agent_memory / agent_run / LTM SQL tables."""

    def __init__(self, session: Session, agent_node_id: int):
        self._session = session
        self._agent_node_id = agent_node_id
        self._run_row_id: Optional[int] = None

    def _get_run_row(self, run_id: uuid.UUID) -> Optional[AgentRunRecord]:
        return (
            self._session.query(AgentRunRecord)
            .filter(
                AgentRunRecord.agent_node_id == self._agent_node_id,
                AgentRunRecord.run_id == run_id,
            )
            .first()
        )

    def start_run(
        self,
        run_id: uuid.UUID,
        correlation_id: Optional[str],
        phase: str,
        command_trace: List[Dict[str, Any]],
        status: str,
    ) -> None:
        row = AgentRunRecord(
            agent_node_id=self._agent_node_id,
            run_id=run_id,
            correlation_id=correlation_id,
            phase=phase,
            command_trace=list(command_trace),
            status=status,
            graph_ops_summary={},
        )
        self._session.add(row)
        self._session.flush()
        self._run_row_id = row.id

    def update_run(
        self,
        run_id: uuid.UUID,
        phase: str,
        command_trace: List[Dict[str, Any]],
        status: str,
        graph_ops_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        row = self._get_run_row(run_id)
        if row is None:
            return
        row.phase = phase
        row.command_trace = list(command_trace)
        row.status = status
        if graph_ops_summary is not None:
            row.graph_ops_summary = graph_ops_summary
        self._session.flush()

    def finish_run(
        self,
        run_id: uuid.UUID,
        phase: str,
        command_trace: List[Dict[str, Any]],
        status: str,
        graph_ops_summary: Optional[Dict[str, Any]] = None,
    ) -> None:
        row = self._get_run_row(run_id)
        if row is None:
            return
        row.phase = phase
        row.command_trace = list(command_trace)
        row.status = status
        if graph_ops_summary is not None:
            row.graph_ops_summary = graph_ops_summary
        row.ended_at = datetime.now(timezone.utc)
        self._session.flush()

    def append_raw(self, kind: str, payload: Dict[str, Any], session_id: Optional[uuid.UUID] = None) -> None:
        self._session.add(
            AgentMemoryEntry(
                agent_node_id=self._agent_node_id,
                session_id=session_id,
                kind=kind,
                payload=payload,
            )
        )
        self._session.flush()
