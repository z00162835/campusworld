#!/usr/bin/env python3
"""
Reconcile `docs/command/SPEC/_generated/registry_snapshot.json` with `CMD_*.md` in features/.

Exit 0 if every registered command name has a corresponding `CMD_<name>.md` (case-sensitive).

`CMD_*.md` may exist for **planned** commands not yet in the registry; see
``_PLANNED_SPEC_WITHOUT_REGISTRY`` (remove a name from that set when the
command is registered and the snapshot is regenerated).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_ROOT.parent

# Target-contract SPEC files before `export_command_registry_snapshot` includes the name.
_PLANNED_SPEC_WITHOUT_REGISTRY: frozenset[str] = frozenset()


def main() -> int:
    snap = _REPO_ROOT / "docs" / "command" / "SPEC" / "_generated" / "registry_snapshot.json"
    if not snap.is_file():
        print(f"Missing snapshot: {snap} — run export_command_registry_snapshot.py first", file=sys.stderr)
        return 2
    data = json.loads(snap.read_text(encoding="utf-8"))
    names = {c["name"] for c in data.get("commands", [])}
    feat = _REPO_ROOT / "docs" / "command" / "SPEC" / "features"
    have = {p.stem[4:] for p in feat.glob("CMD_*.md")}
    missing = sorted(names - have)
    extra = sorted((have - names) - _PLANNED_SPEC_WITHOUT_REGISTRY)
    if missing:
        print("Missing CMD_*.md for registered commands:", ", ".join(missing), file=sys.stderr)
    if extra:
        print("Orphan CMD_*.md (not in registry snapshot):", ", ".join(extra), file=sys.stderr)
    if missing or extra:
        return 1
    print(f"OK: {len(have)} CMD_*.md files match registry ({snap.name} command_count={len(names)}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
