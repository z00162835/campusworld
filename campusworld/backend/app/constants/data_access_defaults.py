"""
Default F11 `data_access` blobs for seeded accounts (see F11 SPEC).

Admin: open template (empty lists = no restriction per axis), empty denies.
Dev: open graph for debugging; still no RBAC data short-circuit — wide template.
User/campus: deny account instances; require world_id on content nodes so system-domain
nodes without world_id are invisible. Optional world allowlist can be set after install.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

ADMIN_DATA_ACCESS: Dict[str, Any] = {
    "version": 1,
    "permission_template": {
        "world_ids": [],
        "type_codes": [],
        "relationships_codes": [],
        "node_ids": [],
        "exclude_nodes_without_world_id": False,
    },
    "denied_world_ids": [],
    "denied_type_codes": [],
    "denied_relationships_codes": [],
    "denied_nodes": [],
}

DEV_DATA_ACCESS: Dict[str, Any] = {
    "version": 1,
    "permission_template": {
        "world_ids": [],
        "type_codes": [],
        "relationships_codes": [],
        "node_ids": [],
        "exclude_nodes_without_world_id": False,
    },
    "denied_world_ids": [],
    "denied_type_codes": [],
    "denied_relationships_codes": [],
    "denied_nodes": [],
}

USER_LIKE_DATA_ACCESS: Dict[str, Any] = {
    "version": 1,
    "permission_template": {
        "world_ids": [],
        "type_codes": [],
        "relationships_codes": [],
        "node_ids": [],
        "exclude_nodes_without_world_id": True,
    },
    "denied_world_ids": [],
    "denied_type_codes": ["account"],
    "denied_relationships_codes": [],
    "denied_nodes": [],
}


def merge_data_access_into_attributes(attrs: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    """Return new attributes dict with data_access set (copy-on-write)."""
    out = deepcopy(attrs or {})
    out["data_access"] = deepcopy(policy)
    return out
