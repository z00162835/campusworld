#!/usr/bin/env python3
"""
Emit a JSON snapshot of the live CommandRegistry after initialize_commands().

Output: docs/command/SPEC/_generated/registry_snapshot.json (under repo root).

Requires a working app import path; run from repo `backend` with Conda `campusworld` per project docs.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure `backend` is on sys.path when run as `python scripts/...` from `backend/`.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.commands.base import BaseCommand, CommandType  # noqa: E402
from app.commands.init_commands import initialize_commands  # noqa: E402
from app.commands.registry import command_registry  # noqa: E402


def _git_head(repo: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def _repo_root() -> Path:
    return _BACKEND_ROOT.parent


def _effective_aliases(cmd: BaseCommand, reg: Any) -> List[str]:
    """Aliases that actually resolve to this command in the global alias map (wins on conflict)."""
    n = cmd.name
    return sorted(a for a, t in reg.aliases.items() if t == n)


def _command_row(cmd: BaseCommand, reg: Any, root: Path) -> Dict[str, Any]:
    cls = cmd.__class__
    try:
        abspath = Path(inspect.getfile(cls)).resolve()
        try:
            file_path = str(abspath.relative_to(root))
        except ValueError:
            file_path = str(abspath)
    except (TypeError, OSError, ValueError):
        file_path = ""
    return {
        "name": cmd.name,
        "command_type": cmd.command_type.name if isinstance(cmd.command_type, CommandType) else str(cmd.command_type),
        "class_declared_aliases": list(cmd.aliases or []),
        "registry_aliases": _effective_aliases(cmd, reg),
        "class": f"{cls.__module__}.{cls.__qualname__}",
        "file": file_path,
    }


def main() -> int:
    out_arg = os.environ.get("REGISTRY_SNAPSHOT_OUT")
    default_out = _repo_root() / "docs" / "command" / "SPEC" / "_generated" / "registry_snapshot.json"
    out_path = Path(out_arg) if out_arg else default_out
    root = _repo_root()

    ok = initialize_commands(force_reinit=True)
    rows: List[Dict[str, Any]] = []
    for c in sorted(command_registry.get_all_commands(), key=lambda x: x.name):
        rows.append(_command_row(c, command_registry, root))
    payload: Dict[str, Any] = {
        "git_commit": _git_head(root),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "initialize_commands_ok": bool(ok),
        "command_count": len(rows),
        "commands": rows,
    }
    if not ok:
        payload["warning"] = (
            "initialize_commands returned False; builder commands (create/create_info) may be missing if DB/discovery failed."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(rows)} commands, init_ok={ok})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
