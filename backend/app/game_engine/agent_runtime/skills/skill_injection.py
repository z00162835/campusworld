"""SkillInjection — per-phase eligible/active/inactive/blocked manifest + L2 body.

Renders the ``skill-context`` text (L1 manifest block prefix + L2 body block
suffix) for one PDCA phase, using the v1 manifest template with an explicit
active / inactive (awareness-only) / blocked split. Only ``phase_mapped`` skills
whose ``allowed_in_react_states`` includes the current phase produce an
:class:`SkillActivation` (L2 body injected); ``model_selected`` skills appear
in the manifest only (body deferred to structured-turn ``selected_skill``);
blocked skills are denied by an optional ``before_activate`` policy hook and
rendered in a dedicated section so the model can distinguish policy-denied
skills from merely inactive ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from app.game_engine.agent_runtime.skills.skill_definition import (
    SkillActivation,
    SkillDefinition,
)
from app.game_engine.agent_runtime.skills.skill_registry import SkillRegistry
from app.game_engine.agent_runtime.skills.skill_runner import SkillRunner

_MANIFEST_HEADER = (
    "## Available Agent Skills\n\n"
    "Skills are split by activation status this turn. "
    "Active skills' guidance applies; inactive skills are listed for awareness only; "
    "blocked skills were denied by policy and are not active this turn.\n"
)
_ACTIVE_HEADING = "### Active skills"
_INACTIVE_HEADING = "### Available but inactive skills"
_BLOCKED_HEADING = "### Blocked by policy"

BeforeActivateHook = Callable[[SkillDefinition, str], Optional[str]]
"""Optional policy hook: (skill_definition, phase) -> reason_code or None."""


@dataclass(frozen=True)
class SkillInjectionResult:
    """Result of one phase injection: manifest+body text, activations, blocked skills."""

    text: str
    activations: Tuple[SkillActivation, ...] = ()
    blocked: Tuple[SkillDefinition, ...] = ()
    blocked_reasons: Tuple[str, ...] = ()


class SkillInjection:
    def __init__(self, *, registry: SkillRegistry, runner: "SkillRunner | None" = None) -> None:
        self._registry = registry
        self._runner = runner or SkillRunner(registry=registry)

    def render_manifest(
        self,
        skill_refs: Sequence[str],
        *,
        phase: str,
        blocked: Optional[Sequence[SkillDefinition]] = None,
        blocked_reasons: Optional[Sequence[str]] = None,
    ) -> str:
        defs = self._registry.manifest_for(skill_refs)
        active: List[SkillDefinition] = []
        inactive: List[SkillDefinition] = []
        for d in defs:
            if _is_eligible(d, phase) and not _in_blocked(d, blocked):
                if _is_active(d, phase):
                    active.append(d)
                else:
                    inactive.append(d)
        blocked_defs = list(blocked or ())
        if not active and not inactive and not blocked_defs:
            return ""
        parts: List[str] = [_MANIFEST_HEADER]
        if active:
            parts.append(_ACTIVE_HEADING)
            parts.extend(f"- **{d.name}** — {d.description.strip()}" for d in active)
        if inactive:
            parts.append(_INACTIVE_HEADING)
            parts.extend(f"- **{d.name}** — {d.description.strip()}" for d in inactive)
        if blocked_defs:
            parts.append(_BLOCKED_HEADING)
            reasons = list(blocked_reasons or ())
            for i, d in enumerate(blocked_defs):
                reason = reasons[i] if i < len(reasons) else "policy_denied"
                parts.append(f"- **{d.name}** — {d.description.strip()} (reason: {reason})")
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
        self,
        skill_refs: Sequence[str],
        *,
        phase: str,
        before_activate: Optional[BeforeActivateHook] = None,
    ) -> SkillInjectionResult:
        defs = self._registry.manifest_for(skill_refs)
        activations: List[SkillActivation] = []
        body_parts: List[str] = []
        blocked: List[SkillDefinition] = []
        blocked_reasons: List[str] = []
        for d in defs:
            if not _is_active(d, phase):
                continue
            reason: Optional[str] = None
            if before_activate is not None:
                reason = before_activate(d, phase)
            if reason is not None:
                blocked.append(d)
                blocked_reasons.append(reason)
                continue
            act = self._runner.activate(d.name)
            activations.append(act)
            body_parts.append(act.text.strip())
        manifest = self.render_manifest(
            skill_refs,
            phase=phase,
            blocked=blocked,
            blocked_reasons=blocked_reasons,
        )
        body_text = "\n\n".join(b for b in body_parts if b)
        if not manifest and not body_text:
            return SkillInjectionResult(text="")
        chunks: List[str] = []
        if manifest:
            chunks.append(manifest.rstrip())
        if body_text:
            chunks.append(body_text)
        return SkillInjectionResult(
            text="\n\n".join(chunks),
            activations=tuple(activations),
            blocked=tuple(blocked),
            blocked_reasons=tuple(blocked_reasons),
        )


def _is_eligible(defn: SkillDefinition, phase: str) -> bool:
    if defn.activation_mode == "model_selected":
        return True
    return phase in defn.allowed_in_react_states


def _is_active(defn: SkillDefinition, phase: str) -> bool:
    return defn.activation_mode == "phase_mapped" and phase in defn.allowed_in_react_states


def _in_blocked(defn: SkillDefinition, blocked: Optional[Sequence[SkillDefinition]]) -> bool:
    if not blocked:
        return False
    return any(b.name == defn.name for b in blocked)
