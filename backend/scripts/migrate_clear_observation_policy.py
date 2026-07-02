#!/usr/bin/env python3
"""Clear stale auto-seeded ``agent_observation_policy`` on command ability nodes.

Background: ``ability_sync._sync_tool_semantics`` previously auto-seeded
``system_command_ability.attributes.agent_observation_policy`` from the
command's class-level ``interaction_profile`` (e.g. ``task`` class profile is
``mutate`` -> ``{'message_mode': 'summary'}``). For commands with read
subcommands (``task list`` / ``task show``), this stale override defeated the
registry's per-subcommand resolution at runtime
(``tool_observation_policy.resolve_tool_observation_policy`` lets the DB
override win), collapsing ``task list`` observations to a useless header-only
summary. The sync logic has been fixed to only write the override when
``observation_message_mode`` is explicitly declared. This script clears the
stale auto-seeded values once, with a pre-clear dump for audit/rollback.

Usage:
    python scripts/migrate_clear_observation_policy.py             # dry-run
    python scripts/migrate_clear_observation_policy.py --execute   # apply
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import and_

from app.core.database import db_session_context
from app.core.log import get_logger, LoggerNames
from app.models.graph import Node

logger = get_logger(LoggerNames.COMMAND)


def _collect_nodes_with_policy(session) -> list:
    rows = (
        session.query(Node)
        .filter(
            and_(
                Node.type_code == 'system_command_ability',
                Node.is_active == True,  # noqa: E712
            )
        )
        .all()
    )
    out = []
    for node in rows:
        attrs = node.attributes if isinstance(node.attributes, dict) else {}
        policy = attrs.get('agent_observation_policy')
        if isinstance(policy, dict):
            out.append({
                'node_id': int(node.id),
                'command_name': attrs.get('command_name'),
                'agent_observation_policy': dict(policy),
            })
    return out


def _dump_path() -> Path:
    ts = datetime.now().strftime('%Y%m%dT%H%M%S')
    d = project_root / 'logs' / 'migration'
    d.mkdir(parents=True, exist_ok=True)
    return d / f'observation_policy_dump_{ts}.json'


def run(dry_run: bool) -> int:
    with db_session_context() as session:
        targets = _collect_nodes_with_policy(session)
        if not targets:
            print('No system_command_ability nodes carry agent_observation_policy; nothing to do.')
            return 0

        dump = _dump_path()
        dump.write_text(json.dumps(targets, ensure_ascii=False, indent=2))
        print(f'Pre-clear dump ({len(targets)} entries) written to: {dump}')
        print('Commands to be cleared:')
        for t in targets:
            print(f"  node_id={t['node_id']} command={t['command_name']} policy={t['agent_observation_policy']}")

        if dry_run:
            print('\nDry-run: no changes applied. Re-run with --execute to clear.')
            return 0

        cleared = 0
        for t in targets:
            node = session.get(Node, t['node_id'])
            if node is None:
                continue
            attrs = dict(node.attributes or {})
            attrs.pop('agent_observation_policy', None)
            node.attributes = attrs
            session.add(node)
            cleared += 1
        try:
            session.commit()
        except Exception as exc:
            logger.error('clear agent_observation_policy commit failed: %s', exc)
            session.rollback()
            raise
        print(f'\nCleared agent_observation_policy on {cleared} nodes.')
        print('Any ops-set overrides must be re-applied manually (sync no longer auto-seeds).')
        return cleared


def main() -> int:
    parser = argparse.ArgumentParser(description='Clear stale auto-seeded agent_observation_policy.')
    parser.add_argument('--execute', action='store_true', help='Apply the clear (default is dry-run).')
    args = parser.parse_args()
    run(dry_run=not args.execute)
    return 0


if __name__ == '__main__':
    sys.exit(main())
