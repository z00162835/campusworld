"""
World management command family.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.commands.base import AdminCommand, CommandContext, CommandResult
from app.core.permissions import permission_checker
from app.game_engine.manager import game_engine_manager
from app.game_engine.topology_service import world_topology_service
from app.game_engine.world_entry_service import world_entry_service


class WorldCommand(AdminCommand):
    """Admin world operations: list/install/uninstall/reload/status/validate/repair."""

    _SUB_PERM: Dict[str, str] = {
        "list": "admin.world.read",
        "status": "admin.world.read",
        "install": "admin.world.manage",
        "uninstall": "admin.world.manage",
        "reload": "admin.world.manage",
        "validate": "admin.world.maintain",
        "repair": "admin.world.maintain",
    }

    def __init__(self):
        super().__init__(
            name="world",
            description="世界包管理（list/install/uninstall/reload/status/validate/repair）",
            aliases=["worlds"],
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result(self.get_usage())
        action = str(args[0]).lower().strip()
        if action not in self._SUB_PERM:
            return CommandResult.error_result(f"未知 world 子命令: {action}")
        if not self._has_sub_permission(context, action):
            return CommandResult.error_result(
                f"Permission denied for world {action}",
                error="WORLD_FORBIDDEN",
            )
        if action == "list":
            return self._list_worlds(context)
        if action == "status":
            return self._status(context, args[1:])
        if action == "install":
            return self._install(context, args[1:])
        if action == "uninstall":
            return self._uninstall(context, args[1:])
        if action == "reload":
            return self._reload(context, args[1:])
        if action == "validate":
            return self._validate(context, args[1:])
        return self._repair(context, args[1:])

    def get_usage(self) -> str:
        return (
            "用法: world <list|install|uninstall|reload|status|validate|repair> [world_id] "
            "[--dry-run] [--force]"
        )

    def _has_sub_permission(self, context: CommandContext, action: str) -> bool:
        required = self._SUB_PERM.get(action, "admin.world.*")
        return permission_checker.check_permission(list(context.permissions or []), required)

    def _resolve_world_path(self, world_id: str) -> Dict[str, Optional[str]]:
        engine = game_engine_manager.get_engine()
        if not engine or not getattr(engine, "loader", None):
            return {"resolved_path": None, "source_type": None}
        loader = engine.loader
        for p in loader.search_paths:
            candidate = Path(p) / world_id
            if candidate.exists() and candidate.is_dir():
                s = str(candidate)
                if "/backend/app/games/" in s:
                    source = "builtin"
                elif "/games/" in s:
                    source = "external"
                else:
                    source = "custom"
                return {"resolved_path": s, "source_type": source}
        return {"resolved_path": None, "source_type": None}

    def _list_worlds(self, context: CommandContext) -> CommandResult:
        available = game_engine_manager.list_games()
        loaded = set()
        engine = game_engine_manager.get_engine()
        if engine and getattr(engine, "loader", None):
            loaded = set(engine.loader.get_loaded_games())
        rows = []
        for wid in available:
            where = self._resolve_world_path(wid)
            rows.append(
                {
                    "world_id": wid,
                    "loaded": wid in loaded,
                    "resolved_path": where["resolved_path"],
                    "source_type": where["source_type"],
                }
            )
        self.logger.info("AUDIT world.list operator=%s count=%s", context.username, len(rows))
        return CommandResult.success_result(
            f"world list ok, total={len(rows)}",
            data={"items": rows, "total": len(rows)},
            command_type=self.command_type,
        )

    def _status(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world status <world_id>")
        world_id = str(args[0]).strip()
        info = game_engine_manager.get_game_status(world_id) or {}
        runtime = {}
        engine = game_engine_manager.get_engine()
        if engine and getattr(engine, "loader", None):
            runtime = engine.loader.get_runtime_state(world_id) or {}
        where = self._resolve_world_path(world_id)
        payload = {
            "world_id": world_id,
            "game_info": info,
            "runtime_state": runtime,
            **where,
        }
        self.logger.info("AUDIT world.status operator=%s world_id=%s", context.username, world_id)
        return CommandResult.success_result(
            f"world status ok: {world_id}",
            data=payload,
            command_type=self.command_type,
        )

    def _install(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world install <world_id>")
        world_id = str(args[0]).strip()
        out = game_engine_manager.load_game(world_id)
        self.logger.info(
            "AUDIT world.install operator=%s world_id=%s result=%s error_code=%s",
            context.username,
            world_id,
            out.get("ok"),
            out.get("error_code"),
        )
        if out.get("ok"):
            world_entry_service.sync_world_entry_visibility(world_id, enabled=True)
        return self._from_world_result("world install", world_id, out)

    def _uninstall(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world uninstall <world_id>")
        world_id = str(args[0]).strip()
        out = game_engine_manager.unload_game(world_id)
        self.logger.info(
            "AUDIT world.uninstall operator=%s world_id=%s result=%s error_code=%s",
            context.username,
            world_id,
            out.get("ok"),
            out.get("error_code"),
        )
        if out.get("ok"):
            world_entry_service.sync_world_entry_visibility(world_id, enabled=False)
        return self._from_world_result("world uninstall", world_id, out)

    def _reload(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world reload <world_id>")
        world_id = str(args[0]).strip()
        out = game_engine_manager.reload_game(world_id)
        self.logger.info(
            "AUDIT world.reload operator=%s world_id=%s result=%s error_code=%s",
            context.username,
            world_id,
            out.get("ok"),
            out.get("error_code"),
        )
        if out.get("ok"):
            world_entry_service.sync_world_entry_visibility(world_id, enabled=True)
        return self._from_world_result("world reload", world_id, out)

    def _validate(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world validate <world_id> [--dry-run]")
        world_id = str(args[0]).strip()
        dry_run = "--dry-run" in args[1:]
        report = world_topology_service.validate_topology(world_id)
        self.logger.info(
            "AUDIT world.validate operator=%s world_id=%s dry_run=%s issues=%s",
            context.username,
            world_id,
            dry_run,
            report.get("issue_count", 0),
        )
        msg = (
            f"world validate passed: {world_id}"
            if report.get("ok")
            else f"world validate found issues: {report.get('issue_count', 0)}"
        )
        payload = {"world_id": world_id, "dry_run": dry_run, "report": report}
        if report.get("ok"):
            return CommandResult.success_result(msg, data=payload, command_type=self.command_type)
        return CommandResult(
            success=False,
            message=msg,
            data=payload,
            error="WORLD_TOPOLOGY_INVALID",
            command_type=self.command_type,
        )

    def _repair(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world repair <world_id> [--dry-run] [--force]")
        world_id = str(args[0]).strip()
        dry_run = "--dry-run" in args[1:]
        force = "--force" in args[1:]
        report = world_topology_service.repair_topology(world_id, dry_run=dry_run, force=force)
        self.logger.info(
            "AUDIT world.repair operator=%s world_id=%s dry_run=%s force=%s planned=%s applied=%s",
            context.username,
            world_id,
            dry_run,
            force,
            len(report.get("planned_actions", [])),
            len(report.get("applied_actions", [])),
        )
        msg = (
            f"world repair dry-run ready: planned={len(report.get('planned_actions', []))}"
            if dry_run
            else f"world repair done: applied={len(report.get('applied_actions', []))}"
        )
        payload = {"world_id": world_id, "dry_run": dry_run, "force": force, "report": report}
        if report.get("ok"):
            return CommandResult.success_result(msg, data=payload, command_type=self.command_type)
        return CommandResult(
            success=False,
            message=msg,
            data=payload,
            error="WORLD_REPAIR_INCOMPLETE",
            command_type=self.command_type,
        )

    def _from_world_result(self, action: str, world_id: str, out: Dict[str, Any]) -> CommandResult:
        ok = bool(out.get("ok"))
        msg = str(out.get("message") or f"{action} {'ok' if ok else 'failed'}: {world_id}")
        payload = dict(out)
        payload.update(self._resolve_world_path(world_id))
        if ok:
            return CommandResult.success_result(msg, data=payload, command_type=self.command_type)
        return CommandResult(
            success=False,
            message=msg,
            data=payload,
            error=str(out.get("error_code") or ""),
            command_type=self.command_type,
        )

