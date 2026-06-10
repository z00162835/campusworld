"""Unit tests for semantic map grid geometry helpers."""
from __future__ import annotations

from app.services.world_interaction.map_geometry import (
    geom_from_room_attrs,
    grid_to_geom_geojson,
    grid_to_map_coords,
    room_has_map_grid,
)


def test_room_has_map_grid_true_when_both_present():
    assert room_has_map_grid({"map_grid_col": 1, "map_grid_row": 2}) is True


def test_grid_to_map_coords_uses_cell_centers():
    x, y = grid_to_map_coords(4, 2, span_w=2, span_h=2, cell_px=4, origin_x=10, origin_y=10)
    assert x == 10 + 5 * 4
    assert y == 10 + 3 * 4


def test_geom_from_room_attrs_returns_feature_polygon():
    geom = geom_from_room_attrs(
        {
            "map_grid_col": 2,
            "map_grid_row": 3,
            "map_grid_span_w": 1,
            "map_grid_span_h": 1,
            "floor_id": "hicampus_f3_03f",
            "building_id": "hicampus_f3",
        }
    )
    assert geom is not None
    assert geom["type"] == "Feature"
    assert geom["geometry"]["type"] == "Polygon"
    assert geom["properties"]["crs"] == "floor_local"


def test_grid_to_geom_geojson_is_valid_feature():
    feature = grid_to_geom_geojson(0, 0, span_w=2, span_h=1, floor_id="f1", building_id="b1")
    coords = feature["geometry"]["coordinates"][0]
    assert coords[0] == [0.0, 0.0]
    assert coords[2] == [2.0, 1.0]
