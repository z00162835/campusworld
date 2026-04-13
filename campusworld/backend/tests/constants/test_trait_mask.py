"""Unit tests: trait_mask constants match documented composites."""

from __future__ import annotations

import pytest

from app.constants import trait_mask as M


@pytest.mark.unit
def test_single_bits_match_shifts():
    assert M.CONCEPTUAL == 1
    assert M.FACTUAL == 2
    assert M.SPATIAL == 4
    assert M.PERCEPTUAL == 8
    assert M.TEMPORAL == 16
    assert M.CONTROLLABLE == 32
    assert M.EVENT_BASED == 64
    assert M.MOBILE == 128
    assert M.AUTO == 256
    assert M.LOAD_BEARING == 512


@pytest.mark.unit
def test_documented_composites_from_f01():
    assert M.SPATIAL_LOAD_BEARING == 516
    assert M.DEVICE_TYPICAL_IOT_END == 58
    assert M.ACCESS_TERMINAL == 126
    assert M.WORLD_OBJECT_BASE == 520
    assert M.NPC_AGENT == 498
    assert M.LOGICAL_ZONE == 65
    assert M.WORLD_ENTRANCE == 101
    assert M.LOCATION_RELATIONSHIP_EDGE == 5
