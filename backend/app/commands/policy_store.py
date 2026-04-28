"""Command authorization policy storage (DB-backed) and bootstrap helpers.

Policy baseline:
- Authz source of truth is the `command_policies` table.
- Non-admin commands should be usable by default (empty requirements => allow).
- Admin commands default to `admin.*` unless overridden explicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from app.core.database import Base
from app.commands.base import CommandType


class CommandPolicy(Base):
    """Persistent policy row for one command."""

    __tablename__ = "command_policies"
    __table_args__ = (
        UniqueConstraint("command_name", name="uq_command_policy_command_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    command_name = Column(String(128), nullable=False, index=True)
    required_permissions_any = Column(JSONB, nullable=False, default=list)
    required_permissions_all = Column(JSONB, nullable=False, default=list)
    required_roles_any = Column(JSONB, nullable=False, default=list)
    # Evennia-style expression, evaluated if present.
    policy_expr = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    scope = Column(String(64), nullable=False, default="global")
    version = Column(Integer, nullable=False, default=1)
    updated_by = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class CommandPolicyRepository:
    """Repository for CRUD-like operations on command policies."""

    def __init__(self, session: Session):
        self.session = session

    def get_policy(self, command_name: str) -> Optional[CommandPolicy]:
        if not command_name:
            return None
        return (
            self.session.query(CommandPolicy)
            .filter(CommandPolicy.command_name == command_name)
            .first()
        )

    def list_policies(self, *, enabled_only: bool = False) -> List[CommandPolicy]:
        query = self.session.query(CommandPolicy)
        if enabled_only:
            query = query.filter(CommandPolicy.enabled == True)  # noqa: E712
        return query.order_by(CommandPolicy.command_name.asc()).all()

    def upsert_policy(
        self,
        command_name: str,
        *,
        required_permissions_any: Optional[List[str]] = None,
        required_permissions_all: Optional[List[str]] = None,
        required_roles_any: Optional[List[str]] = None,
        enabled: bool = True,
        scope: str = "global",
        updated_by: Optional[str] = None,
        commit: bool = True,
    ) -> CommandPolicy:
        row = self.get_policy(command_name)
        if row is None:
            row = CommandPolicy(
                command_name=command_name,
                required_permissions_any=list(required_permissions_any or []),
                required_permissions_all=list(required_permissions_all or []),
                required_roles_any=list(required_roles_any or []),
                enabled=bool(enabled),
                scope=scope or "global",
                version=1,
                updated_by=updated_by,
            )
            self.session.add(row)
        else:
            row.required_permissions_any = list(required_permissions_any or [])
            row.required_permissions_all = list(required_permissions_all or [])
            row.required_roles_any = list(required_roles_any or [])
            row.enabled = bool(enabled)
            row.scope = scope or "global"
            row.version = int((row.version or 0) + 1)
            row.updated_by = updated_by
            row.updated_at = datetime.utcnow()
            self.session.add(row)

        if commit:
            self.session.commit()
            self.session.refresh(row)
        else:
            self.session.flush()
        return row

    def to_policy_dict(self, row: CommandPolicy) -> Dict[str, Any]:
        return {
            "id": row.id,
            "command_name": row.command_name,
            "required_permissions_any": list(row.required_permissions_any or []),
            "required_permissions_all": list(row.required_permissions_all or []),
            "required_roles_any": list(row.required_roles_any or []),
            "enabled": bool(row.enabled),
            "scope": row.scope,
            "version": row.version,
            "updated_by": row.updated_by,
        }


def ensure_default_command_policies(session: Session) -> int:
    """
    Ensure the policy table exists and that every registered command has a row.

    Existing rows are left unchanged.
    """
    from app.commands.policy_bootstrap import policy_seed_for
    from app.commands.registry import command_registry

    repo = CommandPolicyRepository(session)
    created = 0
    for cmd in command_registry.get_all_commands():
        if repo.get_policy(cmd.name) is not None:
            continue
        seed = policy_seed_for(cmd.name)
        # Default policy fallback:
        # - Admin commands are restricted by default.
        # - Non-admin commands are allowed by default (empty lists).
        if (
            not seed["required_permissions_any"]
            and not seed["required_permissions_all"]
            and not seed["required_roles_any"]
            and getattr(cmd, "command_type", None) == CommandType.ADMIN
        ):
            seed["required_permissions_any"] = ["admin.*"]
        repo.upsert_policy(
            cmd.name,
            required_permissions_any=seed["required_permissions_any"],
            required_permissions_all=seed["required_permissions_all"],
            required_roles_any=seed["required_roles_any"],
            enabled=True,
            updated_by="bootstrap",
            commit=False,
        )
        created += 1
    session.commit()
    return created

