"""SkillRunner — activate a skill's L2 body from the registry snapshot.

``prompt`` mode returns a :class:`SkillActivation` carrying the cached body text
and the startup ``definition_hash`` (provenance for trace/audit). ``tool`` and
``hybrid`` modes are scaffolded: they raise ``NotImplementedError`` so a future
non-prompt skill cannot silently no-op before policy/state-machine hooks land.
"""
from __future__ import annotations

from typing import Optional

from app.game_engine.agent_runtime.skills.skill_definition import SkillActivation
from app.game_engine.agent_runtime.skills.skill_registry import SkillRegistry


class SkillRunner:
    def __init__(self, *, registry: SkillRegistry) -> None:
        self._registry = registry

    def activate(self, skill_id: str) -> SkillActivation:
        defn = self._registry.get(skill_id)
        if defn.implementation.mode == "prompt":
            return self._activate_prompt(skill_id, defn)
        # tool / hybrid are scaffolded for v1 (policy engine + structured turn prerequisite).
        raise NotImplementedError(
            f"skill {skill_id!r} implementation.mode={defn.implementation.mode!r} not supported (v1: prompt)"
        )

    def _activate_prompt(self, skill_id: str, defn) -> SkillActivation:
        load = self._registry.load_body(skill_id)
        return SkillActivation(
            skill_id=skill_id,
            text=load.text,
            allowed_tool_groups=tuple(defn.allowed_tool_groups),
            category=defn.category,
            definition_hash=load.definition_hash,
        )
