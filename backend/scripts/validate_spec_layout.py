#!/usr/bin/env python3
"""
Validate docs SPEC layout and naming rules.

Checks:
1) docs/<module>/SPEC root markdown allowlist.
2) features markdown filename pattern allowlist.
3) SPEC.md references features/ when feature docs exist.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DOCS_ROOT = REPO_ROOT / "docs"

ROOT_ALLOWED = {"SPEC.md", "TODO.md", "ACCEPTANCE.md"}
FEATURE_NAME_RE = re.compile(r"^(CMD_[A-Za-z0-9_]+|CMD_TOPIC_[A-Za-z0-9_]+|F\d{2}_[A-Za-z0-9_]+|TOPIC_[A-Za-z0-9_]+|INDEX)\.md$")

# Transitional exceptions to be removed after migration.
ROOT_MD_ALLOWLIST = {
    "models/SPEC/CAMPUSWORLD_SYSTEM_PRIMER.md",
    "models/SPEC/AGENT_PDCA_PHASE_MERGE_TRADEOFFS.md",
    "models/SPEC/AGENT_TOOL_SEMANTIC_REVIEW_GATE.md",
    "models/SPEC/AICO_TOOL_DESCRIPTION_AUDIT.md",
    "frontend/SPEC/SPACES.md",
    "task/SPEC/PLAN_PHASE_B.md",  # compatibility stub, target removal: 2026-07
}

# Transitional exceptions to be renamed to CMD_TOPIC_* in command module.
FEATURE_MD_ALLOWLIST = {
    "command/SPEC/features/FAMILY_direction.md",
    "command/SPEC/features/F01_FIND_COMMAND.md",
    "command/SPEC/features/F02_DESIGN_DECISIONS.md",
    "command/SPEC/features/F02_COMMAND_SYSTEM_I18N_AND_AGENT_FRIENDLY_DESCRIPTIONS.md",
}


def spec_dirs() -> list[Path]:
    out: list[Path] = []
    for p in DOCS_ROOT.glob("**/SPEC"):
        if p.is_dir():
            out.append(p)
    return sorted(out)


def rel_to_docs(path: Path) -> str:
    return str(path.relative_to(DOCS_ROOT)).replace("\\", "/")


def validate_root_md(spec_dir: Path, errors: list[str]) -> None:
    for md in sorted(spec_dir.glob("*.md")):
        name = md.name
        if name in ROOT_ALLOWED:
            continue
        rel = rel_to_docs(md)
        if rel in ROOT_MD_ALLOWLIST:
            continue
        errors.append(f"Root markdown not allowed outside allowlist: docs/{rel}")


def validate_feature_names(spec_dir: Path, errors: list[str]) -> None:
    features_dir = spec_dir / "features"
    if not features_dir.is_dir():
        return
    for md in sorted(features_dir.glob("*.md")):
        rel = rel_to_docs(md)
        if rel in FEATURE_MD_ALLOWLIST:
            continue
        if not FEATURE_NAME_RE.match(md.name):
            errors.append(f"Feature filename violates naming spec: docs/{rel}")


def validate_spec_references(spec_dir: Path, errors: list[str]) -> None:
    features_dir = spec_dir / "features"
    if not features_dir.is_dir():
        return
    feature_docs = [p for p in features_dir.glob("*.md") if p.name != "INDEX.md"]
    if not feature_docs:
        return
    spec_md = spec_dir / "SPEC.md"
    if not spec_md.is_file():
        errors.append(f"Missing SPEC.md in docs/{rel_to_docs(spec_dir)}")
        return
    text = spec_md.read_text(encoding="utf-8")
    if "features/" not in text:
        errors.append(f"SPEC.md missing features/ references: docs/{rel_to_docs(spec_md)}")


def main() -> int:
    if not DOCS_ROOT.is_dir():
        print(f"docs root not found: {DOCS_ROOT}", file=sys.stderr)
        return 2

    errors: list[str] = []
    dirs = spec_dirs()
    for d in dirs:
        validate_root_md(d, errors)
        validate_feature_names(d, errors)
        validate_spec_references(d, errors)

    if errors:
        print("SPEC layout validation failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1

    print(f"OK: validated {len(dirs)} SPEC directories.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
