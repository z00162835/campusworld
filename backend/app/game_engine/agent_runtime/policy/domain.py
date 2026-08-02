"""Domain segmentation for the PolicyEngine.

The PolicyEngine is a single evaluator, but its rules are registered per
**domain**. Each domain owns an orthogonal decision surface, its own rule
definitions, config namespace, and a subset of check_points. One check_point
belongs to exactly one domain; detectors/evaluators read only their own
domain's ``PolicyContext`` fields.

v1 ships three domains: ``skill`` (F15/F16), ``gate`` (F16), ``quality``
(F18). See F16 §3.0 for the boundary invariants.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from app.game_engine.agent_runtime.policy.context import PolicyContext
from app.game_engine.agent_runtime.policy.decisions import PolicyDecision

Detector = Callable[[PolicyContext], Optional[PolicyDecision]]
Evaluator = Callable[[PolicyContext], Optional[PolicyDecision]]


class Domain:
    """Base class for a policy domain.

    Subclasses set ``domain_id`` and ``check_points`` and implement
    ``detectors()`` (skill/gate) or ``evaluators()`` (quality). ``build_context``
    fills this domain's semantic fields on a domain-agnostic ``base`` context
    built by the driver (data sourced from ``base.extra['tick_state']``).
    """

    domain_id: str = ""
    check_points: Tuple[str, ...] = ()

    def detectors(self) -> List[Detector]:
        return []

    def evaluators(self) -> List[Evaluator]:
        return []

    def build_context(self, base: PolicyContext) -> PolicyContext:
        return base


class DomainRegistry:
    """Maps check_points to their owning domain.

    Registered once at startup; ``PolicyEngine`` holds a registry and dispatches
    ``evaluate`` by ``check_point -> domain``. A check_point may belong to at
    most one domain.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, Domain] = {}
        self._by_check_point: Dict[str, str] = {}

    def register(self, domain: Domain) -> None:
        if not domain.domain_id:
            raise ValueError("Domain.domain_id must be set")
        if domain.domain_id in self._by_id:
            raise ValueError(f"Domain already registered: {domain.domain_id}")
        self._by_id[domain.domain_id] = domain
        for cp in domain.check_points:
            if cp in self._by_check_point and self._by_check_point[cp] != domain.domain_id:
                raise ValueError(
                    f"check_point {cp!r} already owned by domain "
                    f"{self._by_check_point[cp]!r}; cannot also belong to "
                    f"{domain.domain_id!r}"
                )
            self._by_check_point[cp] = domain.domain_id

    def domain_for(self, check_point: str) -> Optional[Domain]:
        domain_id = self._by_check_point.get(check_point)
        if domain_id is None:
            return None
        return self._by_id[domain_id]

    def all_domains(self) -> Tuple[Domain, ...]:
        return tuple(self._by_id.values())
