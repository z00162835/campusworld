"""Minimal tasks for CampusWorld world interaction admin demo (direct assign)."""
from __future__ import annotations

import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.graph import Node
from app.services.task.permissions import Principal
from app.services.task.task_state_machine import create_task, transition
from app.services.task.user_task_queue import list_for_principal

logger = logging.getLogger(__name__)

_DEMO_TITLES: tuple[str, ...] = (
    "Explore CampusWorld",
    "Review singularity room setup",
)


def _admin_principal(session: Session) -> Principal | None:
    admin = (
        session.query(Node)
        .filter(Node.type_code == "account", Node.name == "admin", Node.is_active == True)
        .order_by(Node.id.asc())
        .first()
    )
    if not admin:
        return None
    return Principal(id=int(admin.id), kind="user")


def _existing_demo_titles(session: Session, actor: Principal) -> set[str]:
    rows = list_for_principal(session, actor, limit=50, actionable_only=False)
    return {row.title for row in rows}


def _seed_one_task(session: Session, actor: Principal, title: str) -> None:
    created = create_task(
        title=title,
        actor=actor,
        workflow_key="default_v1",
        priority="normal",
        visibility="private",
        assignee_kind="user",
        db_session=session,
    )
    task_id = created.task_id
    opened = transition(
        task_id,
        "open",
        actor,
        expected_version=created.state_version,
        db_session=session,
    )
    transition(
        task_id,
        "assign",
        actor,
        expected_version=opened.state_version,
        payload={"principal_id": actor.id, "principal_kind": "user"},
        db_session=session,
    )


def ensure_world_ui_demo_tasks(session: Session) -> bool:
    """Create open assigned tasks for admin when missing (idempotent)."""
    wf = session.execute(
        text("SELECT 1 FROM task_workflow_definitions WHERE key = 'default_v1' LIMIT 1")
    ).first()
    if not wf:
        logger.debug("ensure_world_ui_demo_tasks: task workflow not ready")
        return False

    actor = _admin_principal(session)
    if actor is None:
        logger.debug("ensure_world_ui_demo_tasks: admin account missing")
        return False

    existing = _existing_demo_titles(session, actor)
    created = 0
    for title in _DEMO_TITLES:
        if title in existing:
            continue
        try:
            _seed_one_task(session, actor, title)
            created += 1
        except Exception as exc:
            logger.warning("ensure_world_ui_demo_tasks: failed title=%s: %s", title, exc)
            session.rollback()
            return False

    if created:
        session.commit()
        logger.info("ensure_world_ui_demo_tasks: created %s task(s) for admin", created)
    return True


def ensure_world_ui_demo_tasks_engine(engine) -> None:
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine, future=True, expire_on_commit=False)
    with Session() as session:
        ensure_world_ui_demo_tasks(session)
