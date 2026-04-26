"""
World management command family.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from app.commands.base import AdminCommand, CommandContext, CommandResult
from app.core.database import db_session_context
from app.core.permissions import permission_checker
from app.game_engine.manager import game_engine_manager
from app.game_engine.topology_service import world_topology_service
from app.game_engine.world_bridge_service import (
    WORLD_BRIDGE_INVALID_ARGUMENT,
    WORLD_BRIDGE_PERMISSION_DENIED,
    world_bridge_service,
)
from app.game_engine.world_entry_service import world_entry_service
from app.games.hicampus.package.content_overlay import (
    apply_spatial_content_overlay,
    content_validate_report,
    diff_spatial_vs_db,
)
from app.games.hicampus.package.contracts import DataPackageError


def _read_manifest_brief(game_root: Path) -> Dict[str, Any]:
    """Light read of manifest.yaml for list / resolve (no full package load)."""
    out: Dict[str, Any] = {"display_name": None, "version": None, "api_version": None}
    mf = game_root / "manifest.yaml"
    if not mf.is_file():
        return out
    try:
        raw = mf.read_text(encoding="utf-8")
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            return out
        out["display_name"] = data.get("display_name") or data.get("title")
        out["version"] = data.get("version")
        out["api_version"] = data.get("api_version")
    except Exception:
        pass
    return out


def _format_world_list_message(rows: List[Dict[str, Any]]) -> str:
    """Multi-line table for SSH and other handlers that only show result.message."""
    if not rows:
        return (
            "world list: no packages found under game search paths.\n"
            "Expected layout: .../games/<world_id>/manifest.yaml"
        )
    lines = [
        f"{'world_id':<16} {'display_name':<26} {'loaded':<6} {'version':<8} {'api':<6} source",
        "-" * 90,
    ]
    for r in rows:
        wid = str(r.get("world_id", ""))[:16]
        dn = str(r.get("display_name") or "-")[:26]
        ld = "yes" if r.get("loaded") else "no"
        ver = str(r.get("version") or "-")[:8]
        api = str(r.get("api_version") or "-")[:6]
        src = str(r.get("source_type") or "-")[:10]
        lines.append(f"{wid:<16} {dn:<26} {ld:<6} {ver:<8} {api:<6} {src}")
    lines.append("")
    lines.append(f"(total={len(rows)})  Canonical install key is world_id (package directory).")
    lines.append("Example: world install <world_id>")
    return "\n".join(lines)


class WorldCommand(AdminCommand):
    """Admin world operations: list/install/uninstall/reload/status/validate/repair, and bridge subcommands."""

    _SUB_PERM: Dict[str, str] = {
        "list": "admin.world.read",
        "status": "admin.world.read",
        "install": "admin.world.manage",
        "uninstall": "admin.world.manage",
        "reload": "admin.world.manage",
        "validate": "admin.world.maintain",
        "repair": "admin.world.maintain",
        "content": "admin.world.maintain",
    }

    def __init__(self):
        super().__init__(
            name="world",
            description="世界包管理（list/install/uninstall/reload/status/validate/repair/content）",
            aliases=["worlds"],
        )

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result(self.get_usage(), is_usage=True)
        action = str(args[0]).lower().strip()
        if action == "bridge":
            return self._bridge(context, args[1:])
        if action == "content":
            return self._content(context, args[1:])
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
            "用法: world <list|install|uninstall|reload|status|validate|repair|content> ...; "
            "<world_id> 可为包目录名world_id（见 world list）、大小写不敏感或 manifest.display_name（唯一时）; "
            "world content <validate|diff|apply> <world_ref> ...; "
            "world bridge <add|remove|list|validate> ... [--dry-run] [--two-way] [--bridge-type portal|gate|transit]"
        )

    def _has_sub_permission(self, context: CommandContext, action: str) -> bool:
        required = self._SUB_PERM.get(action, "admin.world.*")
        return permission_checker.check_permission(list(context.permissions or []), required)

    def _bridge_perm_read(self, context: CommandContext) -> bool:
        return permission_checker.check_permission(
            list(context.permissions or []), "admin.world.bridge.read"
        )

    def _bridge_perm_manage(self, context: CommandContext) -> bool:
        return permission_checker.check_permission(
            list(context.permissions or []), "admin.world.bridge.manage"
        )

    @staticmethod
    def _split_bridge_cli(tokens: List[str]) -> tuple[List[str], Dict[str, Any]]:
        flags: Dict[str, Any] = {"two_way": False, "dry_run": False, "bridge_type": "portal", "force": True}
        rest: List[str] = []
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if t == "--two-way":
                flags["two_way"] = True
            elif t == "--dry-run":
                flags["dry_run"] = True
            elif t == "--include-disabled":
                flags["include_disabled"] = True
            elif t == "--bridge-type" and i + 1 < len(tokens):
                flags["bridge_type"] = tokens[i + 1]
                i += 1
            elif t == "--force":
                flags["force"] = True
            else:
                rest.append(t)
            i += 1
        return rest, flags

    def _bridge(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result(
                "用法: world bridge <add|remove|list|validate> ...",
                error=WORLD_BRIDGE_INVALID_ARGUMENT,
            )
        sub = str(args[0]).lower().strip()
        rest, flags = self._split_bridge_cli(args[1:])
        if sub in ("add", "remove"):
            if not self._bridge_perm_manage(context):
                return CommandResult.error_result(
                    "Permission denied for world bridge management",
                    error=WORLD_BRIDGE_PERMISSION_DENIED,
                )
        elif sub in ("list", "validate"):
            if not self._bridge_perm_read(context):
                return CommandResult.error_result(
                    "Permission denied for world bridge read",
                    error=WORLD_BRIDGE_PERMISSION_DENIED,
                )
        else:
            return CommandResult.error_result(
                f"未知 bridge 子命令: {sub}",
                error=WORLD_BRIDGE_INVALID_ARGUMENT,
            )

        if sub == "add":
            if len(rest) < 5:
                return CommandResult.error_result(
                    "用法: world bridge add <src_world> <src_room> <direction> <dst_world> <dst_room> "
                    "[--two-way] [--bridge-type <portal|gate|transit>] [--dry-run]",
                    error=WORLD_BRIDGE_INVALID_ARGUMENT,
                )
            sw, sn, direc, dw, dn = rest[0], rest[1], rest[2], rest[3], rest[4]
            out = world_bridge_service.add_bridge(
                operator=str(context.username or ""),
                src_world=sw,
                src_node_pkg=sn,
                direction=direc,
                dst_world=dw,
                dst_node_pkg=dn,
                two_way=bool(flags.get("two_way")),
                bridge_type=str(flags.get("bridge_type") or "portal"),
                dry_run=bool(flags.get("dry_run")),
            )
            if out.get("ok"):
                return CommandResult.success_result(
                    str(out.get("message") or "bridge ok"),
                    data=out,
                    command_type=self.command_type,
                )
            return CommandResult(
                success=False,
                message=str(out.get("message") or "bridge add failed"),
                data=out,
                error=str(out.get("error") or WORLD_BRIDGE_INVALID_ARGUMENT),
                command_type=self.command_type,
            )

        if sub == "remove":
            bridge_id = None
            src_world = src_node = direction = None
            rrest, rflags = rest, flags
            if len(rrest) == 1:
                bridge_id = rrest[0]
            elif len(rrest) == 3:
                src_world, src_node, direction = rrest[0], rrest[1], rrest[2]
            else:
                return CommandResult.error_result(
                    "用法: world bridge remove <bridge_id> | <src_world> <src_room> <direction> [--dry-run]",
                    error=WORLD_BRIDGE_INVALID_ARGUMENT,
                )
            out = world_bridge_service.remove_bridge(
                bridge_id=bridge_id,
                src_world=src_world,
                src_node_pkg=src_node,
                direction=direction,
                dry_run=bool(rflags.get("dry_run")),
                force=bool(rflags.get("force", True)),
            )
            if out.get("ok"):
                return CommandResult.success_result(
                    str(out.get("message") or "bridge removed"),
                    data=out,
                    command_type=self.command_type,
                )
            return CommandResult(
                success=False,
                message=str(out.get("message") or "bridge remove failed"),
                data=out,
                error=str(out.get("error") or WORLD_BRIDGE_INVALID_ARGUMENT),
                command_type=self.command_type,
            )

        if sub == "list":
            world_filter = rest[0] if rest else None
            out = world_bridge_service.list_bridges(
                world_id=world_filter,
                include_disabled=bool(flags.get("include_disabled")),
            )
            return CommandResult.success_result(
                f"world bridge list ok, total={out.get('total', 0)}",
                data=out,
                command_type=self.command_type,
            )

        if sub == "validate":
            if not rest:
                return CommandResult.error_result(
                    "用法: world bridge validate <world_id>",
                    error=WORLD_BRIDGE_INVALID_ARGUMENT,
                )
            wid = str(rest[0]).strip()
            out = world_bridge_service.validate_bridges(wid)
            if not out.get("ok") and out.get("error") == WORLD_BRIDGE_INVALID_ARGUMENT:
                return CommandResult.error_result(
                    str(out.get("message") or "validate failed"),
                    error=WORLD_BRIDGE_INVALID_ARGUMENT,
                )
            msg = (
                f"world bridge validate passed: {wid}"
                if out.get("ok")
                else f"world bridge validate issues: {out.get('issue_count', 0)}"
            )
            if out.get("ok"):
                return CommandResult.success_result(msg, data=out, command_type=self.command_type)
            return CommandResult(
                success=False,
                message=msg,
                data=out,
                error="WORLD_BOUNDARY_VIOLATION",
                command_type=self.command_type,
            )

        return CommandResult.error_result("internal: bridge routing", error=WORLD_BRIDGE_INVALID_ARGUMENT)

    def _resolve_world_ref(self, ref: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Map CLI world reference to canonical package id (directory name / manifest world_id key for load_game).

        Returns:
            (canonical_world_id, None) on success, or (None, error_message).
        """
        ref = (ref or "").strip()
        if not ref:
            return None, "world reference is empty"
        available = game_engine_manager.list_games()
        if ref in available:
            return ref, None
        rlo = ref.lower()
        ci_matches = [w for w in available if w.lower() == rlo]
        if len(ci_matches) == 1:
            return ci_matches[0], None
        if len(ci_matches) > 1:
            return None, f"ambiguous world id (case-insensitive): {', '.join(ci_matches)}"

        disk_id = self._try_resolve_from_disk(ref)
        if disk_id:
            return disk_id, None

        engine = game_engine_manager.get_engine()
        if not engine or not getattr(engine, "loader", None):
            return None, (
                f"unknown world '{ref}'. Known package ids: {', '.join(available) or '(none)'}; "
                "try: world list"
            )

        hits: List[str] = []
        for wid in available:
            where = self._resolve_world_path(wid)
            rp = where.get("resolved_path")
            if not rp:
                continue
            brief = _read_manifest_brief(Path(rp))
            dn = brief.get("display_name")
            if isinstance(dn, str) and dn.strip().lower() == rlo:
                hits.append(wid)
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            return None, (
                f"ambiguous display_name '{ref}' matches: {', '.join(hits)}. "
                "Use world_id from: world list"
            )
        return None, (
            f"unknown world '{ref}'. Use: world list (canonical id is the package directory name)."
        )

    def _try_resolve_from_disk(self, ref: str) -> Optional[str]:
        """Directory name under loader search_paths (canonical casing), case-insensitive."""
        engine = game_engine_manager.get_engine()
        if not engine or not getattr(engine, "loader", None):
            return None
        rlo = ref.strip().lower()
        if not rlo:
            return None
        for base in engine.loader.search_paths:
            try:
                if not base.is_dir():
                    continue
                for child in base.iterdir():
                    if child.is_dir() and child.name.lower() == rlo:
                        return child.name
            except OSError:
                continue
        return None

    def _row_for_list(self, wid: str, loaded: set) -> Dict[str, Any]:
        where = self._resolve_world_path(wid)
        brief: Dict[str, Any] = {}
        if where.get("resolved_path"):
            brief = _read_manifest_brief(Path(where["resolved_path"]))
        display = brief.get("display_name")
        if not display:
            display = wid
        return {
            "world_id": wid,
            "display_name": display,
            "version": brief.get("version"),
            "api_version": brief.get("api_version"),
            "loaded": wid in loaded,
            "resolved_path": where["resolved_path"],
            "source_type": where["source_type"],
        }

    def _resolve_data_root(self, world_id: str) -> Optional[Path]:
        info = self._resolve_world_path(world_id)
        p = info.get("resolved_path")
        if not p:
            return None
        d = Path(p) / "data"
        return d if d.is_dir() else None

    def _content_flags(self, tokens: List[str]) -> tuple[List[str], Dict[str, Any]]:
        flags: Dict[str, Any] = {"dry_run": False, "report": False, "no_snapshot": False}
        rest: List[str] = []
        for t in tokens:
            if t == "--dry-run":
                flags["dry_run"] = True
            elif t == "--report":
                flags["report"] = True
            elif t == "--no-snapshot":
                flags["no_snapshot"] = True
            else:
                rest.append(t)
        return rest, flags

    def _content(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result(
                "用法: world content <validate|diff|apply> <world_ref> [--report] [--dry-run] [--no-snapshot]"
            )
        sub = str(args[0]).lower().strip()
        rest, flags = self._content_flags(args[1:])
        if not rest:
            return CommandResult.error_result("缺少 world_ref（包目录 id 或 display_name）")
        ref = str(rest[0]).strip()
        if not self._has_sub_permission(context, "content"):
            return CommandResult.error_result("Permission denied for world content", error="WORLD_FORBIDDEN")

        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")

        data_root = self._resolve_data_root(world_id)
        if not data_root:
            return CommandResult.error_result(
                f"未找到世界数据目录: {world_id}（期望 <game_root>/data）",
                error="WORLD_DATA_UNAVAILABLE",
            )

        if sub == "validate":
            try:
                from app.games.hicampus.package.validator import validate_data_package as _vp

                _vp(data_root)
            except DataPackageError as e:
                return CommandResult.error_result(str(e), error=str(e.error_code or "WORLD_DATA_INVALID"))
            except Exception as e:
                return CommandResult.error_result(str(e), error="WORLD_DATA_INVALID")
            payload: Dict[str, Any] = {"world_id": world_id, "package_ok": True}
            if flags.get("report"):
                payload["completeness"] = content_validate_report(data_root)
            return CommandResult.success_result(
                f"world content validate ok: {world_id}",
                data=payload,
                command_type=self.command_type,
            )

        if sub == "diff":
            with db_session_context() as session:
                out = diff_spatial_vs_db(session, world_id, data_root)
            msg = f"world content diff: {out['diff_count']} mismatch(es)"
            return CommandResult.success_result(msg, data=out, command_type=self.command_type)

        if sub == "apply":
            with db_session_context() as session:
                out = apply_spatial_content_overlay(
                    session,
                    world_id,
                    data_root,
                    dry_run=bool(flags.get("dry_run")),
                    write_revision_snapshot=not bool(flags.get("no_snapshot")),
                )
            msg = (
                f"world content apply dry-run: would touch {len(out.get('applied_node_ids', []))} nodes"
                if out.get("dry_run")
                else f"world content apply ok: updated {len(out.get('applied_node_ids', []))} nodes"
            )
            return CommandResult.success_result(msg, data=out, command_type=self.command_type)

        return CommandResult.error_result(f"未知 content 子命令: {sub}")

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
        rows = [self._row_for_list(wid, loaded) for wid in available]
        msg = _format_world_list_message(rows)
        return CommandResult.success_result(
            msg,
            data={"items": rows, "total": len(rows)},
            command_type=self.command_type,
        )

    def _status(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world status <world_ref>")
        ref = str(args[0]).strip()
        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")
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
        return CommandResult.success_result(
            f"world status ok: {world_id}",
            data=payload,
            command_type=self.command_type,
        )

    def _install(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world install <world_ref>")
        ref = str(args[0]).strip()
        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")
        out = game_engine_manager.load_game(world_id)
        if out.get("ok"):
            world_entry_service.sync_world_entry_visibility(world_id, enabled=True)
        return self._from_world_result("world install", world_id, out)

    def _uninstall(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world uninstall <world_ref>")
        ref = str(args[0]).strip()
        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")
        out = game_engine_manager.unload_game(world_id)
        if out.get("ok"):
            world_entry_service.sync_world_entry_visibility(world_id, enabled=False)
        return self._from_world_result("world uninstall", world_id, out)

    def _reload(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world reload <world_ref>")
        ref = str(args[0]).strip()
        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")
        out = game_engine_manager.reload_game(world_id)
        if out.get("ok"):
            world_entry_service.sync_world_entry_visibility(world_id, enabled=True)
        return self._from_world_result("world reload", world_id, out)

    def _validate(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.error_result("用法: world validate <world_ref> [--dry-run]")
        ref = str(args[0]).strip()
        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")
        dry_run = "--dry-run" in args[1:]
        report = world_topology_service.validate_topology(world_id)
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
            return CommandResult.error_result("用法: world repair <world_ref> [--dry-run] [--force]")
        ref = str(args[0]).strip()
        world_id, err = self._resolve_world_ref(ref)
        if err:
            return CommandResult.error_result(err, error="WORLD_NOT_FOUND")
        dry_run = "--dry-run" in args[1:]
        force = "--force" in args[1:]
        report = world_topology_service.repair_topology(world_id, dry_run=dry_run, force=force)
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

