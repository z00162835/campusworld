"""
Centralized authorization policy for commands.

Policies are loaded from the database only (see CommandPolicy / CommandPolicyRepository).
Missing session, missing row, disabled row, or lookup errors are denied (fail-closed).

Logging: no warning/info/debug on authz outcomes. Only unexpected errors while loading
policy from the store are logged at exception level (with stack trace).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.core.permissions import permission_checker
from app.core.log import get_logger, LoggerNames
from app.commands.policy_store import CommandPolicyRepository
from app.commands.policy_expr import evaluate_policy_expr, PolicyExprError


logger = get_logger(LoggerNames.COMMAND)


@dataclass
class AuthzDecision:
    allowed: bool
    reason: str = ""
    missing: List[str] = field(default_factory=list)
    required_any: List[str] = field(default_factory=list)
    required_all: List[str] = field(default_factory=list)
    required_roles_any: List[str] = field(default_factory=list)


class CommandPolicyEvaluator:
    """Evaluate command access from DB-backed policy rows only."""

    def evaluate(self, command, context) -> AuthzDecision:
        db_session = getattr(context, "db_session", None)
        command_name = (getattr(command, "name", None) or "").strip()

        if db_session is None:
            return AuthzDecision(allowed=False, reason="no_db_session")

        if not command_name:
            return AuthzDecision(allowed=False, reason="invalid_command")

        try:
            repo = CommandPolicyRepository(db_session)
            row = repo.get_policy(command_name)
        except Exception:
            actor = getattr(context, "username", None)
            logger.exception(
                "authz policy_lookup_error actor=%s command=%s",
                actor,
                command_name,
            )
            return AuthzDecision(allowed=False, reason="policy_lookup_error")

        if row is None:
            return AuthzDecision(allowed=False, reason="no_policy")

        if not row.enabled:
            return AuthzDecision(allowed=False, reason="policy_disabled")

        user_permissions = list(getattr(context, "permissions", []) or [])
        user_roles = list(getattr(context, "roles", []) or [])

        policy_expr = getattr(row, "policy_expr", None)
        if isinstance(policy_expr, str) and policy_expr.strip():
            try:
                ok = evaluate_policy_expr(str(policy_expr), user_permissions=user_permissions, user_roles=user_roles)
            except PolicyExprError:
                return AuthzDecision(allowed=False, reason="policy_expr_invalid")
            if not ok:
                return AuthzDecision(allowed=False, reason="policy_expr_denied")
            return AuthzDecision(allowed=True, reason="allowed", missing=[])

        required_any = list(row.required_permissions_any or [])
        required_all = list(row.required_permissions_all or [])
        required_roles_any = list(row.required_roles_any or [])

        if required_roles_any:
            ok_role = any(
                permission_checker.check_role(user_roles, r) for r in required_roles_any
            )
            if not ok_role:
                return AuthzDecision(
                    allowed=False,
                    reason="missing_any_role",
                    missing=list(required_roles_any),
                    required_any=required_any,
                    required_all=required_all,
                    required_roles_any=required_roles_any,
                )

        missing = [
            p
            for p in required_all
            if not permission_checker.check_permission(user_permissions, p)
        ]
        if missing:
            return AuthzDecision(
                allowed=False,
                reason="missing_all_permissions",
                missing=missing,
                required_any=required_any,
                required_all=required_all,
                required_roles_any=required_roles_any,
            )

        if required_any:
            ok_any = any(
                permission_checker.check_permission(user_permissions, p) for p in required_any
            )
            if not ok_any:
                return AuthzDecision(
                    allowed=False,
                    reason="missing_any_permissions",
                    missing=list(required_any),
                    required_any=required_any,
                    required_all=required_all,
                    required_roles_any=required_roles_any,
                )

        return AuthzDecision(
            allowed=True,
            reason="allowed",
            missing=[],
            required_any=required_any,
            required_all=required_all,
            required_roles_any=required_roles_any,
        )
