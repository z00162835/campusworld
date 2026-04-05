"""Level-3 typeclass base for graph-seeded world entities (Evennia-style).

See HiCampus SPEC (features/) entity type registry for type_code ↔ ontology mapping.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models.base import DefaultObject


class WorldThing(DefaultObject):
    """Shared base for HiCampus entity node typeclasses; look/examine hooks."""

    def get_display_desc(self, looker=None, **kwargs) -> str:
        d = super().get_display_desc(looker=looker, **kwargs)
        if d:
            return d
        syn = self._synthetic_device_look_desc()
        return syn or ""

    def _synthetic_device_look_desc(self) -> str:
        a = self._node_attributes
        if str(a.get("item_kind") or "") != "device":
            return ""
        role = str(a.get("device_role") or "")
        if role == "lighting":
            return self._desc_lighting_fixture(a)
        if role == "wifi_ap":
            return self._desc_network_access_point(a)
        if role == "display":
            return self._desc_av_device(a)
        if role == "access_terminal":
            return self._desc_access_terminal(a)
        return ""

    def _desc_lighting_fixture(self, a: Dict[str, Any]) -> str:
        lt = a.get("lighting") if isinstance(a.get("lighting"), dict) else {}
        st = a.get("status")
        if st is None and a.get("power_on") is True:
            st = "on"
        elif st is None and a.get("power_on") is False:
            st = "off"
        bits: List[str] = []
        if isinstance(st, str) and st.strip():
            bits.append(f"状态「{st.strip()}」")
        bp = lt.get("brightness_pct")
        ct = lt.get("color_temp_k")
        sc = lt.get("scene")
        if bp is not None:
            bits.append(f"亮度约 {bp}%")
        if ct is not None:
            bits.append(f"色温约 {ct} K")
        if isinstance(sc, str) and sc.strip():
            bits.append(f"场景「{sc.strip()}」")
        if not bits:
            return "一路受控照明回路，用于空间照度与场景策略。"
        return "室内照明回路，" + "，".join(bits) + "。"

    def _desc_network_access_point(self, a: Dict[str, Any]) -> str:
        net = a.get("network") if isinstance(a.get("network"), dict) else {}
        ssid = str(net.get("ssid") or "").strip()
        bands = net.get("bands")
        enc = str(net.get("encryption") or "").strip()
        mode = str(net.get("mode") or "ap").strip()
        st = str(a.get("status") or "").strip()
        parts: List[str] = ["这是一台无线接入点"]
        if mode:
            parts.append(f"，工作模式为「{mode}」")
        parts.append("。")
        if ssid:
            parts.append(f"主用 SSID：{ssid}。")
        if isinstance(bands, list) and bands:
            parts.append(f"频段：{', '.join(str(b) for b in bands)}。")
        if enc:
            parts.append(f"链路加密：{enc}。")
        if st:
            parts.append(f"设备状态：{st}。")
        tele = a.get("telemetry") if isinstance(a.get("telemetry"), dict) else {}
        clients = tele.get("clients")
        if isinstance(clients, int):
            parts.append(f"当前关联终端数：{clients}。")
        return "".join(parts)

    def _desc_av_device(self, a: Dict[str, Any]) -> str:
        av = a.get("av") if isinstance(a.get("av"), dict) else {}
        res = str(av.get("resolution") or "").strip()
        vol = av.get("volume_pct")
        parts = ["这是一块会议/公共显示设备。"]
        if res:
            parts.append(f"分辨率标称 {res}。")
        if vol is not None:
            parts.append(f"音量约 {vol}%。")
        st = str(a.get("status") or "").strip()
        if st:
            parts.append(f"状态：{st}。")
        return "".join(parts)

    def _desc_access_terminal(self, a: Dict[str, Any]) -> str:
        acc = a.get("access") if isinstance(a.get("access"), dict) else {}
        mode = str(acc.get("mode") or "").strip()
        base = "这是一台门禁/闸机侧访问终端，用于凭证核验与通行控制。"
        if mode:
            return f"{base} 核验方式：{mode}。"
        return base
