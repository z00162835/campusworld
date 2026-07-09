"""SkillRegistry — startup snapshot of all Agent Skills (no hot reload).

Scans ``config/skills/<skill_id>/SKILL.md`` once at construction, reads the
full file source, parses frontmatter to :class:`SkillDefinition`, and caches
the body plus a ``definition_hash`` (sha256 of the full source) in memory.
Tick-time lookups never touch disk; L1 manifest, L2 body, and hash share one
startup snapshot. Editing a ``SKILL.md`` after load has no effect until the
registry is rebuilt or the process restarts (v1 has no hot reload).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from app.game_engine.agent_runtime.skills.skill_definition import (
    SkillBodyLoad,
    SkillDefinition,
    parse_skill_md,
)

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SKILLS_DIR = _BACKEND_ROOT / "config" / "skills"
_HASH_TRUNC = 16


@dataclass(frozen=True)
class _CachedSkill:
    definition: SkillDefinition
    body: str
    definition_hash: str


class SkillRegistry:
    """In-memory registry of parsed Agent Skills (startup snapshot)."""

    def __init__(self, *, skills_dir: Optional[Path] = None) -> None:
        self._skills_dir = Path(skills_dir) if skills_dir is not None else DEFAULT_SKILLS_DIR
        self._by_id: Dict[str, _CachedSkill] = {}
        self._load()

    def _load(self) -> None:
        if not self._skills_dir.is_dir():
            logger.info("skill_registry: skills dir not found %s (registry empty)", self._skills_dir)
            return
        for child in sorted(self._skills_dir.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue
            self._load_one(child, skill_md)

    def _load_one(self, skill_dir: Path, skill_md: Path) -> None:
        try:
            source = skill_md.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("skill_registry: cannot read %s: %s", skill_md, exc)
            return
        (defn, body) = parse_skill_md(source, dir_name=skill_dir.name)
        definition_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:_HASH_TRUNC]
        cached = _CachedSkill(definition=defn, body=body, definition_hash=definition_hash)
        if defn.name in self._by_id:
            raise ValueError(f"duplicate skill name {defn.name!r} in {self._skills_dir}")
        self._by_id[defn.name] = cached
        self._warn_l3_bundled(skill_dir, defn)

    def _warn_l3_bundled(self, skill_dir: Path, defn: SkillDefinition) -> None:
        if defn.implementation.mode != "prompt":
            return
        extras: List[str] = []
        for sub in ("references", "assets"):
            if (skill_dir / sub).is_dir():
                extras.append(sub)
        if extras:
            logger.warning(
                "skill_registry: skill %s dir contains %s; v1 prompt mode does not read L3 bundled "
                "resources — body must be self-contained",
                defn.name,
                "/".join(extras),
            )

    def contains(self, skill_id: str) -> bool:
        return skill_id in self._by_id

    def get(self, skill_id: str) -> SkillDefinition:
        cached = self._by_id.get(skill_id)
        if cached is None:
            raise KeyError(skill_id)
        return cached.definition

    def manifest_for(self, skill_refs: Sequence[str]) -> List[SkillDefinition]:
        """L1 manifest entries for the given skill_refs, preserving declaration order."""
        seen: set = set()
        out: List[SkillDefinition] = []
        for sid in skill_refs or ():
            sid_s = str(sid).strip()
            if not sid_s or sid_s in seen:
                continue
            seen.add(sid_s)
            cached = self._by_id.get(sid_s)
            if cached is not None:
                out.append(cached.definition)
        return out

    def load_body(self, skill_id: str) -> SkillBodyLoad:
        cached = self._by_id.get(skill_id)
        if cached is None:
            raise KeyError(skill_id)
        return SkillBodyLoad(text=cached.body, definition_hash=cached.definition_hash)

    def definition_hash(self, skill_id: str) -> str:
        cached = self._by_id.get(skill_id)
        if cached is None:
            raise KeyError(skill_id)
        return cached.definition_hash

    @property
    def skill_ids(self) -> List[str]:
        return list(self._by_id.keys())


_DEFAULT_REGISTRY: Optional[SkillRegistry] = None


def get_default_skill_registry() -> SkillRegistry:
    """Module-level singleton over ``config/skills`` (lazy, cached for process lifetime)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = SkillRegistry()
    return _DEFAULT_REGISTRY


def reset_default_skill_registry() -> None:
    """Drop the cached singleton (tests / explicit rebuild)."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None
