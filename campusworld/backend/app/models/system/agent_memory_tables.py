"""
Agent memory and run audit tables (ORM).

DDL + indexes: ``db/schemas/database_schema.sql`` (agent memory section).
"""

from __future__ import annotations

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func

from app.core.database import Base


class AgentMemoryEntry(Base):
    __tablename__ = "agent_memory_entries"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    kind = Column(String(32), nullable=False)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentRunRecord(Base):
    __tablename__ = "agent_run_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    run_id = Column(UUID(as_uuid=True), nullable=False)
    correlation_id = Column(Text, nullable=True)
    phase = Column(String(32), nullable=False)
    command_trace = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    status = Column(String(32), nullable=False)
    graph_ops_summary = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)


class AgentLongTermMemory(Base):
    __tablename__ = "agent_long_term_memory"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    summary = Column(Text, nullable=False, server_default="")
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    source_memory_entry_id = Column(
        BigInteger,
        ForeignKey("agent_memory_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    graph_node_id = Column(Integer, nullable=True)
    relationship_id = Column(Integer, nullable=True)
    version = Column(Integer, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    embedding = Column(Vector(1536), nullable=True)
    embedding_model = Column(String(64), nullable=True)
    embedding_updated_at = Column(DateTime(timezone=True), nullable=True)


class AgentLongTermMemoryLink(Base):
    """Directed edges between LTM rows for the same agent."""

    __tablename__ = "agent_long_term_memory_links"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    agent_node_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False)
    source_ltm_id = Column(
        BigInteger,
        ForeignKey("agent_long_term_memory.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_ltm_id = Column(
        BigInteger,
        ForeignKey("agent_long_term_memory.id", ondelete="CASCADE"),
        nullable=False,
    )
    link_type = Column(String(64), nullable=False)
    weight = Column(Float, nullable=True, server_default="1.0")
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
