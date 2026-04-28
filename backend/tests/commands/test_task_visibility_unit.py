"""P0-functional unit tests for visibility constraints (Phase B).

Decisions implemented:

* D2.3 / D4.1 — ``role_scope`` and ``world_scope`` are deferred to Phase C.
  Both ``task create`` and ``task pool create/update`` MUST refuse them at
  write time with ``commands.task.error.visibility_unsupported``.
* D3.1 — ``task create --draft`` is parsed without raising; the actual draft
  behaviour is exercised by the dual-protocol contract test (DB-bound).
* The pure helpers in ``app.services.task.visibility`` are validated here
  without touching the database.
"""

from __future__ import annotations

import pytest

from app.commands.base import CommandContext
from app.services.task.visibility import (
    ALL_VISIBILITIES,
    PHASE_B_DEFERRED_VISIBILITIES,
    PHASE_B_SUPPORTED_VISIBILITIES,
    is_phase_b_supported,
)


def _ctx(*, permissions=None, roles=None, user_id="42") -> CommandContext:
    return CommandContext(
        user_id=user_id,
        username="probe",
        session_id="s",
        permissions=list(permissions or []),
        roles=list(roles or []),
        metadata={"locale": "en-US"},
    )


# ---------------------------------------------------------------------------
# Pure module: visibility constants & helper.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_phase_b_supported_visibilities_are_canonical_subset():
    canonical = {"private", "explicit", "role_scope", "world_scope", "pool_open"}
    assert PHASE_B_SUPPORTED_VISIBILITIES.issubset(canonical)
    assert PHASE_B_DEFERRED_VISIBILITIES.issubset(canonical)
    assert PHASE_B_SUPPORTED_VISIBILITIES | PHASE_B_DEFERRED_VISIBILITIES == canonical
    assert PHASE_B_SUPPORTED_VISIBILITIES.isdisjoint(PHASE_B_DEFERRED_VISIBILITIES)


@pytest.mark.unit
def test_all_visibilities_constant_matches_union():
    assert ALL_VISIBILITIES == (
        PHASE_B_SUPPORTED_VISIBILITIES | PHASE_B_DEFERRED_VISIBILITIES
    )


@pytest.mark.unit
@pytest.mark.parametrize("v", ["private", "explicit", "pool_open"])
def test_is_phase_b_supported_returns_true_for_supported(v: str):
    assert is_phase_b_supported(v) is True


@pytest.mark.unit
@pytest.mark.parametrize("v", ["role_scope", "world_scope", "bogus", "", "PRIVATE"])
def test_is_phase_b_supported_returns_false_for_deferred_or_unknown(v: str):
    assert is_phase_b_supported(v) is False


# ---------------------------------------------------------------------------
# task create — write-time visibility rejection (no DB needed when no --to-pool).
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["role_scope", "world_scope", "bogus"])
def test_task_create_rejects_phase_b_unsupported_visibility(bad: str):
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(permissions=["task.create"]),
        ["create", "--title", "x", "--visibility", bad],
    )
    assert res.success is False
    assert res.error == "commands.task.error.visibility_unsupported"


# ---------------------------------------------------------------------------
# task pool create / update — same rejection at the admin write boundary.
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["role_scope", "world_scope", "bogus"])
def test_task_pool_create_rejects_unsupported_visibility(bad: str):
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(permissions=["task.pool.admin", "task.read"]),
        [
            "pool", "create", "hicampus.unit_test",
            "--display-name", "Unit Test",
            "--visibility", bad,
        ],
    )
    assert res.success is False
    assert res.error == "commands.task.error.visibility_unsupported"


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["role_scope", "world_scope"])
def test_task_pool_update_rejects_unsupported_visibility(bad: str):
    from app.commands.game.task.task_command import TaskCommand

    cmd = TaskCommand()
    res = cmd.execute(
        _ctx(permissions=["task.pool.admin", "task.read"]),
        ["pool", "update", "hicampus.cleaning", "--visibility", bad],
    )
    assert res.success is False
    assert res.error == "commands.task.error.visibility_unsupported"


# ---------------------------------------------------------------------------
# Argv parsing: --draft is registered as a bool flag.
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_task_create_draft_bool_flag_parsed():
    """D3.1: ``--draft`` is a recognised bool flag and does not consume the
    next positional. Behaviour (only-create-no-publish) is verified in the
    DB-bound contract test."""
    from app.commands.game.task._helpers import parse_argv
    from app.commands.game.task.task_command import _CREATE_BOOL_FLAGS

    assert "draft" in _CREATE_BOOL_FLAGS
    parsed = parse_argv(
        ["create", "--title", "x", "--to-pool", "p", "--draft"],
        bool_flags=_CREATE_BOOL_FLAGS,
    )
    assert "draft" in parsed.bools
    assert parsed.flags.get("title") == "x"
    assert parsed.flags.get("to-pool") == "p"
