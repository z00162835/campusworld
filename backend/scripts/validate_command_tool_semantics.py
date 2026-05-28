#!/usr/bin/env python3
"""Validate committed registry_snapshot tool_semantics against live registry."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.commands.init_commands import initialize_commands  # noqa: E402
from scripts.export_command_registry_snapshot import _command_row  # noqa: E402
from app.commands.registry import command_registry  # noqa: E402


def _semantics_by_name(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        sem = row.get('tool_semantics')
        if isinstance(sem, dict):
            out[name] = sem
    return out


def main() -> int:
    repo_root = _BACKEND_ROOT.parent
    snap_path = repo_root / 'docs' / 'command' / 'SPEC' / '_generated' / 'registry_snapshot.json'
    if not snap_path.is_file():
        print(f'Missing snapshot: {snap_path}', file=sys.stderr)
        return 1
    committed = json.loads(snap_path.read_text(encoding='utf-8'))
    committed_map = _semantics_by_name(list(committed.get('commands') or []))

    ok = initialize_commands(force_reinit=True)
    if not ok:
        print('initialize_commands returned False', file=sys.stderr)
    live_rows = [_command_row(c, command_registry, repo_root) for c in sorted(command_registry.get_all_commands(), key=lambda x: x.name)]
    live_map = _semantics_by_name(live_rows)

    errors: List[str] = []
    if set(committed_map) != set(live_map):
        missing = sorted(set(live_map) - set(committed_map))
        extra = sorted(set(committed_map) - set(live_map))
        if missing:
            errors.append(f'commands missing tool_semantics in snapshot: {missing}')
        if extra:
            errors.append(f'commands only in snapshot: {extra}')

    for name in sorted(set(committed_map) & set(live_map)):
        if committed_map[name] != live_map[name]:
            errors.append(f'tool_semantics drift for {name!r}')

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        print('Run: cd backend && python scripts/export_command_registry_snapshot.py', file=sys.stderr)
        return 1
    print(f'tool_semantics OK ({len(live_map)} commands)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
