from __future__ import annotations
import re
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple
import yaml
from app.game_engine.agent_runtime.tool_router.paths import backend_root

class RuleMatch(NamedTuple):
    mandatory: List[str]
    hints: List[str]

def _resolve_rules_path(path_s: str) -> Path:
    p = Path(path_s)
    if p.is_absolute():
        return p
    return backend_root() / p

def load_rule_pack(path_s: str) -> Dict[str, Any]:
    path = _resolve_rules_path(path_s)
    if not path.is_file():
        return {'version': 0, 'rules': []}
    try:
        raw = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except (OSError, yaml.YAMLError):
        return {'version': 0, 'rules': []}
    return raw if isinstance(raw, dict) else {'version': 0, 'rules': []}

def apply_rules(user_message: str, *, rules_path: str) -> Tuple[List[str], List[str], str]:
    """Return (mandatory tool names, rule_hints strings, rule_pack_version)."""
    pack = load_rule_pack(rules_path)
    version = str(pack.get('version') or pack.get('rule_pack_version') or '0')
    rules = pack.get('rules') or []
    if not isinstance(rules, list):
        return ([], [], version)
    mandatory: List[str] = []
    hints: List[str] = []
    text = user_message or ''
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        pattern = rule.get('pattern')
        if not isinstance(pattern, str) or not pattern.strip():
            continue
        try:
            if not re.search(pattern, text, flags=re.UNICODE):
                continue
        except re.error:
            continue
        for m in rule.get('mandatory_tools') or []:
            if isinstance(m, str) and m.strip():
                mandatory.append(m.strip())
        hint = rule.get('hint')
        if isinstance(hint, str) and hint.strip():
            hints.append(hint.strip())
    return (sorted(set(mandatory)), hints, version)

def direction_tokens(text: str) -> List[str]:
    """Lightweight snapshot-free cues for enrich query (v0)."""
    t = (text or '').lower()
    found: List[str] = []
    for d in ('north', 'south', 'east', 'west', 'up', 'down', 'n', 's', 'e', 'w', 'u', 'd'):
        if re.search(f'\\b{re.escape(d)}\\b', t):
            found.append(d)
    return sorted(set(found))
