"""
F11 data_access JSON schema (account Node.attributes.data_access).

Semantics (implementation v1):
- Missing or invalid `data_access` → deny all graph/ontology instance access.
- `permission_template` required; empty nested lists mean "no restriction on that axis"
  except `exclude_nodes_without_world_id` (see below).
- Deny lists subtract after allow.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PermissionTemplate(BaseModel):
    """Allow-set for world / type / relationship / instance."""

    model_config = ConfigDict(extra="ignore")

    world_ids: Optional[List[int]] = Field(
        default=None,
        description="If non-empty, node attributes.world_id (string) must match one of these.",
    )
    type_codes: Optional[List[str]] = Field(
        default=None,
        description="If non-empty, node.type_code must be in this set.",
    )
    relationships_codes: Optional[List[str]] = Field(
        default=None,
        description="If non-empty, relationship.type_code must be in this set.",
    )
    node_ids: Optional[List[int]] = Field(
        default=None,
        description="If non-empty, node.id must be in this set (rare narrow allow).",
    )
    exclude_nodes_without_world_id: bool = Field(
        default=False,
        description="If True, deny nodes with missing/null world_id in attributes (system-domain).",
    )


class DataAccessV1(BaseModel):
    """F11 v1 policy attached to account nodes."""

    model_config = ConfigDict(extra="ignore")

    version: int = Field(default=1, ge=1, le=1)
    permission_template: PermissionTemplate
    denied_world_ids: List[int] = Field(default_factory=list)
    denied_type_codes: List[str] = Field(default_factory=list)
    denied_relationships_codes: List[str] = Field(default_factory=list)
    denied_nodes: List[int] = Field(default_factory=list)

    @field_validator("denied_world_ids", "denied_nodes", mode="before")
    @classmethod
    def _coerce_int_lists(cls, v: Any) -> List[int]:
        if v is None:
            return []
        return [int(x) for x in v]


def parse_data_access(raw: Any) -> Optional[DataAccessV1]:
    """Return None if missing or invalid (caller treats as deny-all)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    try:
        return DataAccessV1.model_validate(raw)
    except Exception:
        return None


def data_access_from_user_attrs(user_attrs: Dict[str, Any]) -> Optional[DataAccessV1]:
    return parse_data_access((user_attrs or {}).get("data_access"))
