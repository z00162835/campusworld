"""Task state machine — single write-path for all task transitions (Phase B).

SSOT: ``docs/task/SPEC/features/F03_TASK_COLLABORATION_WORKFLOW.md`` §3.

Phase B implements **only** the five events ``create / publish / claim /
assign / complete``. Phase C events (``start / submit-review / approve /
reject / handoff / fail / cancel``) raise :class:`WorkflowEventNotAllowed` at
the top of :func:`transition` even though the seeded workflow definition
contains them. This keeps the state machine code path narrow and easy to
review while the seed retains forward-compatibility.

Invariants (SPEC §1.3) enforced here:

* I1 — ``nodes.attributes.current_state`` is always equal to the most recent
  ``task_state_transitions.to_state`` for the task.
* I3 — only this module writes to ``task_state_transitions``, ``task_outbox``,
  ``task_assignments`` and ``nodes.attributes.{current_state,state_version}``.
* I4 — ``state_version`` advances monotonically via optimistic locking;
  ``event_seq`` is monotonic per task (held by the unique constraint).
* I5 — every successful return path commits a single transaction; any error
  rolls everything back, including the outbox row.
* I6 — non-NULL ``idempotency_key`` collisions short-circuit and return the
  recorded transition without re-applying side effects.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.task.acl import AclDecision, evaluate_acl
from app.services.task.errors import (
    AlreadyClaimedError,
    OptimisticLockError,
    PoolInactive,
    PoolNotFound,
    PreconditionFailed,
    ConsumeAclDenied,
    PublishAclDenied,
    RoleRequiredError,
    WorkflowDefinitionInactive,
    WorkflowDefinitionNotFound,
    WorkflowEventNotAllowed,
)
from app.services.task.permissions import Principal


logger = logging.getLogger(__name__)


# Phase B accepts only these events. The seeded ``default_v1`` definition
# carries Phase C events too, but ``transition`` rejects them outright until
# the corresponding handlers ship.
_PHASE_B_EVENTS = frozenset({"create", "publish", "claim", "assign", "complete"})

# Stage column values per (event, to_state).
_STAGE_BY_TO_STATE = {
    "draft": "open",
    "open": "open",
    "claimed": "claimed",
    "in_progress": "in_progress",
    "pending_review": "pending_review",
    "approved": "approved",
    "rejected": "rejected",
    "done": "done",
    "failed": "done",
    "cancelled": "done",
}


# task_outbox.event_kind canonical mapping for Phase B.
_OUTBOX_EVENT_KIND = {
    "create": "task.created",
    "publish": "task.published",
    "claim": "task.claimed",
    "assign": "task.assigned",
    "complete": "task.completed",
}


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TransitionResult:
    """Return value of :func:`transition`.

    See F03 §4 for the canonical field list.
    """

    task_id: int
    from_state: str
    to_state: str
    event: str
    event_seq: int
    state_version: int
    idempotent_replay: bool
    correlation_id: Optional[str]
    trace_id: Optional[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ensure_correlation(correlation_id: Optional[str]) -> str:
    return correlation_id or f"task-{uuid.uuid4()}"


def _ensure_trace(trace_id: Optional[str]) -> str:
    return trace_id or f"trace-{uuid.uuid4()}"


@contextmanager
def _transaction(session: Optional[Session]) -> Iterator[Session]:
    """Yield a transactional ``Session``.

    When the caller provides one we wrap with ``session.begin_nested()``
    (SAVEPOINT) so an outer transaction can compose; otherwise we open a
    fresh session via ``db_session_context``.
    """
    if session is not None:
        if session.in_transaction():
            with session.begin_nested():
                yield session
        else:
            with session.begin():
                yield session
        return

    from app.core.database import db_session_context

    with db_session_context() as fresh:
        with fresh.begin():
            yield fresh


def _load_workflow_spec(
    session: Session, *, key: str, version: int
) -> Dict[str, Any]:
    row = session.execute(
        text(
            """
            SELECT spec, is_active
              FROM task_workflow_definitions
             WHERE key = :key AND version = :version
            """
        ),
        {"key": key, "version": version},
    ).first()
    if row is None:
        raise WorkflowDefinitionNotFound(f"workflow {key}:{version} not found")
    spec = row[0]
    is_active = bool(row[1])
    if isinstance(spec, str):
        spec = json.loads(spec)
    if not is_active:
        raise WorkflowDefinitionInactive(f"workflow {key}:{version} is_active=false")
    if not isinstance(spec, dict):
        raise WorkflowDefinitionNotFound(f"workflow {key}:{version} spec not dict")
    return spec


def _resolve_active_workflow_version(session: Session, *, key: str) -> int:
    """Pin to MAX(version) WHERE is_active for ``create`` events (F03 §2.5)."""
    row = session.execute(
        text(
            """
            SELECT version
              FROM task_workflow_definitions
             WHERE key = :key AND is_active
             ORDER BY version DESC
             LIMIT 1
            """
        ),
        {"key": key},
    ).first()
    if row is None:
        raise WorkflowDefinitionNotFound(
            f"no active workflow_definition for key={key}"
        )
    return int(row[0])


def _check_idempotency(
    session: Session,
    *,
    task_id: int,
    idempotency_key: Optional[str],
) -> Optional[TransitionResult]:
    if not idempotency_key:
        return None
    row = session.execute(
        text(
            """
            SELECT event_seq, from_state, to_state, event, correlation_id, trace_id
              FROM task_state_transitions
             WHERE task_node_id = :tid AND idempotency_key = :key
            """
        ),
        {"tid": task_id, "key": idempotency_key},
    ).first()
    if row is None:
        return None

    # Pull current state_version off the node row to round-trip the result.
    snap = session.execute(
        text("SELECT (attributes->>'state_version')::int FROM nodes WHERE id = :tid"),
        {"tid": task_id},
    ).first()
    state_version = int(snap[0]) if snap and snap[0] is not None else 0

    return TransitionResult(
        task_id=task_id,
        from_state=row[1],
        to_state=row[2],
        event=row[3],
        event_seq=int(row[0]),
        state_version=state_version,
        idempotent_replay=True,
        correlation_id=row[4],
        trace_id=row[5],
    )


def _check_create_idempotency(
    session: Session,
    *,
    actor: Principal,
    idempotency_key: Optional[str],
) -> Optional[TransitionResult]:
    """Cross-task create replay keyed by actor + idempotency_key.

    The table-level unique index protects `(task_node_id, idempotency_key)` only.
    For `create_task` we need to prevent duplicate task rows on client retries,
    so we lookup prior `event='create'` records for the same actor/key pair.
    """
    if not idempotency_key:
        return None
    row = session.execute(
        text(
            """
            SELECT t.task_node_id,
                   t.event_seq,
                   t.from_state,
                   t.to_state,
                   t.event,
                   t.correlation_id,
                   t.trace_id,
                   (n.attributes->>'state_version')::int AS state_version
              FROM task_state_transitions t
              JOIN nodes n ON n.id = t.task_node_id
             WHERE t.event = 'create'
               AND t.idempotency_key = :idem
               AND t.actor_principal_kind = :actor_kind
               AND (
                    (:actor_kind = 'system' AND t.actor_principal_id IS NULL)
                    OR t.actor_principal_id = :actor_id
               )
             ORDER BY t.created_at DESC
             LIMIT 1
            """
        ),
        {
            "idem": idempotency_key,
            "actor_kind": actor.kind,
            "actor_id": actor.id,
        },
    ).first()
    if row is None:
        return None
    return TransitionResult(
        task_id=int(row[0]),
        from_state=row[2],
        to_state=row[3],
        event=row[4],
        event_seq=int(row[1]),
        state_version=int(row[7] or 0),
        idempotent_replay=True,
        correlation_id=row[5],
        trace_id=row[6],
    )


def _check_required_role(
    session: Session,
    *,
    task_id: int,
    actor: Principal,
    required_role: str,
) -> None:
    """``actor_principal`` must hold ``role`` on an active assignment row."""
    if actor.kind == "system":
        # SPEC §1.4 末段：``system`` 是特权主体，跳过 role check。
        return
    row = session.execute(
        text(
            """
            SELECT 1
              FROM task_assignments
             WHERE task_node_id = :tid
               AND is_active = TRUE
               AND role = :role
               AND principal_id = :pid
               AND principal_kind = :pkind
             LIMIT 1
            """
        ),
        {"tid": task_id, "role": required_role, "pid": actor.id, "pkind": actor.kind},
    ).first()
    if row is None:
        raise RoleRequiredError(
            f"actor (id={actor.id}, kind={actor.kind}) lacks active assignment "
            f"with role={required_role} on task {task_id}"
        )


def _retire_assignments(session: Session, *, task_id: int, roles: list[str]) -> None:
    if not roles:
        return
    session.execute(
        text(
            """
            UPDATE task_assignments
               SET is_active = FALSE, released_at = now()
             WHERE task_node_id = :tid
               AND is_active = TRUE
               AND role = ANY(:roles)
            """
        ),
        {"tid": task_id, "roles": list(roles)},
    )


def _add_assignment(
    session: Session,
    *,
    task_id: int,
    role: str,
    stage: str,
    actor: Principal,
    target_principal_id: Optional[int] = None,
    target_principal_kind: Optional[str] = None,
    target_principal_tag: Optional[str] = None,
) -> None:
    """Insert a new active assignment row.

    Either (principal_id + principal_kind) for non-group, or (principal_tag +
    principal_kind='group') per ``chk_task_assignments_principal_shape``.
    """
    pid = target_principal_id
    pkind = target_principal_kind
    ptag = target_principal_tag
    if pkind is None:
        # Default: assignment to the actor themself (used by `claim`, `create`).
        pid = actor.id
        pkind = actor.kind
        ptag = None
    elif pkind == "group":
        if ptag is None:
            raise ValueError("group assignment requires principal_tag")
        pid = None
    else:
        if pid is None:
            raise ValueError("non-group assignment requires principal_id")
        ptag = None

    session.execute(
        text(
            """
            INSERT INTO task_assignments
                (task_node_id, principal_id, principal_kind, principal_tag,
                 role, stage, is_active, assigned_by, assigned_at)
            VALUES
                (:tid, :pid, :pkind, :ptag, :role, :stage, TRUE,
                 :assigned_by, now())
            """
        ),
        {
            "tid": task_id,
            "pid": pid,
            "pkind": pkind,
            "ptag": ptag,
            "role": role,
            "stage": stage,
            "assigned_by": actor.id if actor.kind != "system" else None,
        },
    )


def _next_event_seq(session: Session, *, task_id: int) -> int:
    row = session.execute(
        text(
            "SELECT COALESCE(MAX(event_seq), 0) + 1 FROM task_state_transitions WHERE task_node_id = :tid"
        ),
        {"tid": task_id},
    ).first()
    return int(row[0]) if row and row[0] is not None else 1


def _update_node_state(
    session: Session,
    *,
    task_id: int,
    new_state: str,
    expected_version: int,
    extra_updates: Optional[Dict[str, Any]] = None,
) -> int:
    """Bump current_state + state_version atomically; return new state_version.

    Raises :class:`OptimisticLockError` if no row matched the expected version.
    """
    # Build attribute patch JSON.
    patch: Dict[str, Any] = {
        "current_state": new_state,
    }
    if extra_updates:
        patch.update(extra_updates)
    patch_json = json.dumps(patch, ensure_ascii=False)

    row = session.execute(
        text(
            """
            UPDATE nodes
               SET attributes = jsonb_set(
                       attributes || CAST(:patch AS jsonb),
                       '{state_version}',
                       to_jsonb(((attributes->>'state_version')::int + 1)))
             WHERE id = :tid
               AND type_code = 'task'
               AND (attributes->>'state_version')::int = :expected
            RETURNING (attributes->>'state_version')::int
            """
        ),
        {"tid": task_id, "patch": patch_json, "expected": expected_version},
    ).first()
    if row is None:
        raise OptimisticLockError(
            f"task {task_id}: expected_version={expected_version} did not match"
        )
    return int(row[0])


def _insert_state_transition(
    session: Session,
    *,
    task_id: int,
    event_seq: int,
    idempotency_key: Optional[str],
    from_state: str,
    to_state: str,
    event: str,
    actor: Principal,
    stage: str,
    reason: Optional[str],
    correlation_id: Optional[str],
    trace_id: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> None:
    metadata = metadata or {}
    metadata.setdefault("_schema_version", 1)
    session.execute(
        text(
            """
            INSERT INTO task_state_transitions
                (task_node_id, event_seq, idempotency_key, idempotency_expires_at,
                 from_state, to_state, event,
                 actor_principal_id, actor_principal_kind, stage, reason,
                 correlation_id, trace_id, metadata, created_at)
            VALUES
                (:tid, :seq, :idem,
                 CASE WHEN :idem IS NULL THEN NULL ELSE now() + INTERVAL '7 days' END,
                 :from_state, :to_state, :event,
                 :actor_id, :actor_kind, :stage, :reason,
                 :corr, :trace, CAST(:metadata AS jsonb), now())
            """
        ),
        {
            "tid": task_id,
            "seq": event_seq,
            "idem": idempotency_key,
            "from_state": from_state,
            "to_state": to_state,
            "event": event,
            "actor_id": actor.id if actor.kind != "system" else None,
            "actor_kind": actor.kind,
            "stage": stage,
            "reason": reason,
            "corr": correlation_id,
            "trace": trace_id,
            "metadata": json.dumps(metadata, ensure_ascii=False),
        },
    )


def _insert_outbox(
    session: Session,
    *,
    task_id: int,
    pool_key: Optional[str],
    event_kind: str,
    payload: Dict[str, Any],
    correlation_id: Optional[str],
    trace_id: Optional[str],
) -> None:
    payload = dict(payload)
    payload.setdefault("_schema_version", 1)
    session.execute(
        text(
            """
            INSERT INTO task_outbox
                (task_node_id, pool_key, event_kind, payload,
                 correlation_id, trace_id, created_at)
            VALUES
                (:tid, :pool_key, :kind, CAST(:payload AS jsonb),
                 :corr, :trace, now())
            """
        ),
        {
            "tid": task_id,
            "pool_key": pool_key,
            "kind": event_kind,
            "payload": json.dumps(payload, ensure_ascii=False),
            "corr": correlation_id,
            "trace": trace_id,
        },
    )


def _load_pool(session: Session, *, pool_id: int) -> Dict[str, Any]:
    row = session.execute(
        text(
            """
            SELECT id, key, is_active, publish_acl, consume_acl,
                   default_workflow_ref, default_visibility, default_priority
              FROM task_pools
             WHERE id = :pid
            """
        ),
        {"pid": int(pool_id)},
    ).first()
    if row is None:
        raise PoolNotFound(f"task_pool id={pool_id} not found")
    return {
        "id": int(row[0]),
        "key": row[1],
        "is_active": bool(row[2]),
        "publish_acl": row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}"),
        "consume_acl": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
        "default_workflow_ref": row[5] if isinstance(row[5], dict) else json.loads(row[5] or "{}"),
        "default_visibility": row[6],
        "default_priority": row[7],
    }


def _load_pool_by_key(session: Session, *, pool_key: str) -> Dict[str, Any]:
    row = session.execute(
        text(
            "SELECT id FROM task_pools WHERE key = :k"
        ),
        {"k": pool_key},
    ).first()
    if row is None:
        raise PoolNotFound(f"task_pool key={pool_key} not found")
    return _load_pool(session, pool_id=int(row[0]))


@dataclass
class _EventEffects:
    extra_node_updates: Dict[str, Any]
    outbox_pool_key: Optional[str]
    post_assignments: list[Dict[str, Any]]
    retire_roles: list[str]
    metadata: Dict[str, Any]


def _resolve_publish_pool(session: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
    pool_id = payload.get("pool_id")
    pool_key = payload.get("pool_key")
    if pool_id is not None:
        return _load_pool(session, pool_id=int(pool_id))
    if pool_key:
        return _load_pool_by_key(session, pool_key=str(pool_key))
    raise PoolNotFound("publish requires payload.pool_id or payload.pool_key")


def _handle_publish_event(
    session: Session,
    *,
    task_id: int,
    actor_principal: Principal,
    payload: Dict[str, Any],
    attrs: Dict[str, Any],
    stage: str,
) -> _EventEffects:
    del stage  # not used by publish
    pool = _resolve_publish_pool(session, payload)
    if not pool["is_active"]:
        raise PoolInactive(f"pool {pool['key']} is not active")
    decision: AclDecision = evaluate_acl(actor_principal, pool["publish_acl"])
    if not decision.allow:
        raise PublishAclDenied(
            f"actor (id={actor_principal.id}, kind={actor_principal.kind}) "
            f"failed publish_acl on pool {pool['key']}: {decision.reason}"
        )
    # publish precondition: no active executor.
    row = session.execute(
        text(
            """
            SELECT 1 FROM task_assignments
             WHERE task_node_id = :tid AND is_active AND role = 'executor'
             LIMIT 1
            """
        ),
        {"tid": task_id},
    ).first()
    if row is not None:
        raise AlreadyClaimedError(
            f"task {task_id} already has an active executor; cannot publish"
        )
    return _EventEffects(
        extra_node_updates={
            "pool_id": pool["id"],
            "assignee_kind": "pool",
        },
        outbox_pool_key=pool["key"],
        post_assignments=[],
        retire_roles=[],
        metadata={
            "from_pool_id": attrs.get("pool_id"),
            "to_pool_id": pool["id"],
            "pool_key": pool["key"],
        },
    )


def _handle_claim_event(
    session: Session,
    *,
    task_id: int,
    actor_principal: Principal,
    payload: Dict[str, Any],
    attrs: Dict[str, Any],
    stage: str,
) -> _EventEffects:
    del payload
    pool_id = attrs.get("pool_id")
    if pool_id is None:
        raise PoolNotFound(
            f"task {task_id} has no pool_id; cannot evaluate consume_acl"
        )
    pool = _load_pool(session, pool_id=int(pool_id))
    if not pool["is_active"]:
        raise PoolInactive(f"pool {pool['key']} is not active")
    decision = evaluate_acl(actor_principal, pool["consume_acl"])
    if not decision.allow:
        raise ConsumeAclDenied(
            f"actor (id={actor_principal.id}, kind={actor_principal.kind}) "
            f"failed consume_acl on pool {pool['key']}: {decision.reason}"
        )
    return _EventEffects(
        extra_node_updates={},
        outbox_pool_key=pool["key"],
        post_assignments=[
            {
                "role": "executor",
                "stage": stage,
                "principal_kind": actor_principal.kind,
                "principal_id": actor_principal.id,
            }
        ],
        retire_roles=[],
        metadata={},
    )


def _handle_assign_event(
    session: Session,
    *,
    task_id: int,
    actor_principal: Principal,
    payload: Dict[str, Any],
    attrs: Dict[str, Any],
    stage: str,
) -> _EventEffects:
    del actor_principal
    target_id = payload.get("principal_id")
    target_kind = payload.get("principal_kind", "user")
    target_tag = payload.get("principal_tag")
    if target_kind != "group" and target_id is None:
        raise PreconditionFailed(
            "assign requires payload.principal_id (or principal_kind=group with principal_tag)"
        )
    pool_key: Optional[str] = None
    pool_id = attrs.get("pool_id")
    if pool_id is not None:
        pool_key = _load_pool(session, pool_id=int(pool_id))["key"]
    return _EventEffects(
        extra_node_updates={},
        outbox_pool_key=pool_key,
        post_assignments=[
            {
                "role": "executor",
                "stage": stage,
                "principal_kind": target_kind,
                "principal_id": target_id,
                "principal_tag": target_tag,
            }
        ],
        retire_roles=[],
        metadata={},
    )


def _handle_complete_event(
    session: Session,
    *,
    task_id: int,
    actor_principal: Principal,
    payload: Dict[str, Any],
    attrs: Dict[str, Any],
    stage: str,
) -> _EventEffects:
    del actor_principal, payload, stage
    cs = attrs.get("children_summary")
    if isinstance(cs, dict):
        terminal = int(cs.get("terminal_count") or 0)
        total = int(cs.get("total") or 0)
        if total > 0 and terminal != total:
            raise PreconditionFailed(
                f"task {task_id} has {total - terminal} non-terminal children"
            )
    pool_key: Optional[str] = None
    pool_id = attrs.get("pool_id")
    if pool_id is not None:
        pool_key = _load_pool(session, pool_id=int(pool_id))["key"]
    return _EventEffects(
        extra_node_updates={},
        outbox_pool_key=pool_key,
        post_assignments=[],
        retire_roles=["executor", "approver", "owner"],
        metadata={},
    )


_EVENT_HANDLERS = {
    "publish": _handle_publish_event,
    "claim": _handle_claim_event,
    "assign": _handle_assign_event,
    "complete": _handle_complete_event,
}


def _lock_task_node(session: Session, *, task_id: int) -> Dict[str, Any]:
    row = session.execute(
        text(
            """
            SELECT id, attributes
              FROM nodes
             WHERE id = :tid AND type_code = 'task'
             FOR UPDATE
            """
        ),
        {"tid": task_id},
    ).first()
    if row is None:
        raise WorkflowDefinitionNotFound(f"task node {task_id} not found")
    attrs = row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}")
    return {"id": int(row[0]), "attributes": attrs}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_task(
    *,
    title: str,
    actor: Principal,
    workflow_key: str = "default_v1",
    pool_id: Optional[int] = None,
    priority: str = "normal",
    visibility: str = "private",
    assignee_kind: str = "user",
    scope_selector: Optional[Dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
    due_at: Optional[datetime] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> TransitionResult:
    """Create a new task node and emit the synthetic ``create`` transition.

    Atomically:

    1. Pin ``workflow_ref`` to ``MAX(version) WHERE is_active`` (F03 §2.5).
    2. Insert the ``task`` ``nodes`` row with ``current_state=draft`` and
       ``state_version=0`` (the create transition will bump it to 1).
    3. Insert the ``owner`` assignment row.
    4. Append ``task_state_transitions`` (event=``create``).
    5. Insert ``task_outbox`` (event_kind=``task.created``).
    """

    correlation_id = _ensure_correlation(correlation_id)
    trace_id = _ensure_trace(trace_id)

    with _transaction(db_session) as session:
        replay = _check_create_idempotency(
            session,
            actor=actor,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            return replay

        version = _resolve_active_workflow_version(session, key=workflow_key)
        spec = _load_workflow_spec(session, key=workflow_key, version=version)
        initial_state = spec.get("initial_state", "draft")

        attributes: Dict[str, Any] = {
            "current_state": initial_state,
            "state_version": 1,
            "workflow_ref": {
                "_schema_version": 1,
                "key": workflow_key,
                "version": version,
            },
            "title": title,
            "priority": priority,
            "visibility": visibility,
            "assignee_kind": assignee_kind,
            "tags": list(tags or []),
        }
        if due_at is not None:
            attributes["due_at"] = due_at.astimezone(tz=timezone.utc).isoformat()
        if scope_selector is not None:
            attributes["scope_selector"] = scope_selector
        if pool_id is not None:
            pool = _load_pool(session, pool_id=int(pool_id))
            if not pool["is_active"]:
                raise PoolInactive(f"pool {pool['key']} is not active")
            attributes["pool_id"] = int(pool["id"])

        type_id_row = session.execute(
            text("SELECT id FROM node_types WHERE type_code = 'task'")
        ).first()
        if type_id_row is None:
            raise WorkflowDefinitionNotFound(
                "node_types.type_code='task' missing; run schema migration first"
            )
        type_id = int(type_id_row[0])

        node_row = session.execute(
            text(
                """
                INSERT INTO nodes (type_id, type_code, name, description,
                                   attributes, tags, is_active, is_public)
                VALUES (:type_id, 'task', :name, :description,
                        CAST(:attrs AS jsonb), CAST(:tag_array AS jsonb),
                        TRUE, FALSE)
                RETURNING id
                """
            ),
            {
                "type_id": type_id,
                "name": title[:255],
                "description": None,
                "attrs": json.dumps(attributes, ensure_ascii=False),
                "tag_array": json.dumps(list(tags or []), ensure_ascii=False),
            },
        ).first()
        task_id = int(node_row[0])

        # Owner assignment so subsequent transitions pass `_check_required_role`.
        if actor.kind != "system":
            _add_assignment(
                session,
                task_id=task_id,
                role="owner",
                stage=_STAGE_BY_TO_STATE[initial_state],
                actor=actor,
            )

        event_seq = 1  # first transition for a brand-new task
        _insert_state_transition(
            session,
            task_id=task_id,
            event_seq=event_seq,
            idempotency_key=idempotency_key,
            from_state="__init__",
            to_state=initial_state,
            event="create",
            actor=actor,
            stage=_STAGE_BY_TO_STATE[initial_state],
            reason=None,
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata={
                "workflow_ref": attributes["workflow_ref"],
                "pool_id": attributes.get("pool_id"),
            },
        )

        pool_key: Optional[str] = None
        if pool_id is not None:
            pool_key = _load_pool(session, pool_id=int(pool_id))["key"]
        _insert_outbox(
            session,
            task_id=task_id,
            pool_key=pool_key,
            event_kind=_OUTBOX_EVENT_KIND["create"],
            payload={
                "task_id": task_id,
                "from_state": "__init__",
                "to_state": initial_state,
                "event": "create",
                "workflow_ref": attributes["workflow_ref"],
                "actor": {"id": actor.id, "kind": actor.kind},
            },
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

        return TransitionResult(
            task_id=task_id,
            from_state="__init__",
            to_state=initial_state,
            event="create",
            event_seq=event_seq,
            state_version=1,
            idempotent_replay=False,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )


def transition(
    task_id: int,
    event: str,
    actor_principal: Principal,
    expected_version: int,
    *,
    idempotency_key: Optional[str] = None,
    correlation_id: Optional[str] = None,
    trace_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    db_session: Optional[Session] = None,
) -> TransitionResult:
    """Atomically apply ``event`` to ``task_id``.

    Phase B handles ``publish / claim / assign / complete``. ``create`` is
    routed through :func:`create_task` since it must allocate a new node row.
    """
    if event == "create":
        raise WorkflowEventNotAllowed("use create_task() for the synthetic create event")
    if event not in _PHASE_B_EVENTS:
        # Detail string is bubbled up to user via i18n {detail}; keep it terse
        # and free of internal roadmap / SPEC section references.
        raise WorkflowEventNotAllowed(
            f"event {event!r} is not currently enabled"
        )

    correlation_id = _ensure_correlation(correlation_id)
    trace_id = _ensure_trace(trace_id)
    payload = payload or {}

    try:
        with _transaction(db_session) as session:
            # I6 — idempotency short-circuit (must precede ANY side-effect).
            replay = _check_idempotency(
                session, task_id=task_id, idempotency_key=idempotency_key
            )
            if replay is not None:
                logger.info(
                    "task.transition.replay",
                    extra={
                        "task_id": task_id,
                        "event": event,
                        "actor_id": actor_principal.id,
                        "actor_kind": actor_principal.kind,
                        "event_seq": replay.event_seq,
                        "state_version": replay.state_version,
                        "correlation_id": replay.correlation_id,
                        "trace_id": replay.trace_id,
                    },
                )
                return replay

        # Step 2 — lock task row.
        node = _lock_task_node(session, task_id=task_id)
        attrs = node["attributes"]
        current_state = attrs.get("current_state")
        state_version = int(attrs.get("state_version") or 0)
        workflow_ref = attrs.get("workflow_ref") or {}
        workflow_key = workflow_ref.get("key", "default_v1")
        workflow_version = int(workflow_ref.get("version") or 0)

        # Step 3a — workflow + event lookup.
        spec = _load_workflow_spec(
            session, key=workflow_key, version=workflow_version
        )
        events = spec.get("events") or {}
        event_def = events.get(event)
        if event_def is None or current_state not in (event_def.get("from") or []):
            raise WorkflowEventNotAllowed(
                f"event={event!r} not allowed from state={current_state!r} "
                f"in workflow {workflow_key}:{workflow_version}"
            )

        # Step 3b — optimistic version check.
        if expected_version != state_version:
            raise OptimisticLockError(
                f"task {task_id}: expected_version={expected_version} but "
                f"current state_version={state_version}"
            )

        # Step 3c — required_role.
        required_role = event_def.get("required_role") or "owner"
        if event != "claim":
            _check_required_role(
                session,
                task_id=task_id,
                actor=actor_principal,
                required_role=required_role,
            )

        new_state = event_def["to"]
        stage = _STAGE_BY_TO_STATE[new_state]
        handler = _EVENT_HANDLERS.get(event)
        if handler is None:
            raise WorkflowEventNotAllowed(f"event {event!r} is not currently enabled")
        effects = handler(
            session,
            task_id=task_id,
            actor_principal=actor_principal,
            payload=payload,
            attrs=attrs,
            stage=stage,
        )
        extra_node_updates = effects.extra_node_updates
        outbox_pool_key = effects.outbox_pool_key
        post_assignments = effects.post_assignments
        retire_roles = effects.retire_roles
        metadata = effects.metadata

        # Step 5 — update SSOT.
        new_state_version = _update_node_state(
            session,
            task_id=task_id,
            new_state=new_state,
            expected_version=expected_version,
            extra_updates=extra_node_updates,
        )

        # Step 6 — assignments.
        _retire_assignments(session, task_id=task_id, roles=retire_roles)
        for ass in post_assignments:
            _add_assignment(
                session,
                task_id=task_id,
                role=ass["role"],
                stage=ass["stage"],
                actor=actor_principal,
                target_principal_id=ass.get("principal_id"),
                target_principal_kind=ass.get("principal_kind"),
                target_principal_tag=ass.get("principal_tag"),
            )

        # Step 4 — event_seq.
        event_seq = _next_event_seq(session, task_id=task_id)

        # Step 7 — append transition.
        _insert_state_transition(
            session,
            task_id=task_id,
            event_seq=event_seq,
            idempotency_key=idempotency_key,
            from_state=current_state,
            to_state=new_state,
            event=event,
            actor=actor_principal,
            stage=stage,
            reason=payload.get("reason"),
            correlation_id=correlation_id,
            trace_id=trace_id,
            metadata=metadata,
        )

        # Step 8 — outbox.
        _insert_outbox(
            session,
            task_id=task_id,
            pool_key=outbox_pool_key,
            event_kind=_OUTBOX_EVENT_KIND[event],
            payload={
                "task_id": task_id,
                "from_state": current_state,
                "to_state": new_state,
                "event": event,
                "event_seq": event_seq,
                "actor": {"id": actor_principal.id, "kind": actor_principal.kind},
                **({"pool_key": outbox_pool_key} if outbox_pool_key else {}),
            },
            correlation_id=correlation_id,
            trace_id=trace_id,
        )

        result = TransitionResult(
            task_id=task_id,
            from_state=current_state,
            to_state=new_state,
            event=event,
            event_seq=event_seq,
            state_version=new_state_version,
            idempotent_replay=False,
            correlation_id=correlation_id,
            trace_id=trace_id,
        )
        logger.info(
            "task.transition.ok",
            extra={
                "task_id": task_id,
                "event": event,
                "from_state": current_state,
                "to_state": new_state,
                "event_seq": event_seq,
                "state_version": new_state_version,
                "actor_id": actor_principal.id,
                "actor_kind": actor_principal.kind,
                "correlation_id": correlation_id,
                "trace_id": trace_id,
            },
        )
        return result
    except Exception:
        logger.warning(
            "task.transition.failed",
            extra={
                "task_id": task_id,
                "event": event,
                "actor_id": actor_principal.id,
                "actor_kind": actor_principal.kind,
                "expected_version": expected_version,
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_id,
                "trace_id": trace_id,
            },
            exc_info=True,
        )
        raise


__all__ = [
    "TransitionResult",
    "create_task",
    "transition",
]
