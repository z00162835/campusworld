"""
SSH post-auth entry routing.

Decides whether a user should stay in Singularity Room or enter a world.
"""

from dataclasses import dataclass
from typing import Optional, Any, Dict

from app.core.log import get_logger, LoggerNames
from app.game_engine.manager import game_engine_manager


@dataclass
class RouteDecision:
    target_kind: str
    reason: str
    world_name: Optional[str] = None
    world_spawn_key: Optional[str] = None


class EntryRouter:
    """Routes post-auth destination based on persisted user attributes."""

    def __init__(self):
        self.logger = get_logger(LoggerNames.GAME)

    def resolve_post_auth_destination(self, user_node: Any) -> RouteDecision:
        attrs: Dict[str, Any] = user_node.attributes or {}
        active_world = attrs.get("active_world")
        last_world_location = attrs.get("last_world_location")

        if not active_world:
            return RouteDecision(
                target_kind="singularity",
                reason="no_active_world",
            )

        if not self._is_world_available(active_world):
            self.logger.warning(
                f"世界不可用，降级到奇点屋: {active_world}",
                extra={"event_type": "entry_route_world_unavailable", "world": active_world},
            )
            return RouteDecision(
                target_kind="singularity",
                reason="world_unavailable",
            )

        return RouteDecision(
            target_kind="world",
            reason="resume_active_world",
            world_name=active_world,
            world_spawn_key=last_world_location or "campus",
        )

    def _is_world_available(self, world_name: str) -> bool:
        engine = game_engine_manager.get_engine()
        if not engine:
            return False
        return engine.get_game(world_name) is not None

