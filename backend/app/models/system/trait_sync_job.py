"""
Trait sync job model for eventual consistency updates.
"""

from __future__ import annotations

import uuid as uuidlib

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class TraitSyncJob(Base):
    __tablename__ = "trait_sync_jobs"

    job_id = Column(UUID(as_uuid=True), primary_key=True, default=uuidlib.uuid4)
    domain = Column(String(32), nullable=False)  # node | relationship
    type_code = Column(String(128), nullable=False)
    reason = Column(String(64), nullable=False, default="type_trait_changed")
    status = Column(String(32), nullable=False, default="pending")  # pending|running|done|failed
    retries = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=5)
    payload = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, onupdate=func.now(), server_default=func.now())
