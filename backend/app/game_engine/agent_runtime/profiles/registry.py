"""Runtime profile registry for npc_agent NLP ticks."""
from __future__ import annotations

from app.game_engine.agent_runtime.profiles.base import AgentRuntimeProfile, NoopAgentRuntimeProfile


def _build_aico_profile() -> AgentRuntimeProfile:
    from app.game_engine.agent_runtime.aico.profile import AicoRuntimeProfile
    return AicoRuntimeProfile()


_PROFILE_FACTORIES = {
    'aico': _build_aico_profile,
}


def resolve_agent_runtime_profile(service_id: str) -> AgentRuntimeProfile:
    factory = _PROFILE_FACTORIES.get(str(service_id or '').strip().lower())
    if factory is not None:
        return factory()
    return NoopAgentRuntimeProfile()
