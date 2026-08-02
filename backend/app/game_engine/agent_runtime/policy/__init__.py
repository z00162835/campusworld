"""Agent Policy Engine — deterministic behaviour-plane check_points.

The PolicyEngine is a pure-function engine (no LLM, no DB) that evaluates
behavioural safety at check_points. Rules are registered per **domain**
(skill / gate / quality); see F16 §3.0 for the domain segmentation contract.
v1 implements ``before_tool_call`` (gate domain) and ``before_skill_activation``
(skill domain). ``after_tool_observation`` (audit-only) and ``before_final_answer``
(non-streaming Act path) are deferred. F18 quality-domain evaluators land in P1+.
"""
from app.game_engine.agent_runtime.policy.check_points import CheckPoint
from app.game_engine.agent_runtime.policy.config import PolicyConfig
from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.game_engine.agent_runtime.policy.domain import Domain, DomainRegistry
from app.game_engine.agent_runtime.policy.engine import PolicyEngine

__all__ = [
    "CheckPoint",
    "Domain",
    "DomainRegistry",
    "PolicyConfig",
    "PolicyContext",
    "PolicyDecision",
    "PolicyEngine",
]
