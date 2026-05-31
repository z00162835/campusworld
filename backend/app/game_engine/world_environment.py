"""Resolve and format world-level environment graph nodes."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from sqlalchemy.orm import Session

from app.models.graph import Node

_WEATHER_LABELS: Dict[str, str] = {
    'clear': '晴',
    'cloudy': '多云',
    'overcast': '阴',
    'rain': '雨',
    'fog': '雾',
}


def resolve_world_environment(session: Session, *, world_id: str) -> Optional[Node]:
    """Return the active ``world_environment`` node for a package ``world_id``."""
    wid = str(world_id or '').strip()
    if not wid or session is None:
        return None
    return (
        session.query(Node)
        .filter(
            Node.type_code == 'world_environment',
            Node.is_active.is_(True),
            Node.attributes['world_id'].astext == wid,
        )
        .first()
    )


def format_environment_summary(attrs: Mapping[str, Any]) -> str:
    """Single-line Chinese summary for outdoor ``look``."""
    raw_code = str(attrs.get('weather_code') or '').strip().lower()
    weather = _WEATHER_LABELS.get(raw_code, raw_code or '未知')
    parts = [f'室外：{weather}']
    temp = attrs.get('temperature_c')
    if temp is not None:
        try:
            parts.append(f'{float(temp):.0f}°C')
        except (TypeError, ValueError):
            pass
    hum = attrs.get('humidity_pct')
    if hum is not None:
        try:
            parts.append(f'湿度 {int(hum)}%')
        except (TypeError, ValueError):
            pass
    return '，'.join(parts)
