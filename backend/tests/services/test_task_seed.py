"""Phase B PR2: structural tests for default_v1 workflow + 3 seed pools.

Asserts the seed structures imported by ``ensure_task_system_seed`` are
consistent with docs/task/SPEC/features/F03 §2.3 and F05 §9 without requiring
a database.
"""

from __future__ import annotations

import re

import pytest

from db.seeds.task_seed import DEFAULT_WORKFLOW_SEED, SEED_TASK_POOLS


# ---------------------------------------------------------------------------
# default_v1 workflow shape (F03 §2.3)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_default_workflow_identity():
    assert DEFAULT_WORKFLOW_SEED["key"] == "default_v1"
    assert DEFAULT_WORKFLOW_SEED["version"] == 1
    assert DEFAULT_WORKFLOW_SEED["is_active"] is True


@pytest.mark.unit
def test_default_workflow_spec_schema_version():
    spec = DEFAULT_WORKFLOW_SEED["spec"]
    assert spec["_schema_version"] == 1


@pytest.mark.unit
def test_default_workflow_terminal_states():
    spec = DEFAULT_WORKFLOW_SEED["spec"]
    assert set(spec["terminal_states"]) == {"done", "cancelled", "failed"}


@pytest.mark.unit
def test_default_workflow_states_match_f03_table():
    expected_states = {
        "draft",
        "open",
        "claimed",
        "in_progress",
        "pending_review",
        "approved",
        "rejected",
        "failed",
        "done",
        "cancelled",
    }
    states = DEFAULT_WORKFLOW_SEED["spec"]["states"]
    assert set(states.keys()) == expected_states


@pytest.mark.unit
def test_default_workflow_phase_b_minimum_event_set_present():
    """Phase B MUST be able to drive these 5 events (SPEC §6 / ACCEPTANCE B.2)."""
    events = DEFAULT_WORKFLOW_SEED["spec"]["events"]
    for required in ("create", "publish", "claim", "assign", "complete"):
        assert required in events, f"workflow missing Phase B required event {required}"


@pytest.mark.unit
def test_default_workflow_phase_c_events_pre_provisioned():
    """Phase C events ship in the seed but transition() will gate them out (PR4)."""
    events = DEFAULT_WORKFLOW_SEED["spec"]["events"]
    for future in ("submit-review", "approve", "reject", "handoff", "fail", "cancel", "start"):
        assert future in events


@pytest.mark.unit
def test_default_workflow_event_targets_are_known_states():
    spec = DEFAULT_WORKFLOW_SEED["spec"]
    states = set(spec["states"].keys())
    for event_name, event_def in spec["events"].items():
        if event_name == "create":
            # Synthetic: from='__init__' produces draft. Skip from-states cross-check.
            continue
        assert event_def["to"] in states, f"event {event_name}.to not in declared states"
        for src in event_def["from"]:
            assert src in states, f"event {event_name}.from contains unknown state {src}"


@pytest.mark.unit
def test_default_workflow_required_role_present_for_each_event():
    events = DEFAULT_WORKFLOW_SEED["spec"]["events"]
    for name, defn in events.items():
        assert "required_role" in defn, f"event {name} missing required_role"


# ---------------------------------------------------------------------------
# Seed pools (F05 §9)
# ---------------------------------------------------------------------------


_KEY_FORMAT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$")


@pytest.mark.unit
def test_seed_pools_count_and_keys():
    keys = [p["key"] for p in SEED_TASK_POOLS]
    assert keys == ["hicampus.cleaning", "hicampus.security", "hicampus.maintenance"]


@pytest.mark.unit
def test_seed_pool_keys_match_chk_task_pools_key_format():
    for pool in SEED_TASK_POOLS:
        assert _KEY_FORMAT.match(pool["key"]), (
            f"pool key {pool['key']} violates chk_task_pools_key_format regex"
        )


@pytest.mark.unit
def test_seed_pools_default_workflow_ref_pin_to_default_v1():
    for pool in SEED_TASK_POOLS:
        ref = pool["default_workflow_ref"]
        assert ref["key"] == "default_v1"
        assert ref["version"] == 1
        assert ref["_schema_version"] == 1


@pytest.mark.unit
def test_seed_pools_visibility_in_canonical_enum():
    canonical = {"private", "explicit", "role_scope", "world_scope", "pool_open"}
    for pool in SEED_TASK_POOLS:
        assert pool["default_visibility"] in canonical


@pytest.mark.unit
def test_seed_pools_visibility_phase_b_supported_only():
    """Phase B (decision D2.3 + D4.1): seed pools MUST NOT default to
    ``role_scope`` or ``world_scope``; those visibility levels are deferred to
    Phase C alongside F11 data-access predicate evaluation."""
    from app.services.task.visibility import PHASE_B_SUPPORTED_VISIBILITIES

    for pool in SEED_TASK_POOLS:
        assert pool["default_visibility"] in PHASE_B_SUPPORTED_VISIBILITIES, (
            f"seed pool {pool['key']} declares default_visibility="
            f"{pool['default_visibility']!r} which is deferred to Phase C"
        )


@pytest.mark.unit
def test_seed_pools_acl_payloads_have_schema_version():
    for pool in SEED_TASK_POOLS:
        assert pool["publish_acl"].get("_schema_version") == 1
        assert pool["consume_acl"].get("_schema_version") == 1


@pytest.mark.unit
def test_seed_pools_publish_acl_allows_system_principal():
    """SPEC §1.4 OQ-28: `system` virtual principal must be able to publish."""
    for pool in SEED_TASK_POOLS:
        kinds = pool["publish_acl"].get("principal_kinds") or []
        assert "system" in kinds, (
            f"pool {pool['key']} publish_acl must include `system` for automation sources"
        )
