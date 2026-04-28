"""
Default command authorization seeds for first-time DB bootstrap.

Command classes must not encode permissions; this mapping is the code-side
template used only when no policy row exists yet (see ensure_default_command_policies).
"""

from __future__ import annotations

from typing import Any, Dict, List, TypedDict


class PolicySeed(TypedDict, total=False):
    required_permissions_any: List[str]
    required_permissions_all: List[str]
    required_roles_any: List[str]


# Keys are primary command names (registry), not aliases.
# Read-only graph commands (find, describe, space) use the default empty seed = allow when logged in;
# enforcement matches other user commands unless a policy row overrides.
DEFAULT_COMMAND_POLICIES: Dict[str, PolicySeed] = {
    # Most user-facing commands should be available by default (empty policy == allow).
    # Game/world constraints should be enforced by command execution logic, not authz.
    "notice": {"required_permissions_any": ["admin.system_notice"]},
    "world": {"required_permissions_any": ["admin.world.*"]},
    "create": {"required_permissions_any": ["admin.*"]},
    "create_info": {"required_permissions_any": ["admin.*"]},
}


def policy_seed_for(command_name: str) -> Dict[str, Any]:
    """Return seed dict with all three lists present (possibly empty)."""
    seed = DEFAULT_COMMAND_POLICIES.get(command_name, {})
    return {
        "required_permissions_any": list(seed.get("required_permissions_any", [])),
        "required_permissions_all": list(seed.get("required_permissions_all", [])),
        "required_roles_any": list(seed.get("required_roles_any", [])),
    }
