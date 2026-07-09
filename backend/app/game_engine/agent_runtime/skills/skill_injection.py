"""SkillInjection — per-phase eligible/active/inactive manifest + L2 body.

Renders the ``skill-context`` text (L1 manifest block prefix + L2 body block
suffix) for one PDCA phase, using the v1 manifest template with an explicit
active / inactive (awareness-only) split. Only ``phase_mapped`` skills whose
``allowed_in_react_states`` includes the current phase produce an
:class:`SkillActivation` (L2 body injected); ``model_selected`` skills appear
in the manifest only (body deferred to structured-turn ``selected_skill``).
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from app.game_engine.agent_runtime.skills.skill_definition import (
    SkillActivation,
    SkillDefinition,
)
from app.game_engine.agent_runtime.skills.skill_registry import SkillRegistry
from app.game_engine.agent_runtime.skills.skill_runner import SkillRunner

_MANIFEST_HEADER = "## Available Agent Skills\n\nSkills are split by activation status this turn. Active skills' guidance applies; inactive skills are listed for awareness only (not active this turn).\n"
_ACTIVE_HEADING = "### Active skills"
_INACTIVE_HEADING = "### Available but inactive skills"


class SkillInjection:
    def __init__(self, *, registry: SkillRegistry, runner: "SkillRunner | None" = None) -> None:
        self._registry = registry
        self._runner = runner or SkillRunner(registry=registry)

    def render_manifest(self, skill_refs: Sequence[str], *, phase: str) -> str:
        defs = self._registry.manifest_for(skill_refs)
        active: List[SkillDefinition] = []
        inactive: List[SkillDefinition] = []
        for d in defs:
            if _is_eligible(d, phase):
                if _is_active(d, phase):
                    active.append(d)
                else:
                    inactive.append(d)
        if not active and not inactive:
            return ""
        parts: List[str] = [_MANIFEST_HEADER]
        if active:
            parts.append(_ACTIVE_HEADING)
            parts.extend(f"- **{d.name}** — {d.description.strip()}" for d in active)
        if inactive:
            parts.append(_INACTIVE_HEADING)
            parts.extend(f"- **{d.name}** — {d.description.strip()}" for d in inactive)
        return "\n".join(parts) + "\n"

    def inject_bodies(self, skill_refs: Sequence[str], *, phase: str) -> str:
        defs = self._registry.manifest_for(skill_refs)
        bodies: List[str] = []
        for d in defs:
            if _is_active(d, phase):
                act = self._runner.activate(d.name)
                bodies.append(act.text.strip())
        return "\n\n".join(b for b in bodies if b)

    def inject(
        self, skill_refs: Sequence[str], *, phase: str
    ) -> Tuple[str, List[SkillActivation]]:
        defs = self._registry.manifest_for(skill_refs)
        manifest = self.render_manifest(skill_refs, phase=phase)
        activations: List[SkillActivation] = []
        body_parts: List[str] = []
        for d in defs:
            if _is_active(d, phase):
                act = self._runner.activate(d.name)
                activations.append(act)
                body_parts.append(act.text.strip())
        body_text = "\n\n".join(b for b in body_parts if b)
        if not manifest and not body_text:
            return ("", [])
        chunks: List[str] = []
        if manifest:
            chunks.append(manifest.rstrip())
        if body_text:
            chunks.append(body_text)
        return ("\n\n".join(chunks), activations)


def _is_eligible(defn: SkillDefinition, phase: str) -> bool:
    if defn.activation_mode == "model_selected":
        return True
    return phase in defn.allowed_in_react_states


def _is_active(defn: SkillDefinition, phase: str) -> bool:
    return defn.activation_mode == "phase_mapped" and phase in defn.allowed_in_react_states
