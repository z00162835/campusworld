"""
Directional movement command for world-internal navigation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.commands.base import CommandContext, CommandResult, GameCommand
from app.core.database import db_session_context
from app.game_engine.direction_util import normalize_direction
from app.game_engine.subgraph_boundary import bridge_enabled, is_authorized_cross_world_bridge
from app.models.graph import Node, Relationship


class MovementCommand(GameCommand):
    def __init__(self):
        super().__init__(
            name="go",
            description="按方向移动（n/s/e/w/ne/nw/se/sw/up/down/in/out）",
            aliases=["walk"],
            game_name="",
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        try:
            direction = self._resolve_input_direction(args)
            if not direction:
                return CommandResult.error_result("用法: go <direction>")
            self.logger.info(
                "AUDIT world.move.attempt operator=%s direction=%s",
                context.username,
                direction,
            )
            ok, msg, err = self._move(str(context.user_id), direction)
            if ok:
                self.logger.info(
                    "AUDIT world.move.success operator=%s direction=%s",
                    context.username,
                    direction,
                )
                return CommandResult.success_result(msg)
            self.logger.info(
                "AUDIT world.move.fail operator=%s direction=%s reason=%s",
                context.username,
                direction,
                msg,
            )
            return CommandResult.error_result(msg, error=err)
        except Exception as e:
            return CommandResult.error_result(f"移动失败: {e}")

    def _resolve_input_direction(self, args: List[str]) -> Optional[str]:
        if self.name != "go":
            return None
        if args:
            return normalize_direction(args[0])
        return None

    def _move(self, user_id: str, direction: str) -> Tuple[bool, str, Optional[str]]:
        with db_session_context() as session:
            user = (
                session.query(Node)
                .filter(Node.id == user_id, Node.type_code == "account", Node.is_active == True)  # noqa: E712
                .first()
            )
            if not user:
                return False, "用户不存在", None
            attrs: Dict[str, Any] = dict(user.attributes or {})
            world_id = str(attrs.get("active_world") or "").strip().lower()
            room_pkg_id = str(attrs.get("world_location") or "").strip().lower()
            if not world_id or not room_pkg_id:
                return False, "你当前不在世界内", None

            room = (
                session.query(Node)
                .filter(
                    Node.type_code == "room",
                    Node.attributes["world_id"].astext == world_id,
                    Node.attributes["package_node_id"].astext == room_pkg_id,
                    Node.is_active == True,  # noqa: E712
                )
                .first()
            )
            if not room:
                return False, "当前位置无效", None

            candidates = (
                session.query(Relationship, Node)
                .join(Node, Relationship.target_id == Node.id)
                .filter(
                    Relationship.source_id == room.id,
                    Relationship.type_code == "connects_to",
                    Relationship.is_active == True,  # noqa: E712
                    Node.attributes["world_id"].astext == world_id,
                    Node.is_active == True,  # noqa: E712
                )
                .all()
            )
            available_dirs: List[str] = []
            target = None
            for rel, node in candidates:
                rel_attrs = dict(rel.attributes or {})
                rel_dir = normalize_direction(str(rel_attrs.get("direction") or ""))
                if rel_dir:
                    available_dirs.append(rel_dir)
                if rel_dir == normalize_direction(direction):
                    target = node
                    break
            if not target:
                bridge_candidates = (
                    session.query(Relationship, Node)
                    .join(Node, Relationship.target_id == Node.id)
                    .filter(
                        Relationship.source_id == room.id,
                        Relationship.type_code == "connects_to",
                        Relationship.is_active == True,  # noqa: E712
                        Node.is_active == True,  # noqa: E712
                    )
                    .all()
                )
                dir_norm = normalize_direction(direction)
                for rel, node in bridge_candidates:
                    if not is_authorized_cross_world_bridge(rel):
                        continue
                    rel_attrs = dict(rel.attributes or {})
                    rel_dir = normalize_direction(str(rel_attrs.get("direction") or ""))
                    if rel_dir:
                        available_dirs.append(rel_dir)
                    if rel_dir != dir_norm:
                        continue
                    if not bridge_enabled(rel):
                        return False, "该方向的跨世界桥接已关闭", "WORLD_BRIDGE_DISABLED"
                    tw = str((node.attributes or {}).get("world_id") or "").strip().lower()
                    if tw == world_id:
                        continue
                    target = node
                    attrs["active_world"] = tw
                    break

            if not target:
                if available_dirs:
                    return (
                        False,
                        f"无法向 {direction} 移动，可用方向: {', '.join(sorted(set(available_dirs)))}",
                        None,
                    )
                return False, "该方向目标不可达", None

            target_pkg_id = str((target.attributes or {}).get("package_node_id") or "")
            attrs["world_location"] = target_pkg_id
            attrs["last_world_location"] = target_pkg_id
            user.attributes = attrs
            session.add(user)
            session.commit()
            target_name = str((target.attributes or {}).get("display_name") or target.name or target_pkg_id)
            tw_final = str((target.attributes or {}).get("world_id") or "").strip().lower()
            if tw_final and tw_final != world_id:
                return (
                    True,
                    f"你通过跨世界连接向 {normalize_direction(direction)} 移动，来到 {target_name}（{tw_final}）",
                    None,
                )
            return True, f"你向 {normalize_direction(direction)} 移动，来到 {target_name}", None


class FixedDirectionCommand(MovementCommand):
    def __init__(self, *, name: str, description: str, aliases: Optional[List[str]] = None, direction: str):
        super().__init__()
        self.name = name
        self.description = description
        self.aliases = list(aliases or [])
        self._fixed_direction = normalize_direction(direction)

    def _resolve_input_direction(self, args: List[str]) -> Optional[str]:
        return self._fixed_direction


def build_direction_commands() -> List[GameCommand]:
    return [
        MovementCommand(),
        FixedDirectionCommand(name="north", aliases=["n"], description="向北移动", direction="north"),
        FixedDirectionCommand(name="south", aliases=["s"], description="向南移动", direction="south"),
        FixedDirectionCommand(name="east", aliases=["e"], description="向东移动", direction="east"),
        FixedDirectionCommand(name="west", aliases=["w"], description="向西移动", direction="west"),
        FixedDirectionCommand(name="northeast", aliases=["ne"], description="向东北移动", direction="northeast"),
        FixedDirectionCommand(name="northwest", aliases=["nw"], description="向西北移动", direction="northwest"),
        FixedDirectionCommand(name="southeast", aliases=["se"], description="向东南移动", direction="southeast"),
        FixedDirectionCommand(name="southwest", aliases=["sw"], description="向西南移动", direction="southwest"),
        FixedDirectionCommand(name="up", aliases=["u"], description="向上移动", direction="up"),
        FixedDirectionCommand(name="down", aliases=["d"], description="向下移动", direction="down"),
        FixedDirectionCommand(name="in", aliases=[], description="向内移动", direction="enter"),
        FixedDirectionCommand(name="out", aliases=["o"], description="向外移动", direction="out"),
    ]

