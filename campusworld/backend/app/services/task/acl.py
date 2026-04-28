"""Task pool ACL evaluator (Phase B).

SSOT: ``docs/task/SPEC/features/F05_TASK_POOL_FIRST_CLASS_REGISTRY.md §4``.

Evaluation order (F05 §4.1):

1. RBAC at command layer ensures the actor already holds e.g. ``task.publish``;
   this evaluator is invoked AFTER that check, never as a substitute.
2. Explicit ``principals`` whitelist short-circuits to ``allow``.
3. ``principal_kinds`` whitelist must be satisfied if specified; combined with
   any of the secondary clauses (``roles`` or ``groups``) yields ``allow``.
4. ``data_access_predicate`` (F11) is a hook left as ``False`` in v1; Phase C
   wiring will dispatch into ``app.services.data_access_policy``.
5. Otherwise the ``default`` field decides (``allow`` / ``deny``).

This module is **pure**: no DB, no logging side-effects. The ``AclDecision``
return value carries an ``allow`` flag plus a ``reason`` so callers can map
to specific exception classes (``PublishAclDenied`` vs ``ConsumeAclDenied``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.services.task.permissions import Principal


@dataclass(frozen=True)
class AclDecision:
    allow: bool
    reason: str

    def __bool__(self) -> bool:  # convenience
        return self.allow


_ALLOW = AclDecision(True, "")


def evaluate_acl(
    actor: Principal,
    acl: Optional[Dict[str, Any]],
    *,
    f11_evaluate=None,
) -> AclDecision:
    """Return :class:`AclDecision` for the given actor against a pool ACL.

    ``acl`` is the JSONB dict stored in ``task_pools.publish_acl`` /
    ``task_pools.consume_acl``. ``None`` or missing dict short-circuits to
    ``allow`` (back-compat for legacy pools); seeded pools always provide an
    explicit ``default``.
    """

    if not acl:
        return _ALLOW

    # Schema sanity: refuse silently bad shapes by treating as deny.
    if not isinstance(acl, dict):
        return AclDecision(False, "acl.schema_invalid")

    principals = set(acl.get("principals") or [])
    principal_kinds = set(acl.get("principal_kinds") or [])
    roles = set(acl.get("roles") or [])
    groups = set(acl.get("groups") or [])
    predicate = acl.get("data_access_predicate")
    default = (acl.get("default") or "deny").lower()

    # 1. Explicit principal id whitelist.
    if actor.id in principals:
        return AclDecision(True, "matched.principals")

    # 2. Kind + (role | group) intersection.
    kind_ok = (not principal_kinds) or (actor.kind in principal_kinds)
    if kind_ok:
        # If only kinds are configured (no role/group/predicate), treat the
        # kind whitelist as sufficient (consistent with seed pools and SPEC
        # §1.4 "publish_acl.principal_kinds 含 system 时允许").
        if not roles and not groups and not predicate:
            return AclDecision(True, "matched.principal_kinds")
        if roles and (actor.roles & roles):
            return AclDecision(True, "matched.roles")
        if groups and (actor.group_tags & groups):
            return AclDecision(True, "matched.groups")

    # 3. F11 data-access predicate hook (Phase C wires the real evaluator).
    if predicate:
        if f11_evaluate is None:
            # Conservatively deny in v1 if the caller did not provide an evaluator.
            return AclDecision(False, "data_access_predicate.no_evaluator")
        if bool(f11_evaluate(actor, predicate)):
            return AclDecision(True, "matched.data_access_predicate")

    # 4. Default fall-through.
    if default == "allow":
        return AclDecision(True, "matched.default_allow")
    return AclDecision(False, "denied.default_deny")


__all__ = [
    "AclDecision",
    "evaluate_acl",
]
