"""NPC / agent nodes.

NpcAgent 暂不继承 Character（后续可对齐 Evennia 角色树）；Look 按 type_code 与 character 同桶。
"""

from .base import WorldThing


class NpcAgent(WorldThing):
    """Package ``type_code``: ``npc_agent``; see entity type registry in HiCampus SPEC."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "npc_agent"
        super().__init__(name=name, **kwargs)

    def get_display_extra_name_info(self, looker=None, **kwargs):
        del looker, kwargs
        st = self._node_attributes.get("activity") or self._node_attributes.get("mood")
        return f"（{st}）" if st else ""

    def room_line_format_kwargs(self):
        kw = super().room_line_format_kwargs()
        extra = self.get_display_extra_name_info()
        if extra:
            kw["hints"] = (kw.get("hints") or "") + extra
        return kw
