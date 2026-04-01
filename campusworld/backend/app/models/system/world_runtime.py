"""
World runtime control-plane ORM models.

These models are intentionally separate from graph `Node/Relationship` to keep
runtime/job control data isolated from semantic digital-twin graph entities.
"""

from __future__ import annotations

import uuid as uuidlib

from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class WorldRuntimeState(Base):
    """Persistent runtime status per world package."""

    __tablename__ = "world_runtime_states"

    world_id = Column(String(128), primary_key=True)
    status = Column(String(32), nullable=False, index=True)
    version = Column(String(64), nullable=True)
    last_error_code = Column(String(128), nullable=True)
    last_error_message = Column(Text, nullable=True)
    # DB column remains "metadata"; Python name avoids Declarative reserved `metadata`.
    state_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_world_runtime_states_status", "status"),
        Index("ix_world_runtime_states_updated_at", "updated_at"),
    )


class WorldInstallJob(Base):
    """Install/uninstall/reload runtime job history for worlds."""

    __tablename__ = "world_install_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuidlib.uuid4)
    world_id = Column(String(128), nullable=False, index=True)
    action = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    requested_by = Column(String(128), nullable=True)
    request_fingerprint = Column(String(255), nullable=True, index=True)
    error_code = Column(String(128), nullable=True)
    event_log = Column(JSONB, nullable=False, default=list)
    summary = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_world_install_jobs_world_id", "world_id"),
        Index("ix_world_install_jobs_status", "status"),
        Index("ix_world_install_jobs_created_at", "created_at"),
        Index("ix_world_install_jobs_fingerprint", "request_fingerprint"),
    )
