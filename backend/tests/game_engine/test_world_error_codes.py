"""WorldErrorCode: graph-seed-related members must exist (regression guard)."""

import pytest

from app.game_engine.runtime_store import WorldErrorCode


@pytest.mark.game
@pytest.mark.unit
def test_graph_seed_error_codes_exist():
    assert WorldErrorCode.GRAPH_SEED_REFERENCE_BROKEN.value == "GRAPH_SEED_REFERENCE_BROKEN"
    assert WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN.value == "GRAPH_SEED_TYPE_UNKNOWN"
    assert WorldErrorCode.GRAPH_SEED_RELATIONSHIP_UNSUPPORTED.value == "GRAPH_SEED_RELATIONSHIP_UNSUPPORTED"
    assert WorldErrorCode.GRAPH_SEED_FAILED.value == "GRAPH_SEED_FAILED"


@pytest.mark.game
@pytest.mark.unit
def test_world_error_code_from_graph_seed_string():
    assert WorldErrorCode("GRAPH_SEED_TYPE_UNKNOWN") is WorldErrorCode.GRAPH_SEED_TYPE_UNKNOWN
