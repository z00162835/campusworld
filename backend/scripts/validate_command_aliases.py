#!/usr/bin/env python3
"""Validate CommandRegistry alias namespace against snapshot and optional DB ability nodes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.commands.init_commands import initialize_commands  # noqa: E402
from app.commands.registry import (  # noqa: E402
    RESERVED_FUTURE_COMMAND_TOKENS,
    collect_all_command_tokens,
    command_registry,
)
from scripts.export_command_registry_snapshot import _effective_aliases  # noqa: E402

CANONICAL_ALIAS_RESOLUTION: Dict[str, str] = {
    'l': 'look',
    'lookat': 'look',
    'examine': 'describe',
    'ex': 'describe',
    'h': 'help',
    '?': 'help',
    'exit': 'quit',
    'q': 'quit',
    'walk': 'go',
    '@find': 'find',
    'locate': 'find',
    'stat': 'stats',
    'system': 'stats',
    'ver': 'version',
    'date': 'time',
    'ooc': 'leave',
    'tasks': 'task',
    'manual': 'primer',
    'worlds': 'world',
    'notices': 'notice',
}

EVENNIA_DEFAULT_ALIASES: Dict[str, List[str]] = {
    'look': ['l', 'ls'],
    'find': ['@find', '@search', '@locate'],
    'describe': ['examine', 'ex'],
    'quit': [],
    'help': [],
    'inventory': ['inv', 'i'],
    'go': [],
}


def _aliases_by_name_from_snapshot(commands: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for row in commands:
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        aliases = row.get('registry_aliases') or row.get('class_declared_aliases') or []
        out[name] = sorted(str(a) for a in aliases)
    return out


def _cmdset_tokens() -> Set[str]:
    from app.commands.cmdset import CharacterCmdSet

    cs = CharacterCmdSet()
    tokens: Set[str] = set(cs.commands.keys())
    tokens.update(cs.aliases.keys())
    return tokens


def _check_namespace_unique() -> List[str]:
    errors: List[str] = []
    owner_by_token: Dict[str, str] = {}
    for cmd in command_registry.get_all_commands():
        for token in [cmd.name, *list(cmd.aliases or [])]:
            prev = owner_by_token.get(token)
            if prev and prev != cmd.name:
                errors.append(f"token {token!r} maps to both {prev!r} and {cmd.name!r}")
            owner_by_token[token] = cmd.name
    return errors


def _check_canonical_resolution() -> List[str]:
    errors: List[str] = []
    for alias, expected in CANONICAL_ALIAS_RESOLUTION.items():
        cmd = command_registry.get_command(alias)
        if cmd is None:
            errors.append(f"canonical alias {alias!r} does not resolve")
            continue
        if cmd.name != expected:
            errors.append(f"canonical alias {alias!r} -> {cmd.name!r}, expected {expected!r}")
    return errors


def _check_snapshot_drift(snap_path: Path) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    if not snap_path.is_file():
        errors.append(f'Missing snapshot: {snap_path}')
        return errors, warnings
    committed = json.loads(snap_path.read_text(encoding='utf-8'))
    committed_map = _aliases_by_name_from_snapshot(list(committed.get('commands') or []))
    live_map: Dict[str, List[str]] = {}
    for cmd in command_registry.get_all_commands():
        live_map[cmd.name] = sorted(_effective_aliases(cmd, command_registry))
    if set(committed_map) != set(live_map):
        missing = sorted(set(live_map) - set(committed_map))
        extra = sorted(set(committed_map) - set(live_map))
        if missing:
            errors.append(f'commands missing in snapshot: {missing}')
        if extra:
            errors.append(f'commands only in snapshot: {extra}')
    for name in sorted(set(committed_map) & set(live_map)):
        if committed_map[name] != live_map[name]:
            errors.append(f'registry_aliases drift for {name!r}: snapshot={committed_map[name]!r} live={live_map[name]!r}')
        declared = []
        cmd = command_registry.get_command(name)
        if cmd is not None:
            declared = sorted(str(a) for a in (cmd.aliases or []))
        dropped = sorted(set(declared) - set(live_map[name]))
        if dropped:
            warnings.append(f"{name!r} class_declared_aliases not in registry_aliases: {dropped}")
    return errors, warnings


def _check_cmdset_vs_registry() -> List[str]:
    errors: List[str] = []
    reg_tokens = collect_all_command_tokens(command_registry.commands, command_registry.aliases)
    overlap = _cmdset_tokens() & reg_tokens
    if overlap:
        errors.append(f'CharacterCmdSet tokens overlap registry: {sorted(overlap)}')
    return errors


def _check_reserved_tokens() -> List[str]:
    warnings: List[str] = []
    reg_tokens = collect_all_command_tokens(command_registry.commands, command_registry.aliases)
    cmdset_tokens = _cmdset_tokens()
    for token in sorted(RESERVED_FUTURE_COMMAND_TOKENS):
        if token in reg_tokens:
            warnings.append(f"reserved future token {token!r} occupied by CommandRegistry")
        if token in cmdset_tokens:
            warnings.append(f"reserved future token {token!r} occupied by CharacterCmdSet")
    return warnings


def _check_db_abilities() -> List[str]:
    errors: List[str] = []
    try:
        from app.core.database import db_session_context
        from app.models.graph import Node
        from sqlalchemy import and_
    except Exception as e:
        return [f'--check-db import failed: {e}']
    live_by_name: Dict[str, List[str]] = {}
    for cmd in command_registry.get_all_commands():
        live_by_name[cmd.name] = sorted(_effective_aliases(cmd, command_registry))
    try:
        with db_session_context() as session:
            rows = session.query(Node).filter(
                and_(Node.type_code == 'system_command_ability', Node.is_active == True)
            ).all()
    except Exception as e:
        return [f'--check-db query failed: {e}']
    for node in rows:
        attrs = node.attributes if isinstance(node.attributes, dict) else {}
        cmd_name = str(attrs.get('command_name') or node.name or '').strip()
        if not cmd_name or cmd_name not in live_by_name:
            continue
        raw = attrs.get('aliases')
        db_aliases: List[str] = []
        if isinstance(raw, list):
            db_aliases = sorted(str(x).strip() for x in raw if str(x).strip())
        elif isinstance(raw, str) and raw.strip():
            db_aliases = [raw.strip()]
        if db_aliases != live_by_name[cmd_name]:
            errors.append(
                f"ability node {cmd_name!r} aliases drift: db={db_aliases!r} registry={live_by_name[cmd_name]!r}"
            )
    return errors


def _report_evennia() -> None:
    print('Evennia comparison (informational):')
    for primary, evennia_aliases in sorted(EVENNIA_DEFAULT_ALIASES.items()):
        cmd = command_registry.get_command(primary)
        if cmd is None:
            print(f'  {primary}: not registered (Evennia aliases: {evennia_aliases})')
            continue
        live = sorted(_effective_aliases(cmd, command_registry))
        missing = sorted(set(evennia_aliases) - set(live))
        extra = sorted(set(live) - set(evennia_aliases))
        note = []
        if missing:
            note.append(f'missing vs Evennia: {missing}')
        if extra:
            note.append(f'CampusWorld-only: {extra}')
        print(f'  {primary}: live={live}' + (f" ({'; '.join(note)})" if note else ''))


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate command alias namespace')
    parser.add_argument('--skip-snapshot', action='store_true', help='Skip registry_snapshot.json drift check')
    parser.add_argument('--check-db', action='store_true', help='Compare system_command_ability node aliases to registry')
    parser.add_argument('--report-evennia', action='store_true', help='Print Evennia default alias diff (informational)')
    args = parser.parse_args()

    ok = initialize_commands(force_reinit=True)
    if not ok:
        print('initialize_commands returned False', file=sys.stderr)

    errors: List[str] = []
    warnings: List[str] = []

    errors.extend(_check_namespace_unique())
    errors.extend(_check_canonical_resolution())
    errors.extend(_check_cmdset_vs_registry())
    warnings.extend(_check_reserved_tokens())

    if not args.skip_snapshot:
        repo_root = _BACKEND_ROOT.parent
        snap_path = repo_root / 'docs' / 'command' / 'SPEC' / '_generated' / 'registry_snapshot.json'
        snap_errors, snap_warnings = _check_snapshot_drift(snap_path)
        errors.extend(snap_errors)
        warnings.extend(snap_warnings)

    if args.check_db:
        errors.extend(_check_db_abilities())

    for w in warnings:
        print(f'WARNING: {w}', file=sys.stderr)
    for err in errors:
        print(f'ERROR: {err}', file=sys.stderr)

    if args.report_evennia:
        _report_evennia()

    if errors:
        print('Alias validation failed', file=sys.stderr)
        return 1
    print(f'Alias validation OK ({len(command_registry.get_all_commands())} commands, {len(command_registry.aliases)} aliases)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
