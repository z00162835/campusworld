"""Layout helpers for semantic map coordinates (North-up compass)."""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from app.game_engine.direction_util import normalize_direction

CENTER_X = 50
CENTER_Y = 50
COMPASS_RADIUS = 28
# Inner ring for occupants/items/devices — keeps compass ring for directional exits.
_INNER_RING = 14

# Logical room zones (hub-and-spoke; industry IF/MUD pattern).
_LOGICAL_ZONE_ANCHORS: Dict[str, Tuple[int, int]] = {
    "occupant": (CENTER_X, CENTER_Y - _INNER_RING),
    "device": (CENTER_X + _INNER_RING, CENTER_Y),
    "item": (CENTER_X - _INNER_RING, CENTER_Y),
    "exit": (CENTER_X, CENTER_Y + _INNER_RING),
}

# Screen Y decreases toward North (North-up).
_PLANAR_OFFSETS: Dict[str, Tuple[int, int]] = {
    "north": (0, -COMPASS_RADIUS),
    "south": (0, COMPASS_RADIUS),
    "east": (COMPASS_RADIUS, 0),
    "west": (-COMPASS_RADIUS, 0),
    "northeast": (20, -20),
    "northwest": (-20, -20),
    "southeast": (20, 20),
    "southwest": (-20, 20),
}

_VERTICAL_DIRECTIONS = frozenset({"up", "down", "enter", "out"})


def compass_position(direction: str, *, index: int = 0, total: int = 1) -> Tuple[int, int]:
    """Map a normalized direction to (x, y) around the center node."""
    norm = normalize_direction(str(direction or "").strip().lower())
    if norm in _PLANAR_OFFSETS:
        dx, dy = _PLANAR_OFFSETS[norm]
        return (CENTER_X + dx, CENTER_Y + dy)
    if norm in _VERTICAL_DIRECTIONS or not norm:
        return circular_fallback_position(index, total)
    return circular_fallback_position(index, total)


def circular_fallback_position(index: int, total: int) -> Tuple[int, int]:
    """Circular layout when direction is missing or non-planar."""
    if total <= 1:
        return (CENTER_X, CENTER_Y - COMPASS_RADIUS)
    angle = (2 * math.pi * index / total) - math.pi / 2
    x = int(round(CENTER_X + COMPASS_RADIUS * math.cos(angle)))
    y = int(round(CENTER_Y + COMPASS_RADIUS * math.sin(angle)))
    return (x, y)


def assign_neighbor_positions(
    entries: List[Tuple[str, Optional[str]]],
) -> List[Tuple[int, int]]:
    """
    Assign (x, y) for neighbor nodes.

    ``entries`` is ``(direction, target_id)`` in display order.
    """
    positions: List[Tuple[int, int]] = []
    fallback_indices = [i for i, (d, _) in enumerate(entries) if normalize_direction(d) not in _PLANAR_OFFSETS]
    fallback_total = len(fallback_indices)
    fallback_cursor = 0
    for _, (direction, _) in enumerate(entries):
        norm = normalize_direction(str(direction or "").strip().lower())
        if norm in _PLANAR_OFFSETS:
            positions.append(compass_position(norm))
        else:
            positions.append(circular_fallback_position(fallback_cursor, max(1, fallback_total)))
            fallback_cursor += 1
    return positions


def floor_grid_compass_position(anchor_x: int, anchor_y: int, direction: str) -> Tuple[int, int]:
    """Offset a floor-plan anchor by a planar compass direction."""
    norm = normalize_direction(str(direction or "").strip().lower())
    if norm in _PLANAR_OFFSETS:
        dx, dy = _PLANAR_OFFSETS[norm]
        return (anchor_x + dx, anchor_y + dy)
    return circular_fallback_position(0, 1)


def vertical_stack_positions(count: int, *, center_x: int = CENTER_X, start_y: int = 18, step: int = 14) -> List[Tuple[int, int]]:
    """Stack nodes vertically (building floors, list fallback)."""
    if count <= 0:
        return []
    return [(center_x, start_y + index * step) for index in range(count)]


def campus_grid_position(col: int, row: int, *, max_col: int = 24, max_row: int = 20) -> Tuple[int, int]:
    """Campus-layer grid mapped into semantic 0–100 space (North-up)."""
    mc = max(1, int(max_col))
    mr = max(1, int(max_row))
    x = 12 + int((int(col) / mc) * 76)
    y = 12 + int((int(row) / mr) * 76)
    return (x, y)


def horizontal_row_positions(count: int, *, start_x: int = 14, y: int = 50, step: int = 16) -> List[Tuple[int, int]]:
    """Simple row layout when campus grid metadata is absent."""
    if count <= 0:
        return []
    return [(start_x + index * step, y) for index in range(count)]


def logical_zone_positions(count: int, zone: str) -> List[Tuple[int, int]]:
    """Place nodes in a logical room zone around the center hub."""
    if count <= 0:
        return []
    anchor_x, anchor_y = _LOGICAL_ZONE_ANCHORS.get(zone, (CENTER_X, CENTER_Y))
    if zone in {"occupant", "exit"}:
        step = 14
        span = max(0, (count - 1) * step)
        start_x = anchor_x - span // 2
        return [(start_x + index * step, anchor_y) for index in range(count)]
    step = 12
    start_y = anchor_y - (count - 1) * step // 2
    return [(anchor_x, start_y + index * step) for index in range(count)]
