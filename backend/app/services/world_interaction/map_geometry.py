"""Grid-to-layout and GeoJSON helpers for semantic map floor plans."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

MAP_GRID_CELL_PX = 4
MAP_GRID_ORIGIN_X = 10
MAP_GRID_ORIGIN_Y = 10


def room_has_map_grid(attrs: Dict[str, Any]) -> bool:
    return attrs.get("map_grid_col") is not None and attrs.get("map_grid_row") is not None


def grid_tile_bounds(
    col: int,
    row: int,
    *,
    span_w: int = 1,
    span_h: int = 1,
    cell_px: int = MAP_GRID_CELL_PX,
    origin_x: int = MAP_GRID_ORIGIN_X,
    origin_y: int = MAP_GRID_ORIGIN_Y,
) -> Tuple[int, int, int, int]:
    """Top-left (x, y) and (width, height) in semantic map units (North-up)."""
    x = int(origin_x + int(col) * cell_px)
    y = int(origin_y + int(row) * cell_px)
    width = int(max(1, span_w) * cell_px)
    height = int(max(1, span_h) * cell_px)
    return (x, y, width, height)


def grid_to_map_coords(
    col: int,
    row: int,
    *,
    span_w: int = 1,
    span_h: int = 1,
    cell_px: int = MAP_GRID_CELL_PX,
    origin_x: int = MAP_GRID_ORIGIN_X,
    origin_y: int = MAP_GRID_ORIGIN_Y,
) -> Tuple[int, int]:
    """Convert floor grid cell to semantic map x/y (North-up: smaller row = north)."""
    center_col = col + max(1, span_w) / 2.0
    center_row = row + max(1, span_h) / 2.0
    x = int(origin_x + center_col * cell_px)
    y = int(origin_y + center_row * cell_px)
    return (x, y)


def grid_to_geom_geojson(
    col: int,
    row: int,
    *,
    span_w: int = 1,
    span_h: int = 1,
    cell_unit: float = 1.0,
    floor_id: str = "",
    building_id: str = "",
) -> Dict[str, Any]:
    """Derive a floor-local rectangular GeoJSON Feature from grid metadata."""
    x0 = float(col) * cell_unit
    y0 = float(row) * cell_unit
    x1 = x0 + float(span_w) * cell_unit
    y1 = y0 + float(span_h) * cell_unit
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [x0, y0],
                    [x1, y0],
                    [x1, y1],
                    [x0, y1],
                    [x0, y0],
                ]
            ],
        },
        "properties": {
            "crs": "floor_local",
            "floor_id": floor_id,
            "building_id": building_id,
            "map_grid_col": col,
            "map_grid_row": row,
            "map_grid_span_w": span_w,
            "map_grid_span_h": span_h,
        },
    }


def geom_from_room_attrs(attrs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not room_has_map_grid(attrs):
        return None
    try:
        col = int(attrs["map_grid_col"])
        row = int(attrs["map_grid_row"])
        span_w = int(attrs.get("map_grid_span_w") or 1)
        span_h = int(attrs.get("map_grid_span_h") or 1)
        unit = float(attrs.get("map_grid_unit") or 1)
    except (TypeError, ValueError):
        return None
    return grid_to_geom_geojson(
        col,
        row,
        span_w=span_w,
        span_h=span_h,
        cell_unit=unit,
        floor_id=str(attrs.get("floor_id") or ""),
        building_id=str(attrs.get("building_id") or ""),
    )
