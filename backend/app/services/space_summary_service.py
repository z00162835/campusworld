"""Shared read-only SPACE node summary (SSOT for ``space`` command and semantic map)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.commands.space_command import SpaceCommand, _node_space_trait, _rows_devices, _rows_occupants


def build_space_summary_data(session: Any, node_id: int, *, locale: str = "en") -> Optional[Dict[str, Any]]:
    """Return the same structured payload as ``space -i <node_id>`` CommandResult.data."""
    from app.models.graph import Node, NodeType

    node = session.query(Node).filter(Node.id == int(node_id), Node.is_active == True).first()
    if node is None or not _node_space_trait(session, node):
        return None

    nt = session.query(NodeType).filter(NodeType.id == node.type_id).first()
    ntype_name = (getattr(nt, "type_code", None) or node.type_code or "?").strip()
    cmd = SpaceCommand()
    loc = str(locale or "en")
    s1_lines = cmd._section1_lines(session, node, ntype_name, loc)
    occ = _rows_occupants(session, int(node.id))
    dev = _rows_devices(session, int(node.id))
    s2_rows, s2_data = cmd._section_occupants(occ, loc)
    s3_rows, s3_data = cmd._section_devices(dev, loc)
    s4_rows, s4_data, s4_mode, s4_fb = cmd._section4(session, node, ntype_name, loc)
    s1_text = "\n".join(s1_lines) if s1_lines else ""
    return {
        "space_node": {
            "id": int(node.id),
            "type_code": str(node.type_code or ""),
            "name": str(node.name or ""),
            "parent_id": int(node.location_id) if node.location_id else None,
        },
        "section1_appearance": {"message_fragment": s1_text, "lines": s1_lines},
        "section2_occupants": s2_data,
        "section3_devices": s3_data,
        "section4_next_or_adjacent": s4_data,
        "section4_mode": s4_mode,
        "section4_fallback": s4_fb,
        "section2_rows": s2_rows,
        "section3_rows": s3_rows,
        "section4_rows": s4_rows,
    }
