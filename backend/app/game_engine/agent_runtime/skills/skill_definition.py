"""SkillDefinition + SKILL.md frontmatter parser.

Single-file ``SKILL.md`` = YAML frontmatter + markdown body (Anthropic Agent
Skills convention). frontmatter parses to an immutable :class:`SkillDefinition`
(L1 manifest data source); body is the L2 prompt text cached verbatim.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Sequence, Tuple

from app.commands.command_tool_semantics import ToolSideEffectLevel

SkillCategory = Literal[
    "reasoning", "retrieval", "analysis", "observation",
    "verifier", "finalization", "user_interaction",
]
ActivationMode = Literal["phase_mapped", "model_selected"]
SkillImplementationMode = Literal["prompt", "tool", "hybrid"]
SkillSideEffectLevel = ToolSideEffectLevel

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_DESCRIPTION_MAX = 1024
_SUPPORTED_IMPLEMENTATION_MODES: Tuple[str, ...] = ("prompt",)
_VALID_ACTIVATION_MODES: frozenset[str] = frozenset({"phase_mapped", "model_selected"})
_VALID_CATEGORIES: frozenset[str] = frozenset({
    "reasoning", "retrieval", "analysis", "observation",
    "verifier", "finalization", "user_interaction",
})
_VALID_SIDE_EFFECT_LEVELS: frozenset[str] = frozenset({
    "none", "read", "write_low", "write_high",
})


@dataclass(frozen=True)
class SkillImplementation:
    mode: SkillImplementationMode = "prompt"


@dataclass(frozen=True)
class SkillDefinition:
    name: str
    description: str
    implementation: SkillImplementation
    display_name: Optional[str] = None
    category: Optional[SkillCategory] = None
    side_effect_level: Optional[SkillSideEffectLevel] = None
    activation_mode: ActivationMode = "phase_mapped"
    allowed_in_react_states: Tuple[str, ...] = ()
    allowed_tool_groups: Tuple[str, ...] = ()
    runtime: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _NAME_RE.match(self.name or ""):
            raise ValueError(f"skill name {self.name!r} must match {_NAME_RE.pattern}")
        desc = (self.description or "").strip()
        if not desc:
            raise ValueError(f"skill {self.name!r}: description required")
        if len(desc) > _DESCRIPTION_MAX:
            raise ValueError(
                f"skill {self.name!r}: description exceeds {_DESCRIPTION_MAX} chars"
            )
        if self.activation_mode not in _VALID_ACTIVATION_MODES:
            raise ValueError(
                f"skill {self.name!r}: invalid activation_mode {self.activation_mode!r}; "
                f"expected one of {sorted(_VALID_ACTIVATION_MODES)}"
            )
        if self.category is not None and self.category not in _VALID_CATEGORIES:
            raise ValueError(
                f"skill {self.name!r}: invalid category {self.category!r}; "
                f"expected one of {sorted(_VALID_CATEGORIES)}"
            )
        if (
            self.side_effect_level is not None
            and self.side_effect_level not in _VALID_SIDE_EFFECT_LEVELS
        ):
            raise ValueError(
                f"skill {self.name!r}: invalid side_effect_level {self.side_effect_level!r}; "
                f"expected one of {sorted(_VALID_SIDE_EFFECT_LEVELS)}"
            )
        if self.activation_mode == "phase_mapped" and not self.allowed_in_react_states:
            raise ValueError(
                f"skill {self.name!r}: activation_mode=phase_mapped requires >=1 allowed_in_react_states"
            )
        if self.activation_mode == "model_selected" and self.allowed_in_react_states:
            raise ValueError(
                f"skill {self.name!r}: activation_mode=model_selected forbids allowed_in_react_states"
            )
        if self.implementation.mode not in _SUPPORTED_IMPLEMENTATION_MODES:
            raise ValueError(
                f"skill {self.name!r}: implementation.mode {self.implementation.mode!r} not supported (v1: prompt)"
            )

    @property
    def effective_display_name(self) -> str:
        return self.display_name or self.name


@dataclass(frozen=True)
class SkillBodyLoad:
    """L2 body + provenance hash, from the startup snapshot (no disk read)."""

    text: str
    definition_hash: str


@dataclass(frozen=True)
class SkillActivation:
    """Per-skill activation payload consumed by SkillInjection and policy audit hooks."""

    skill_id: str
    text: str
    allowed_tool_groups: Tuple[str, ...]
    category: Optional[SkillCategory]
    definition_hash: str


def parse_skill_md(source: str, dir_name: str) -> Tuple[SkillDefinition, str]:
    """Parse a ``SKILL.md`` source string into (definition, body).

    frontmatter is the YAML between leading ``---`` and the closing ``---``;
    the remainder is the markdown body (L2 prompt text).
    """
    if source is None:
        raise ValueError("empty SKILL.md source")
    text = source.lstrip("\ufeff")
    if not text.startswith("---"):
        raise ValueError("SKILL.md must start with YAML frontmatter (---)")
    lines = text.splitlines()
    # First line is the opening ---; find the closing ---.
    close_idx: Optional[int] = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        raise ValueError("SKILL.md frontmatter not closed (missing closing ---)")
    fm_text = "\n".join(lines[1:close_idx])
    body = "\n".join(lines[close_idx + 1 :]).lstrip("\n")
    try:
        import yaml

        raw = yaml.safe_load(fm_text) or {}
    except Exception as exc:  # noqa: BLE001 - surface as validation error
        raise ValueError(f"SKILL.md frontmatter YAML parse failed: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    defn = _dict_to_definition(raw, dir_name=dir_name)
    return (defn, body)


def _dict_to_definition(raw: Dict[str, Any], *, dir_name: str) -> SkillDefinition:
    name = str(raw.get("name") or "").strip()
    if name != dir_name:
        raise ValueError(
            f"skill name {name!r} must match its directory name {dir_name!r}"
        )
    impl_raw = raw.get("implementation") or {}
    if not isinstance(impl_raw, dict):
        impl_raw = {}
    implementation = SkillImplementation(mode=str(impl_raw.get("mode") or "prompt"))
    states = _to_tuple_of_str(raw.get("allowed_in_react_states"))
    groups = _to_tuple_of_str(raw.get("allowed_tool_groups"))
    return SkillDefinition(
        name=name,
        description=str(raw.get("description") or "").strip(),
        implementation=implementation,
        display_name=_opt_str(raw.get("display_name")),
        category=raw.get("category"),
        side_effect_level=raw.get("side_effect_level"),
        activation_mode=str(raw.get("activation_mode") or "phase_mapped"),
        allowed_in_react_states=states,
        allowed_tool_groups=groups,
        runtime=dict(raw.get("runtime") or {}),
    )


def _to_tuple_of_str(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(x).strip() for x in value if str(x).strip())
    return ()


def _opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s or None
