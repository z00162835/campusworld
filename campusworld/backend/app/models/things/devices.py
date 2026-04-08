"""Controllable in-room devices (Evennia-style Object descendants via WorldThing)."""

from __future__ import annotations

from typing import Any, Dict

from .base import WorldThing


class NetworkAccessPoint(WorldThing):
    """Package ``type_code``: ``network_access_point``."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "network_access_point"
        super().__init__(name=name, **kwargs)

    def room_line_format_kwargs(self):
        kw = super().room_line_format_kwargs()
        a = self._node_attributes
        parts = []
        ssid = a.get("ssid") or a.get("SSID")
        if ssid:
            parts.append(f"SSID: {ssid}")
        sig = a.get("signal_label") or a.get("signal")
        if sig:
            parts.append(str(sig))
        suffix = ""
        if parts:
            suffix = " · " + " · ".join(parts)
        kw["hints"] = (kw.get("hints") or "") + suffix
        kw["wifi_hint"] = suffix
        return kw


class AvDisplay(WorldThing):
    """Package ``type_code``: ``av_display`` (meeting / signage display)."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "av_display"
        super().__init__(name=name, **kwargs)

    def room_line_format_kwargs(self):
        kw = super().room_line_format_kwargs()
        a = self._node_attributes
        st = a.get("display_state") or a.get("av_state") or a.get("power_state")
        suf = f"（{st}）" if st else ""
        kw["hints"] = (kw.get("hints") or "") + suf
        kw["av_hint"] = suf
        return kw


class LightingFixture(WorldThing):
    """Package ``type_code``: ``lighting_fixture``."""

    def __init__(self, name: str, **kwargs):
        self._node_type = "lighting_fixture"
        super().__init__(name=name, **kwargs)

    def _attributes_for_schema_look(self) -> Dict[str, Any]:
        """Map ``power_on`` into ``status`` for schema-driven examine."""
        a = dict(self._node_attributes)
        if a.get("status") is None and a.get("power_on") is True:
            a["status"] = "on"
        elif a.get("status") is None and a.get("power_on") is False:
            a["status"] = "off"
        return a

    def room_line_format_kwargs(self):
        kw = super().room_line_format_kwargs()
        a = self._node_attributes
        on = a.get("power_on")
        if on is None:
            on = a.get("on")
        if on is True:
            suf = "（开）"
        elif on is False:
            suf = "（关）"
        else:
            suf = ""
        kw["hints"] = (kw.get("hints") or "") + suf
        kw["power_hint"] = suf
        return kw
