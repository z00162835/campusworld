from __future__ import annotations

from contextlib import contextmanager

import pytest

from db import trait_migration_check


class _ScalarResult:
    def __init__(self, v):
        self._v = v

    def scalar(self):
        return self._v


class _FakeSession:
    def __init__(self):
        self.calls = 0

    def execute(self, *_args, **_kwargs):
        self.calls += 1
        # total_nodes, total_relationships, node_mismatch, rel_mismatch, mask_errors
        values = [10, 20, 0, 0, 0]
        return _ScalarResult(values[self.calls - 1])


@pytest.mark.unit
def test_run_trait_migration_checks_happy_path(monkeypatch):
    @contextmanager
    def _fake_ctx():
        yield _FakeSession()

    monkeypatch.setattr(trait_migration_check, "db_session_context", _fake_ctx)
    report = trait_migration_check.run_trait_migration_checks().to_dict()
    assert report["total_nodes"] == 10
    assert report["total_relationships"] == 20
    assert report["node_type_mismatch"] == 0
    assert report["relationship_type_mismatch"] == 0
    assert report["null_or_negative_masks"] == 0
