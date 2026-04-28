"""Phase B PR3: task pool ACL evaluator (F05 §4)."""

from __future__ import annotations

import pytest

from app.services.task.acl import AclDecision, evaluate_acl
from app.services.task.permissions import Principal, SYSTEM_PRINCIPAL


@pytest.mark.unit
def test_none_acl_short_circuits_to_allow():
    actor = Principal(id=1, kind="user")
    decision = evaluate_acl(actor, None)
    assert decision.allow
    assert isinstance(decision, AclDecision)


@pytest.mark.unit
def test_explicit_principal_id_whitelist_grants_access():
    actor = Principal(id=42, kind="user")
    acl = {
        "_schema_version": 1,
        "principals": [42, 7],
        "default": "deny",
    }
    assert evaluate_acl(actor, acl).allow


@pytest.mark.unit
def test_principal_kinds_only_admits_listed_kinds():
    user = Principal(id=1, kind="user")
    agent = Principal(id=2, kind="agent")
    acl = {"_schema_version": 1, "principal_kinds": ["agent"], "default": "deny"}
    assert not evaluate_acl(user, acl).allow
    assert evaluate_acl(agent, acl).allow


@pytest.mark.unit
def test_kind_plus_role_intersection_grants_access():
    actor = Principal(id=1, kind="user", roles=frozenset({"facility_manager"}))
    acl = {
        "_schema_version": 1,
        "principal_kinds": ["user"],
        "roles": ["facility_manager", "admin"],
        "default": "deny",
    }
    assert evaluate_acl(actor, acl).allow


@pytest.mark.unit
def test_kind_plus_role_without_intersection_denies():
    actor = Principal(id=1, kind="user", roles=frozenset({"unrelated"}))
    acl = {
        "_schema_version": 1,
        "principal_kinds": ["user"],
        "roles": ["facility_manager"],
        "default": "deny",
    }
    decision = evaluate_acl(actor, acl)
    assert not decision.allow
    assert decision.reason == "denied.default_deny"


@pytest.mark.unit
def test_kind_plus_groups_intersection_grants_access():
    actor = Principal(id=1, kind="group", group_tags=frozenset({"facility"}))
    acl = {
        "_schema_version": 1,
        "principal_kinds": ["group"],
        "groups": ["facility", "ops"],
        "default": "deny",
    }
    assert evaluate_acl(actor, acl).allow


@pytest.mark.unit
def test_data_access_predicate_without_evaluator_denies():
    actor = Principal(id=1, kind="user")
    acl = {
        "_schema_version": 1,
        "principal_kinds": ["user"],
        "data_access_predicate": {"scope_anchor_in_world": "hicampus"},
        "default": "deny",
    }
    decision = evaluate_acl(actor, acl)
    assert not decision.allow
    assert decision.reason == "data_access_predicate.no_evaluator"


@pytest.mark.unit
def test_data_access_predicate_with_evaluator_allows_when_true():
    actor = Principal(id=1, kind="user")
    acl = {
        "_schema_version": 1,
        "principal_kinds": ["user"],
        "data_access_predicate": {"scope_anchor_in_world": "hicampus"},
        "default": "deny",
    }
    decision = evaluate_acl(actor, acl, f11_evaluate=lambda a, p: True)
    assert decision.allow
    assert decision.reason == "matched.data_access_predicate"


@pytest.mark.unit
def test_default_allow_falls_through_when_no_clauses_match():
    actor = Principal(id=1, kind="user")
    acl = {"_schema_version": 1, "principal_kinds": ["agent"], "default": "allow"}
    # kind mismatch + default allow → still allowed
    assert evaluate_acl(actor, acl).allow


@pytest.mark.unit
def test_default_deny_when_no_clauses_match_and_no_default_specified():
    actor = Principal(id=1, kind="user")
    acl = {"_schema_version": 1, "principal_kinds": ["agent"]}
    # default missing → "deny" per evaluator
    assert not evaluate_acl(actor, acl).allow


@pytest.mark.unit
def test_system_principal_allowed_when_kinds_include_system():
    """SPEC §1.4 末段：publish_acl.principal_kinds 含 'system' 时允许."""
    acl = {
        "_schema_version": 1,
        "principal_kinds": ["user", "agent", "system"],
        "default": "deny",
    }
    decision = evaluate_acl(SYSTEM_PRINCIPAL, acl)
    assert decision.allow
    assert decision.reason == "matched.principal_kinds"


@pytest.mark.unit
def test_system_principal_denied_when_kinds_exclude_system():
    acl = {"_schema_version": 1, "principal_kinds": ["user"], "default": "deny"}
    assert not evaluate_acl(SYSTEM_PRINCIPAL, acl).allow


@pytest.mark.unit
def test_invalid_acl_shape_denies_silently():
    actor = Principal(id=1, kind="user")
    decision = evaluate_acl(actor, "not-a-dict")  # type: ignore[arg-type]
    assert not decision.allow
    assert decision.reason == "acl.schema_invalid"


@pytest.mark.unit
def test_seed_pool_acls_accept_admin_roles():
    """Sanity: the canned ACL shape from db/seeds/task_seed.py must allow regular users."""
    from db.seeds.task_seed import SEED_TASK_POOLS

    actor = Principal(id=1, kind="user")
    for pool in SEED_TASK_POOLS:
        assert evaluate_acl(actor, pool["publish_acl"]).allow, pool["key"]
        assert evaluate_acl(actor, pool["consume_acl"]).allow, pool["key"]


@pytest.mark.unit
def test_seed_pool_publish_acls_admit_system_principal():
    from db.seeds.task_seed import SEED_TASK_POOLS

    for pool in SEED_TASK_POOLS:
        assert evaluate_acl(SYSTEM_PRINCIPAL, pool["publish_acl"]).allow, pool["key"]
