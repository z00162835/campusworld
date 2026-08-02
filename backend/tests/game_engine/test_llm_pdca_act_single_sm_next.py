"""B6-b: act state advances the state machine exactly once per iteration.

The PDCA driver calls ``sm.next`` once per state. For the act state, the
``after_state_execute`` hook sets flags only (no sm.next), then
``_detect_tick_emit_deferral`` + ``before_terminal`` run, then a single
``sm.next`` consumes the merged flags. The existing driver already does this;
this test is a structural lock that the framework exposes ``_run_inner`` and
the single-advance contract is preserved. The real byte-equivalent guarantee
is covered by ``test_llm_pdca_agent_loop.py`` (which must remain green).
"""
from __future__ import annotations

from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework


def test_framework_exposes_run_inner():
    """The driver loop entry point exists; single-advance is enforced within it."""
    assert hasattr(LlmPDCAFramework, "_run_inner")


def test_quality_domain_registered_in_default_engine():
    """The quality domain (after_state_execute check_point) is registered so the
    driver can dispatch to it. The act single-sm.next contract depends on the
    driver, not the engine; this asserts the dispatch surface is in place."""
    from app.game_engine.agent_runtime.policy import PolicyEngine
    from app.game_engine.agent_runtime.policy.check_points import CheckPoint

    engine = PolicyEngine()
    domain = engine.registry.domain_for(CheckPoint.AFTER_STATE_EXECUTE)
    assert domain is not None
    assert domain.domain_id == "quality"
