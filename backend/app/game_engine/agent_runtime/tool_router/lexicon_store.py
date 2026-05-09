from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.game_engine.agent_runtime.tool_router.paths import (
    lexicon_active_pointer_path,
    lexicon_version_dir,
)


def read_active_lexicon_id() -> Optional[str]:
    p = lexicon_active_pointer_path()
    if not p.is_file():
        return None
    try:
        raw = p.read_text(encoding="utf-8").strip()
        return raw or None
    except OSError:
        return None


def load_lexicon_entries(active_id: Optional[str] = None) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Return (active_id, entries) from active snapshot; entries may be empty."""
    vid = active_id if active_id else read_active_lexicon_id()
    if not vid:
        return None, []
    meta_path = lexicon_version_dir(vid) / "meta.json"
    ent_path = lexicon_version_dir(vid) / "entries.jsonl"
    if not ent_path.is_file():
        return vid, []
    rows: List[Dict[str, Any]] = []
    try:
        with ent_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        return vid, []
    if meta_path.is_file():
        try:
            meta_path.read_text(encoding="utf-8")
        except OSError:
            pass
    return vid, rows


def lexicon_phrases_for_align(entries: List[Dict[str, Any]], *, limit: int = 5000) -> List[str]:
    phrases: List[str] = []
    for row in entries[:limit]:
        name = row.get("name")
        if isinstance(name, str) and name.strip():
            phrases.append(name.strip())
        for al in row.get("aliases") or []:
            if isinstance(al, str) and al.strip():
                phrases.append(al.strip())
    # Dedupe preserving order
    seen = set()
    out: List[str] = []
    for p in phrases:
        k = p.casefold()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out
