"""
Unified command invocation gateway (for NPC/Agent calls).

This mirrors the SSH/HTTP execution chain:
- Parse command line
- Resolve command from registry
- Authorize via CommandPolicyEvaluator (DB-backed)
- Execute command

NPC/world code should call this instead of invoking command implementations directly.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from app.commands.base import CommandContext, CommandResult
from app.commands.registry import command_registry
from app.core.database import db_session_context
from app.commands.policy_expr import evaluate_policy_expr, PolicyExprError
from app.models.graph import Node


def invoke_command_line(
    *,
    actor_id: str,
    actor_name: str,
    session_id: str = "npc_session",
    permissions: Optional[List[str]] = None,
    roles: Optional[List[str]] = None,
    command_line: str,
    caller: Optional[Any] = None,
    game_state: Optional[Dict[str, Any]] = None,
) -> CommandResult:
    line = (command_line or "").strip()
    if not line:
        return CommandResult.success_result("")

    parts = line.split()
    command_name = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []

    with db_session_context() as db_session:
        ctx = CommandContext(
            user_id=str(actor_id),
            username=str(actor_name),
            session_id=str(session_id),
            permissions=list(permissions or []),
            roles=list(roles or []),
            caller=caller,
            game_state=game_state or {},
            metadata={},
            db_session=db_session,
        )

        cmd = command_registry.get_command(command_name)
        if not cmd:
            return CommandResult.error_result(f"Command '{command_name}' not found")

        # Ability-node invoke lock gate (semantic plane), if ability node exists.
        ability_node = (
            db_session.query(Node)
            .filter(
                Node.type_code == "system_command_ability",
                Node.attributes["command_name"].astext == command_name,
                Node.is_active == True,  # noqa: E712
            )
            .first()
        )
        if ability_node:
            attrs = dict(ability_node.attributes or {})
            locks = attrs.get("access_locks", {}) if isinstance(attrs.get("access_locks", {}), dict) else {}
            invoke_lock = str(locks.get("invoke", "all()"))
            try:
                ok = evaluate_policy_expr(
                    invoke_lock,
                    user_permissions=list(permissions or []),
                    user_roles=list(roles or []),
                    object_attrs=attrs,
                )
            except PolicyExprError:
                ok = False
            if not ok:
                return CommandResult.error_result(f"Permission denied for command '{command_name}'")

        decision = command_registry.authorize_command(cmd, ctx)
        if not decision.allowed:
            return CommandResult.error_result(f"Permission denied for command '{command_name}'")

        return cmd.execute(ctx, args)

