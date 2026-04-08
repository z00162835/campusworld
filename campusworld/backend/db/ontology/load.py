"""Load optional YAML overlays for graph-seed node_types (schema_definition, etc.)."""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

_DEFAULT_FILE = Path(__file__).resolve().parent / "graph_seed_node_types.yaml"


def default_graph_seed_node_types_path() -> Path:
    return _DEFAULT_FILE


def load_graph_seed_node_type_overrides(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """
    Return map type_code -> overlay dict with optional keys:
    schema_definition, schema_default, inferred_rules, tags, ui_config, description.
    Missing file -> {}.
    """
    p = path or _DEFAULT_FILE
    if not p.is_file():
        return {}
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw = doc.get("node_types")
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in raw.items():
        code = str(k).strip()
        if not code or not isinstance(v, dict):
            continue
        out[code] = v
    return out


@functools.lru_cache(maxsize=1)
def _graph_seed_node_type_overlays_cached() -> Dict[str, Dict[str, Any]]:
    """In-process cache for default-path YAML (invalidated only by process restart)."""
    return load_graph_seed_node_type_overrides(None)


def clear_graph_seed_node_type_cache() -> None:
    """Tests or reload hooks may call to drop cached overlays."""
    _graph_seed_node_type_overlays_cached.cache_clear()


def get_graph_seed_schema_definition(type_code: str) -> Optional[Dict[str, Any]]:
    """
    Return merged schema_definition for a graph-seed type_code from packaged YAML.

    Used at runtime for schema-driven examine text; DB may hold the same JSON after migrate.
    """
    code = str(type_code or "").strip()
    if not code:
        return None
    ent = _graph_seed_node_type_overlays_cached().get(code) or {}
    sd = ent.get("schema_definition")
    if not isinstance(sd, dict):
        return None
    if not isinstance(sd.get("properties"), dict):
        return None
    return sd


def node_type_jsonb_params(overlay: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Build CAST(:name AS jsonb) bind parameters as JSON strings."""
    o = overlay or {}
    sd = o.get("schema_definition")
    if sd is not None and not isinstance(sd, dict):
        sd = {}
    elif sd is None:
        sd = {}
    sdef = o.get("schema_default")
    if sdef is not None and not isinstance(sdef, dict):
        sdef = {}
    elif sdef is None:
        sdef = {}
    ir = o.get("inferred_rules")
    if ir is not None and not isinstance(ir, dict):
        ir = {}
    elif ir is None:
        ir = {}
    tags = o.get("tags")
    if tags is not None and not isinstance(tags, list):
        tags = []
    elif tags is None:
        tags = []
    ui = o.get("ui_config")
    if ui is not None and not isinstance(ui, dict):
        ui = {}
    elif ui is None:
        ui = {}
    return {
        "schema_definition": json.dumps(sd, ensure_ascii=False),
        "schema_default": json.dumps(sdef, ensure_ascii=False),
        "inferred_rules": json.dumps(ir, ensure_ascii=False),
        "tags": json.dumps(tags, ensure_ascii=False),
        "ui_config": json.dumps(ui, ensure_ascii=False),
    }
