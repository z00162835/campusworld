from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional, Type

if TYPE_CHECKING:
    from app.game_engine.agent_runtime.worker import AgentWorker
else:
    AgentWorker = Any


class AgentWorkerRegistry:
    """
    Maps node_types.typeclass (Python path) to a factory.

    Default unregistered paths fall back to SysSampleWorker for `NpcAgent`.
    """

    def __init__(self) -> None:
        self._by_typeclass: Dict[str, Type[AgentWorker]] = {}

    def register(self, typeclass: str, worker_cls: Type[AgentWorker]) -> None:
        self._by_typeclass[typeclass] = worker_cls

    def get(self, typeclass: str) -> Optional[Type[AgentWorker]]:
        return self._by_typeclass.get(typeclass)


default_worker_registry = AgentWorkerRegistry()


def get_worker_for_typeclass(typeclass: str) -> Type[AgentWorker]:
    from app.game_engine.agent_runtime.worker import SysSampleWorker

    # app.models.things.agents.NpcAgent — default sample worker
    if "NpcAgent" in typeclass or typeclass.endswith("agents.NpcAgent"):
        return SysSampleWorker
    w = default_worker_registry.get(typeclass)
    if w is not None:
        return w
    return SysSampleWorker
