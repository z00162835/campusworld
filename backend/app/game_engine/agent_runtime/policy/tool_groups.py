"""tool_group hierarchy and matching rules (SPEC §4.4).

v1 taxonomy:

    read (parent)
    ├── observe
    ├── agent_meta
    ├── identity
    └── communicate

    mutate (no subgroups in v1)
    admin (reserved, no subgroups in v1)

Matching rule: a command group ``g`` is allowed by a skill's
``allowed_tool_groups`` set ``S`` when either:
  1. ``g`` is exactly in ``S``, or
  2. the parent of ``g`` is in ``S``.

Example: ``allowed_tool_groups: [read]`` allows commands whose groups are
``read``, ``observe``, ``agent_meta``, ``identity``, or ``communicate``.
``allowed_tool_groups: [observe]`` allows only ``observe`` commands.
"""
from __future__ import annotations

from typing import FrozenSet, Tuple

# Parent → children mapping.
_GROUP_CHILDREN: dict[str, FrozenSet[str]] = {
    "read": frozenset({"observe", "agent_meta", "identity", "communicate"}),
}

# Child → parent reverse mapping (built once at import).
_GROUP_PARENT: dict[str, str] = {}
for _parent, _children in _GROUP_CHILDREN.items():
    for _child in _children:
        _GROUP_PARENT[_child] = _parent


def get_parent(group: str) -> str | None:
    """Return the parent group of ``group``, or ``None`` if it has no parent."""
    return _GROUP_PARENT.get(group)


def is_group_allowed(group: str, allowed_groups: Tuple[str, ...]) -> bool:
    """Check whether ``group`` is covered by ``allowed_groups``.

    True when ``group`` is exactly in ``allowed_groups`` or when the parent
    of ``group`` is in ``allowed_groups``.
    """
    allowed_set = set(allowed_groups)
    if group in allowed_set:
        return True
    parent = get_parent(group)
    if parent is not None and parent in allowed_set:
        return True
    return False


def is_any_group_allowed(
    command_groups: Tuple[str, ...],
    skill_allowed_groups: Tuple[str, ...],
) -> bool:
    """Check whether *any* of ``command_groups`` is covered by ``skill_allowed_groups``."""
    for g in command_groups:
        if is_group_allowed(g, skill_allowed_groups):
            return True
    return False
