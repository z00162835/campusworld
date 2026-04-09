"""
API key persistence model.
"""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True)
    kid = Column(String(64), unique=True, nullable=False, index=True)
    owner_account_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(256), nullable=False)
    salt = Column(String(128), nullable=False)
    algorithm = Column(String(32), nullable=False, default="pbkdf2_sha256")
    iterations = Column(Integer, nullable=False, default=210000)
    name = Column(String(128), nullable=True)
    scopes = Column(JSONB, nullable=False, default=list)
    revoked = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    last_used_ip = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("ix_api_keys_owner_revoked", "owner_account_id", "revoked"),
    )
