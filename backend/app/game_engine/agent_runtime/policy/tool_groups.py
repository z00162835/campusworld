"""tool_group hierarchy and matching rules.

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

from typing import Dict, FrozenSet, Optional, Tuple

# Default parent → children mapping (platform ontology baseline; configurable
# via GateDomainConfig.tool_group_hierarchy, H4).
_DEFAULT_GROUP_CHILDREN: Dict[str, FrozenSet[str]] = {
    "read": frozenset({"observe", "agent_meta", "identity", "communicate"}),
}

# Child → parent reverse mapping (built once at import from the default).
_DEFAULT_GROUP_PARENT: Dict[str, str] = {}
for _parent, _children in _DEFAULT_GROUP_CHILDREN.items():
    for _child in _children:
        _DEFAULT_GROUP_PARENT[_child] = _parent


def _build_parent_map(
    hierarchy: Optional[Dict[str, Tuple[str, ...]]],
) -> Dict[str, str]:
    """Build a child → parent reverse map from a hierarchy dict.

    When ``hierarchy`` is None, returns the default reverse map (byte-equiv).
    """
    if hierarchy is None:
        return dict(_DEFAULT_GROUP_PARENT)
    parent_map: Dict[str, str] = {}
    for parent, children in hierarchy.items():
        for child in children:
            parent_map[child] = parent
    return parent_map


def get_parent(group: str, *, hierarchy: Optional[Dict[str, Tuple[str, ...]]] = None) -> Optional[str]:
    """Return the parent group of ``group``, or ``None`` if it has no parent."""
    parent_map = _build_parent_map(hierarchy)
    return parent_map.get(group)


def is_group_allowed(
    group: str,
    allowed_groups: Tuple[str, ...],
    *,
    hierarchy: Optional[Dict[str, Tuple[str, ...]]] = None,
) -> bool:
    """Check whether ``group`` is covered by ``allowed_groups``.

    True when ``group`` is exactly in ``allowed_groups`` or when the parent
    of ``group`` (per ``hierarchy``) is in ``allowed_groups``.
    """
    allowed_set = set(allowed_groups)
    if group in allowed_set:
        return True
    parent = get_parent(group, hierarchy=hierarchy)
    if parent is not None and parent in allowed_set:
        return True
    return False


def is_any_group_allowed(
    command_groups: Tuple[str, ...],
    skill_allowed_groups: Tuple[str, ...],
    *,
    hierarchy: Optional[Dict[str, Tuple[str, ...]]] = None,
) -> bool:
    """Check whether *any* of ``command_groups`` is covered by ``skill_allowed_groups``."""
    for g in command_groups:
        if is_group_allowed(g, skill_allowed_groups, hierarchy=hierarchy):
            return True
    return False
