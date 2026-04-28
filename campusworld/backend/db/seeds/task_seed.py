"""Phase B seed data for the task system.

- ``DEFAULT_WORKFLOW_SEED`` — ``default_v1`` workflow definition (see F03 §2.3).
- ``SEED_TASK_POOLS`` — three Hicampus pools (see F05 §9).

These structures are also imported by Phase B unit tests so that the seed
contract is verified without requiring the database.
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# default_v1 workflow definition (docs/task/SPEC/features/F03 §2.3)
# ---------------------------------------------------------------------------

# Phase B implements a strict subset of the events declared here.
# The seed still installs the full default_v1 spec so that Phase C events
# (start / submit-review / approve / reject / handoff / fail / cancel / expand)
# can be unlocked via in-process state-machine extensions without a re-seed.
DEFAULT_WORKFLOW_SEED: Dict[str, Any] = {
    "key": "default_v1",
    "version": 1,
    "is_active": True,
    "description": "default task workflow v1 (docs/task/SPEC/features/F03 §2.3)",
    "spec": {
        "_schema_version": 1,
        "initial_state": "draft",
        "terminal_states": ["done", "cancelled", "failed"],
        "states": {
            "draft": {"expected_roles": ["owner"]},
            "open": {"expected_roles": ["owner"]},
            "claimed": {"expected_roles": ["owner", "executor"]},
            "in_progress": {"expected_roles": ["owner", "executor"]},
            "pending_review": {"expected_roles": ["owner", "executor", "approver"]},
            "approved": {"expected_roles": ["owner", "executor"]},
            "rejected": {"expected_roles": ["owner", "executor"]},
            "failed": {"expected_roles": []},
            "done": {"expected_roles": []},
            "cancelled": {"expected_roles": []},
        },
        "events": {
            # Phase B minimum set (5 events): create / publish / claim / assign / complete
            "create": {
                "from": ["__init__"],
                "to": "draft",
                "required_role": "owner",
            },
            "open": {
                "from": ["draft"],
                "to": "open",
                "required_role": "owner",
            },
            "publish": {
                "from": ["draft", "open"],
                "to": "open",
                "required_role": "owner",
                "preconditions": ["no_active_executor"],
                "side_effects": [
                    "update_pool(pool_id=:payload.pool_id)",
                    "check_publish_acl(:payload.pool_id)",
                ],
            },
            "claim": {
                "from": ["open", "rejected"],
                "to": "claimed",
                "required_role": "executor",
                "side_effects": ["add_assignment(role=executor, kind=actor)"],
            },
            "assign": {
                "from": ["open"],
                "to": "claimed",
                "required_role": "owner",
                "side_effects": ["add_assignment(role=executor, kind=payload.principal)"],
            },
            "start": {
                "from": ["claimed", "rejected"],
                "to": "in_progress",
                "required_role": "executor",
            },
            "submit-review": {
                "from": ["in_progress"],
                "to": "pending_review",
                "required_role": "executor",
                "side_effects": ["add_assignment(role=approver, kind=payload.approver)"],
            },
            "approve": {
                "from": ["pending_review"],
                "to": "approved",
                "required_role": "approver",
            },
            "reject": {
                "from": ["pending_review"],
                "to": "rejected",
                "required_role": "approver",
                "side_effects": ["retire_assignments(roles=[approver])"],
            },
            "handoff": {
                "from": ["approved"],
                "to": "in_progress",
                "required_role": "owner",
                "side_effects": [
                    "retire_assignments(roles=[executor])",
                    "add_assignment(role=executor, kind=payload.principal)",
                ],
            },
            "complete": {
                # Phase B minimal event set has no `start`; allow direct
                # completion from `claimed` for the create→publish→claim→complete
                # happy path while keeping Phase C states intact.
                "from": ["claimed", "in_progress", "approved"],
                "to": "done",
                "required_role": "executor",
                "preconditions": ["children_all_terminal"],
            },
            "fail": {
                "from": ["claimed", "in_progress"],
                "to": "failed",
                "required_role": "executor",
                "side_effects": ["retire_assignments(roles=[executor])"],
                "payload_schema": {
                    "failure_reason": "str",
                    "retry_attempt": "int",
                    "error_code": "str?",
                },
            },
            "cancel": {
                "from": [
                    "draft",
                    "open",
                    "claimed",
                    "in_progress",
                    "pending_review",
                    "approved",
                    "rejected",
                    "failed",
                ],
                "to": "cancelled",
                "required_role": "owner",
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Phase B seed pools (docs/task/SPEC/features/F05 §9)
# ---------------------------------------------------------------------------

# ACL schema (F05 §4 / §4.1):
#   { principals?, principal_kinds?, roles?, groups?, data_access_predicate?, default }
# Phase B layers ACL on top of RBAC: command-layer decorators check
# `task.publish` / `task.claim`; the pool ACL then further narrows.
# `system` virtual principal (SPEC §1.4 / OQ-28) gets `publish` access via
# the explicit `principal_kinds=[..., 'system']` whitelist below.

_DEFAULT_PUBLISH_ACL: Dict[str, Any] = {
    "_schema_version": 1,
    "principal_kinds": ["user", "agent", "system"],
    "default": "allow",
}

_DEFAULT_CONSUME_ACL: Dict[str, Any] = {
    "_schema_version": 1,
    "principal_kinds": ["user", "agent"],
    "default": "allow",
}


SEED_TASK_POOLS: List[Dict[str, Any]] = [
    {
        "key": "hicampus.cleaning",
        "display_name": "Hicampus 清洁任务池",
        "description": "校园清洁日常任务（保洁/巡保等）。",
        "default_workflow_ref": {
            "_schema_version": 1,
            "key": "default_v1",
            "version": 1,
        },
        "default_visibility": "pool_open",
        "default_priority": "normal",
        "publish_acl": dict(_DEFAULT_PUBLISH_ACL),
        "consume_acl": dict(_DEFAULT_CONSUME_ACL),
        "attributes": {"_schema_version": 1, "domain": "cleaning"},
    },
    {
        "key": "hicampus.security",
        "display_name": "Hicampus 安防任务池",
        "description": "校园安防巡检 / 异常处置任务。",
        "default_workflow_ref": {
            "_schema_version": 1,
            "key": "default_v1",
            "version": 1,
        },
        "default_visibility": "pool_open",
        "default_priority": "high",
        "publish_acl": dict(_DEFAULT_PUBLISH_ACL),
        "consume_acl": dict(_DEFAULT_CONSUME_ACL),
        "attributes": {"_schema_version": 1, "domain": "security"},
    },
    {
        "key": "hicampus.maintenance",
        "display_name": "Hicampus 维修任务池",
        "description": "校园设施 / 设备的维护与维修任务。",
        "default_workflow_ref": {
            "_schema_version": 1,
            "key": "default_v1",
            "version": 1,
        },
        "default_visibility": "pool_open",
        "default_priority": "normal",
        "publish_acl": dict(_DEFAULT_PUBLISH_ACL),
        "consume_acl": dict(_DEFAULT_CONSUME_ACL),
        "attributes": {"_schema_version": 1, "domain": "maintenance"},
    },
]


__all__ = [
    "DEFAULT_WORKFLOW_SEED",
    "SEED_TASK_POOLS",
]
