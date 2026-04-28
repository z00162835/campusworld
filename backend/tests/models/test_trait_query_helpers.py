from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.models.graph import Node, Relationship


@pytest.mark.unit
def test_node_filter_by_trait_any_mask_zero_noop():
    q = Mock()
    out = Node.filter_by_trait_any(q, 0)
    assert out is q
    q.filter.assert_not_called()


@pytest.mark.unit
def test_node_filter_by_trait_all_mask_zero_noop():
    q = Mock()
    out = Node.filter_by_trait_all(q, 0)
    assert out is q
    q.filter.assert_not_called()


@pytest.mark.unit
def test_relationship_filter_by_trait_any_mask_zero_noop():
    q = Mock()
    out = Relationship.filter_by_trait_any(q, 0)
    assert out is q
    q.filter.assert_not_called()


@pytest.mark.unit
def test_relationship_filter_by_trait_all_mask_zero_noop():
    q = Mock()
    out = Relationship.filter_by_trait_all(q, 0)
    assert out is q
    q.filter.assert_not_called()
