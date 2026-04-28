"""
System notice object model.

Represents one notice entry under system bulletin board semantics.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from app.models.base import DefaultObject


class SystemNotice(DefaultObject):
    """System notice object (`type_code=system_notice`)."""

    def __init__(self, title: str, content_md: str, config: Optional[Dict[str, Any]] = None, **kwargs):
        self._node_type = "system_notice"

        now = datetime.now().isoformat()
        attrs = {
            "title": title,
            "content_md": content_md,
            "status": kwargs.pop("status", "published"),
            "is_active": kwargs.pop("is_active", True),
            "priority": kwargs.pop("priority", "normal"),
            "published_at": kwargs.pop("published_at", now),
            "updated_at": now,
            "author_id": kwargs.pop("author_id", None),
            "notice_code": kwargs.pop("notice_code", None),
            "tags": kwargs.pop("tags", []),
        }
        if config and "attributes" in config:
            attrs.update(config["attributes"])
        attrs.update(kwargs)

        base_tags = ["system", "notice", "bulletin_notice"]
        if attrs.get("status"):
            base_tags.append(str(attrs["status"]))
        dynamic_tags = attrs.get("tags", [])
        if isinstance(dynamic_tags, list):
            base_tags.extend(dynamic_tags)

        super().__init__(
            name=title,
            attributes=attrs,
            tags=list(dict.fromkeys(base_tags)),
            disable_auto_sync=bool(attrs.get("disable_auto_sync", False)),
            is_public=True,
            access_level="normal",
        )

    def get_summary(self) -> Dict[str, Any]:
        """Return lightweight list-view payload."""
        return {
            "id": self.id,
            "title": self.get_attribute("title", self.name),
            "published_at": self.get_attribute("published_at"),
            "priority": self.get_attribute("priority", "normal"),
            "status": self.get_attribute("status", "published"),
        }

    def to_notice_dto(self) -> Dict[str, Any]:
        """Return complete notice payload for service/command layers."""
        return {
            "id": self.id,
            "uuid": self.get_node_uuid(),
            "title": self.get_attribute("title", self.name),
            "content_md": self.get_attribute("content_md", ""),
            "status": self.get_attribute("status", "published"),
            "is_active": self.get_attribute("is_active", True),
            "priority": self.get_attribute("priority", "normal"),
            "published_at": self.get_attribute("published_at"),
            "updated_at": self.get_attribute("updated_at"),
            "author_id": self.get_attribute("author_id"),
            "notice_code": self.get_attribute("notice_code"),
            "tags": self.get_attribute("tags", []),
        }
