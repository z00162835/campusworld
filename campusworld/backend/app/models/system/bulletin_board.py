"""
System bulletin board object.

This object represents the singleton board placed in SingularityRoom.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from app.models.base import DefaultObject


class BulletinBoard(DefaultObject):
    """System singleton bulletin board object."""

    DEFAULT_BOARD_KEY = "system_bulletin_board"

    def __init__(self, name: str = "bulletin_board", config: Optional[Dict[str, Any]] = None, **kwargs):
        self._node_type = "system_bulletin_board"

        attrs = {
            "board_key": self.DEFAULT_BOARD_KEY,
            "display_name": "bulletin_board",
            "desc": "System bulletin board in SingularityRoom",
            "entry_room": "singularity_room",
            "is_system_singleton": True,
            "supports_markdown_notice": True,
            "created_at": datetime.now().isoformat(),
        }
        if config and "attributes" in config:
            attrs.update(config["attributes"])
        attrs.update(kwargs)

        tags = ["system", "bulletin_board", "singleton"]
        if config and "tags" in config:
            tags.extend(config["tags"])

        super().__init__(
            name=name,
            attributes=attrs,
            tags=list(dict.fromkeys(tags)),
            disable_auto_sync=bool(kwargs.get("disable_auto_sync", False)),
            is_public=True,
            access_level="normal",
        )

    def get_display_name(self) -> str:
        return self.get_attribute("display_name", "bulletin_board")

    def get_appearance(self, context=None) -> str:
        # Phase 1 only provides object-level placeholder appearance.
        # Detailed notice rendering is introduced in service integration phases.
        return (
            "bulletin_board\n"
            "System bulletin board. Use look bulletin_board to browse notices."
        )
