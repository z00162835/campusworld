"""Tests for DomainRegistry dispatch and check_point -> domain ownership."""
from __future__ import annotations

import pytest

from app.game_engine.agent_runtime.policy import Domain, DomainRegistry


class _DummyDomain(Domain):
    def __init__(self, domain_id, check_points):
        self.domain_id = domain_id
        self.check_points = check_points


class TestDomainRegistry:
    def test_register_and_lookup(self):
        reg = DomainRegistry()
        d = _DummyDomain("alpha", ("cp_one",))
        reg.register(d)
        assert reg.domain_for("cp_one") is d
        assert reg.domain_for("unknown") is None

    def test_all_domains(self):
        reg = DomainRegistry()
        a = _DummyDomain("a", ("cp_a",))
        b = _DummyDomain("b", ("cp_b",))
        reg.register(a)
        reg.register(b)
        assert set(reg.all_domains()) == {a, b}

    def test_duplicate_domain_id_rejected(self):
        reg = DomainRegistry()
        reg.register(_DummyDomain("dup", ("cp_x",)))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_DummyDomain("dup", ("cp_y",)))

    def test_check_point_owned_by_two_domains_rejected(self):
        reg = DomainRegistry()
        reg.register(_DummyDomain("a", ("shared_cp",)))
        with pytest.raises(ValueError, match="already owned"):
            reg.register(_DummyDomain("b", ("shared_cp",)))

    def test_same_domain_id_different_instance_rejected(self):
        reg = DomainRegistry()
        reg.register(_DummyDomain("a", ("cp_a",)))
        # Re-registering a different instance with the same domain_id is an
        # error — each Domain instance must have a unique id.
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_DummyDomain("a", ("cp_a",)))

    def test_domain_without_id_rejected(self):
        reg = DomainRegistry()
        d = _DummyDomain("", ("cp",))
        with pytest.raises(ValueError, match="domain_id must be set"):
            reg.register(d)

    def test_default_engine_has_skill_gate_quality_domains(self):
        from app.game_engine.agent_runtime.policy import PolicyEngine

        engine = PolicyEngine()
        ids = {d.domain_id for d in engine.registry.all_domains()}
        assert ids == {"skill", "gate", "quality"}

    def test_default_engine_dispatches_before_tool_call_to_gate(self):
        from app.game_engine.agent_runtime.policy import PolicyContext, PolicyEngine
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        engine = PolicyEngine()
        domain = engine.registry.domain_for(CheckPoint.BEFORE_TOOL_CALL)
        assert domain is not None
        assert domain.domain_id == "gate"

    def test_default_engine_dispatches_before_skill_activation_to_skill(self):
        from app.game_engine.agent_runtime.policy import PolicyEngine
        from app.game_engine.agent_runtime.policy.check_points import CheckPoint

        engine = PolicyEngine()
        domain = engine.registry.domain_for(CheckPoint.BEFORE_SKILL_ACTIVATION)
        assert domain is not None
        assert domain.domain_id == "skill"

    def test_unregistered_check_point_returns_allow(self):
        from app.game_engine.agent_runtime.policy import PolicyContext, PolicyEngine

        engine = PolicyEngine(registry=DomainRegistry())
        ctx = PolicyContext(check_point="not_registered")
        decision = engine.evaluate(ctx)
        assert decision.is_allow is True
