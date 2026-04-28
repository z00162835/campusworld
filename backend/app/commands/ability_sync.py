"""
Command ability graph synchronization.

Creates/updates `system_command_ability` nodes to represent registered commands as
semantic capabilities in the world graph. Authorization remains in `command_policies`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.log import get_logger, LoggerNames
from app.models.graph import Node, NodeType
from app.models.root_manager import RootNodeManager
from db.ontology.schema_envelope import system_command_ability_node_type_schema_definition


logger = get_logger(LoggerNames.COMMAND)


def _sync_llm_hints_from_command(cmd: Any, attrs: Dict[str, Any]) -> None:
    """Mirror registry one-line text into graph ``llm_hint`` / ``llm_hint_i18n`` for AICO tools."""
    from app.commands.i18n.command_resource import merge_description_i18n_for_ability
    from app.commands.i18n.locale_text import tool_manifest_locale

    loc = tool_manifest_locale()
    one = ""
    if hasattr(cmd, "get_localized_description"):
        try:
            one = (cmd.get_localized_description(loc) or "").strip()
        except Exception:
            one = ""
    if not one:
        one = (getattr(cmd, "description", None) or "").strip()
    if one:
        attrs["llm_hint"] = one
    else:
        attrs.pop("llm_hint", None)
    legacy = getattr(cmd, "description_i18n", None)
    merged = merge_description_i18n_for_ability(
        str(getattr(cmd, "name", "") or "").strip(),
        legacy if isinstance(legacy, dict) else None,
    )
    if merged:
        attrs["llm_hint_i18n"] = {str(k): str(v) for k, v in merged.items() if str(v).strip()}
    else:
        attrs.pop("llm_hint_i18n", None)


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
            schema_definition=system_command_ability_node_type_schema_definition(),
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
                    "entity_kind": "ability",
                    "presentation_domains": ["help", "npc"],
                    "access_locks": {"view": "all()", "invoke": "all()"},
                    "updated_at": now,
                }
            )
            _sync_llm_hints_from_command(cmd, attrs)
            existing.attributes = attrs
            if root_node_id and not existing.location_id:
                existing.location_id = root_node_id
                existing.home_id = root_node_id
            session.add(existing)
            touched += 1
            continue

        base_attr = {
            "command_name": command_name,
            "aliases": aliases,
            "command_type": command_type,
            "entity_kind": "ability",
            "presentation_domains": ["help", "npc"],
            "access_locks": {"view": "all()", "invoke": "all()"},
            "updated_at": now,
        }
        _sync_llm_hints_from_command(cmd, base_attr)
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
            attributes=base_attr,
            tags=["system", "ability", "command_ability", "command", command_type],
        )
        session.add(node)
        touched += 1

    try:
        session.commit()
    except Exception as e:
        logger.error("command ability batch commit failed: %s", e)
        session.rollback()
        raise
    return touched

