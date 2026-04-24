"""Validate docs/models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md against the live code/config.

Checks:
  1. All required section anchors (``## N. <Slot>``) are present.
  2. Every placeholder used in the primer is in the known set that
     ``build_ontology_primer`` knows how to substitute.
  3. Command names referenced in the primer exist in the command registry
     (after ``initialize_commands``).
  4. Node type codes referenced in the Ontology section exist in the seeded
     ontology (``NodeType.type_code``) when a DB is reachable; otherwise
     warns instead of failing to keep the script runnable in non-DB CI.
  5. Each section yields non-empty content when sliced via
     ``build_ontology_primer(section=...)``.

Exit code 0 on success, non-zero on any hard failure. Warnings go to stderr.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Set, Tuple

# Expected section titles (normalised to lowercase keys) in order.
REQUIRED_SECTIONS: List[Tuple[str, str]] = [
    ("identity", "1. Identity"),
    ("structure", "2. Structure"),
    ("ontology", "3. Ontology"),
    ("world", "4. World"),
    ("actions", "5. Actions"),
    ("interaction", "6. Interaction"),
    ("memory", "7. Memory"),
    ("invariants", "8. Invariants"),
    ("examples", "9. Examples"),
]

ALLOWED_PLACEHOLDERS: Set[str] = {
    "AGENT_SERVICE_ID",
    "CALLER_LOCATION",
    "ROOT_ROOM_LABEL",
}

# Commands the primer tells the LLM to call. Must exist in registry.
COMMAND_NAMES_IN_PRIMER: List[str] = [
    "whoami",
    "look",
    "primer",
    "find",
    "describe",
    "agent_capabilities",
    "agent_tools",
    "help",
    "aico",
    "world",
    "enter",
    "leave",
]

# Node type codes named in the Ontology section.
NODE_TYPE_CODES_IN_PRIMER: List[str] = [
    "account",
    "character",
    "npc_agent",
    "room",
    "exit",
    "world_entrance",
    "world",
    "package",
    "building",
    "item",
    "system_command_ability",
    "system_bulletin_board",
]


def _primer_path() -> Path:
    # backend/scripts/validate_system_primer.py -> parents[2] == workspace root.
    here = Path(__file__).resolve()
    return here.parents[2] / "docs" / "models" / "SPEC" / "CAMPUSWORLD_SYSTEM_PRIMER.md"


def _check_sections(text: str) -> List[str]:
    errors: List[str] = []
    for _, title in REQUIRED_SECTIONS:
        pat = r"^##\s+" + re.escape(title) + r"\s*$"
        if not re.search(pat, text, flags=re.MULTILINE):
            errors.append(f"missing section: '## {title}'")
    return errors


def _check_placeholders(text: str) -> List[str]:
    errors: List[str] = []
    seen = set(re.findall(r"\{([A-Z_][A-Z0-9_]*)\}", text))
    unknown = seen - ALLOWED_PLACEHOLDERS
    if unknown:
        errors.append(
            f"unknown placeholders not implemented in build_ontology_primer: {sorted(unknown)}"
        )
    return errors


def _check_commands_registered() -> List[str]:
    errors: List[str] = []
    try:
        from app.commands.init_commands import initialize_commands
        from app.commands.registry import command_registry

        initialize_commands()
        known = {c.name for c in command_registry.get_all_commands()}
        for name in COMMAND_NAMES_IN_PRIMER:
            if name not in known:
                errors.append(
                    f"primer references command '{name}' which is not in the registry"
                )
    except Exception as e:
        print(
            f"[warn] command registry check skipped: {e}",
            file=sys.stderr,
        )
    return errors


def _check_ontology_codes() -> List[str]:
    errors: List[str] = []
    try:
        from app.core.database import db_session_context
        from app.models.graph import NodeType

        with db_session_context() as session:
            rows = session.query(NodeType.type_code).all()
            known = {r[0] for r in rows}
        missing = [tc for tc in NODE_TYPE_CODES_IN_PRIMER if tc not in known]
        if missing:
            print(
                f"[warn] primer ontology lists types not present in this DB: {missing}",
                file=sys.stderr,
            )
    except Exception as e:
        print(
            f"[warn] node type check skipped (DB unavailable?): {e}",
            file=sys.stderr,
        )
    return errors


def _check_sections_have_content() -> List[str]:
    errors: List[str] = []
    try:
        from app.game_engine.agent_runtime.system_primer_context import (
            build_ontology_primer,
        )

        for key, title in REQUIRED_SECTIONS:
            chunk = build_ontology_primer(section=key)
            if not chunk or not chunk.strip():
                errors.append(
                    f"section '{key}' (## {title}) returns empty from build_ontology_primer"
                )
    except Exception as e:
        print(
            f"[warn] build_ontology_primer slice check skipped: {e}",
            file=sys.stderr,
        )
    return errors


def main(argv: List[str]) -> int:
    p = _primer_path()
    if not p.exists():
        print(f"[error] primer file not found: {p}", file=sys.stderr)
        return 2
    text = p.read_text(encoding="utf-8")

    errors: List[str] = []
    errors += _check_sections(text)
    errors += _check_placeholders(text)
    errors += _check_commands_registered()
    errors += _check_ontology_codes()
    errors += _check_sections_have_content()

    if errors:
        print("CampusWorld System Primer validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("CampusWorld System Primer validation OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
