"""
System command ability object model.

Represents a command as a graph object for semantic discovery and later NPC/world orchestration.
Authorization remains in `command_policies` (control plane).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.models.base import DefaultObject


class SystemCommandAbility(DefaultObject):
    """Command ability object (`type_code=system_command_ability`)."""

    def __init__(
        self,
        command_name: str,
        config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        self._node_type = "system_command_ability"

        now = datetime.now().isoformat()
        attrs = {
            "command_name": command_name,
            "aliases": list(kwargs.pop("aliases", [])),
            "command_type": kwargs.pop("command_type", "system"),
            "help_category": kwargs.pop("help_category", "general"),
            "stability": kwargs.pop("stability", "stable"),
            "input_schema": kwargs.pop("input_schema", {}),
            "output_schema": kwargs.pop("output_schema", {}),
            "tags": kwargs.pop("tags", []),
            "updated_at": now,
        }
        if config and "attributes" in config:
            attrs.update(config["attributes"])
        attrs.update(kwargs)

        base_tags = ["system", "ability", "command_ability", "command"]
        if attrs.get("command_type"):
            base_tags.append(str(attrs["command_type"]))
        dynamic_tags = attrs.get("tags", [])
        if isinstance(dynamic_tags, list):
            base_tags.extend(dynamic_tags)

        super().__init__(
            name=command_name,
            attributes=attrs,
            tags=list(dict.fromkeys(base_tags)),
            disable_auto_sync=bool(attrs.get("disable_auto_sync", False)),
            is_public=True,
            access_level="normal",
        )

