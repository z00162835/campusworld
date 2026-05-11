from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from sqlalchemy.orm import Session
from app.models.graph import Node

def iter_graph_nodes_for_lexicon(session: Session) -> Iterable[Dict[str, Any]]:
    """Export active nodes as gazetteer rows (name, type_code, aliases from attributes)."""
    q = session.query(Node).filter(Node.is_active.is_(True))
    for n in q.yield_per(500):
        attrs = n.attributes if isinstance(n.attributes, dict) else {}
        aliases = attrs.get('aliases')
        if aliases is None:
            aliases = attrs.get('alias')
        norm_aliases: List[str] = []
        if isinstance(aliases, list):
            norm_aliases = [str(x).strip() for x in aliases if str(x).strip()]
        elif isinstance(aliases, str) and aliases.strip():
            norm_aliases = [aliases.strip()]
        yield {'id': n.id, 'type_code': n.type_code or '', 'name': n.name or '', 'aliases': norm_aliases}

def compute_lexicon_revision(rows: List[Dict[str, Any]]) -> str:
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]

def build_lexicon_snapshot_rows(session: Session) -> List[Dict[str, Any]]:
    return list(iter_graph_nodes_for_lexicon(session))

def snapshot_meta(*, lexicon_id: str, lexicon_revision: str, built_at: Optional[str]=None, source_graph_hint: str='nodes.is_active') -> Dict[str, Any]:
    return {'id': lexicon_id, 'lexicon_revision': lexicon_revision, 'built_at': built_at or datetime.now(timezone.utc).isoformat(), 'source_graph_hint': source_graph_hint}
