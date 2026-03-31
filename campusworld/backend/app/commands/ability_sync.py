"""
Command ability graph synchronization.

Creates/updates `system_command_ability` nodes to represent registered commands as
semantic capabilities in the world graph. Authorization remains in `command_policies`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.log import get_logger, LoggerNames
from app.models.graph import Node, NodeType
from app.models.root_manager import RootNodeManager


logger = get_logger(LoggerNames.COMMAND)


def _get_or_create_command_ability_type(session: Session) -> Optional[int]:
    try:
        row = session.query(NodeType).filter(NodeType.type_code == "system_command_ability").first()
        if row:
            return row.id

        nt = NodeType(
            type_code="system_command_ability",
            type_name="SystemCommandAbility",
            typeclass="app.models.system.command_ability.SystemCommandAbility",
            classname="SystemCommandAbility",
            module_path="app.models.system.command_ability",
            description="Semantic capability node representing a command",
            schema_definition={
                "command_name": "string",
                "aliases": "json",
                "command_type": "string",
                "help_category": "string",
                "stability": "string",
                "input_schema": "json",
                "output_schema": "json",
                "updated_at": "string",
            },
            is_active=True,
        )
        session.add(nt)
        session.commit()
        session.refresh(nt)
        return nt.id
    except Exception as e:
        logger.error("command ability type ensure failed: %s", e)
        session.rollback()
        return None


def ensure_command_ability_nodes(session: Session) -> int:
    """
    Ensure ability nodes exist for all registered commands.

    Nodes are placed in SingularityRoom (root node) when available.
    Existing nodes are updated in-place.
    """
    from app.commands.registry import command_registry

    type_id = _get_or_create_command_ability_type(session)
    if not type_id:
        return 0

    root_mgr = RootNodeManager()
    root = root_mgr.get_root_node(session)
    root_node_id = root.id if root else None

    now = datetime.now().isoformat()
    touched = 0
    for cmd in command_registry.get_all_commands():
        command_name = cmd.name
        aliases = list(getattr(cmd, "aliases", []) or [])
        command_type = getattr(getattr(cmd, "command_type", None), "value", None) or str(getattr(cmd, "command_type", "system"))

        existing = session.query(Node).filter(
            and_(
                Node.type_code == "system_command_ability",
                Node.attributes["command_name"].astext == command_name,
                Node.is_active == True,  # noqa: E712
            )
        ).first()

        if existing:
            attrs = dict(existing.attributes or {})
            attrs.update(
                {
                    "command_name": command_name,
                    "aliases": aliases,
                    "command_type": command_type,
                    "updated_at": now,
                }
            )
            existing.attributes = attrs
            if root_node_id and not existing.location_id:
                existing.location_id = root_node_id
                existing.home_id = root_node_id
            session.add(existing)
            touched += 1
            continue

        node = Node(
            type_id=type_id,
            type_code="system_command_ability",
            name=command_name,
            description=f"Command ability: {command_name}",
            is_active=True,
            is_public=True,
            access_level="normal",
            location_id=root_node_id,
            home_id=root_node_id,
            attributes={
                "command_name": command_name,
                "aliases": aliases,
                "command_type": command_type,
                "updated_at": now,
            },
            tags=["system", "ability", "command_ability", "command", command_type],
        )
        session.add(node)
        session.commit()
        session.refresh(node)
        touched += 1

    return touched

