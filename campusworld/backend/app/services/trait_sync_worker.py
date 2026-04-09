"""
Trait sync worker: eventually sync instance trait fields from type tables.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict

from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.models.graph import Node, NodeType, Relationship, RelationshipType
from app.models.system import TraitSyncJob

logger = get_logger(LoggerNames.SYSTEM)


def _sync_node_type(session, type_code: str) -> int:
    nt = session.query(NodeType).filter(NodeType.type_code == type_code).first()
    if not nt:
        raise RuntimeError(f"node_types missing type_code={type_code}")
    updated = (
        session.query(Node)
        .filter(Node.type_code == type_code)
        .update(
            {
                Node.trait_class: nt.trait_class,
                Node.trait_mask: nt.trait_mask,
            },
            synchronize_session=False,
        )
    )
    return int(updated or 0)


def _sync_relationship_type(session, type_code: str) -> int:
    rt = session.query(RelationshipType).filter(RelationshipType.type_code == type_code).first()
    if not rt:
        raise RuntimeError(f"relationship_types missing type_code={type_code}")
    updated = (
        session.query(Relationship)
        .filter(Relationship.type_code == type_code)
        .update(
            {
                Relationship.trait_class: rt.trait_class,
                Relationship.trait_mask: rt.trait_mask,
            },
            synchronize_session=False,
        )
    )
    return int(updated or 0)


def process_trait_sync_jobs(limit: int = 100) -> Dict[str, int]:
    """
    Pull and process pending trait sync jobs.
    Returns counters: processed/succeeded/failed/updated.
    """
    counters = {"processed": 0, "succeeded": 0, "failed": 0, "updated": 0}
    with db_session_context() as session:
        jobs = (
            session.query(TraitSyncJob)
            .filter(TraitSyncJob.status.in_(["pending", "failed"]))
            .order_by(TraitSyncJob.created_at.asc())
            .limit(int(limit))
            .all()
        )
        for job in jobs:
            counters["processed"] += 1
            job.status = "running"
            job.started_at = datetime.utcnow()
            job.updated_at = datetime.utcnow()
            session.flush()
            try:
                if job.domain == "node":
                    changed = _sync_node_type(session, job.type_code)
                elif job.domain == "relationship":
                    changed = _sync_relationship_type(session, job.type_code)
                else:
                    raise RuntimeError(f"unsupported domain={job.domain}")
                counters["updated"] += changed
                counters["succeeded"] += 1
                job.status = "done"
                job.finished_at = datetime.utcnow()
                job.error_message = None
                pl = job.payload if isinstance(job.payload, dict) else {}
                logger.info(
                    "trait_sync_job_done",
                    event="trait.update.type_trait_synced",
                    domain=job.domain,
                    type_code=job.type_code,
                    updated=changed,
                    before_trait_class=pl.get("before_trait_class"),
                    after_trait_class=pl.get("after_trait_class"),
                    before_trait_mask=pl.get("before_trait_mask"),
                    after_trait_mask=pl.get("after_trait_mask"),
                )
            except Exception as exc:
                counters["failed"] += 1
                job.retries = int(job.retries or 0) + 1
                job.status = "failed" if job.retries < int(job.max_retries or 5) else "dead"
                job.error_message = str(exc)
                job.finished_at = datetime.utcnow()
                pl = job.payload if isinstance(job.payload, dict) else {}
                logger.error(
                    "trait_sync_job_failed",
                    event="trait.update.type_trait_sync_failed",
                    domain=job.domain,
                    type_code=job.type_code,
                    retries=job.retries,
                    error=str(exc),
                    before_trait_class=pl.get("before_trait_class"),
                    after_trait_class=pl.get("after_trait_class"),
                    before_trait_mask=pl.get("before_trait_mask"),
                    after_trait_mask=pl.get("after_trait_mask"),
                )
            finally:
                job.updated_at = datetime.utcnow()
        session.commit()
    return counters
