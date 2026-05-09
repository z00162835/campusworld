"""Lexicon snapshot admin command (gazetteer export)."""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import List

from app.commands.base import AdminCommand, CommandContext, CommandResult, CommandType
from app.core.permissions import permission_checker
from app.game_engine.agent_runtime.tool_router.lexicon_export import (
    build_lexicon_snapshot_rows,
    compute_lexicon_revision,
    snapshot_meta,
)
from app.game_engine.agent_runtime.tool_router.paths import (
    lexicon_active_pointer_path,
    lexicon_data_root,
    lexicon_version_dir,
)


class LexiconCommand(AdminCommand):
    """Offline lexicon builds and activation (admin)."""

    _PERM = "admin.world.manage"

    def __init__(self):
        super().__init__(
            "lexicon",
            "Build, list, delete, or activate graph-derived gazetteer snapshots.",
            [],
        )
        self.command_type = CommandType.ADMIN

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.usage_result(self._usage())
        if not permission_checker.check_permission(list(context.permissions or []), self._PERM):
            return CommandResult.error_result("Permission denied for lexicon management")
        sub = str(args[0]).lower().strip()
        if sub == "-b":
            return self._build(context, args[1:])
        if sub == "-l":
            return self._list()
        if sub == "-d":
            return self._delete(args[1:])
        if sub == "-a":
            return self._activate(args[1:])
        return CommandResult.usage_result(self._usage())

    def _usage(self) -> str:
        return (
            "lexicon -b   — build new snapshot from graph DB\n"
            "lexicon -l   — list versions\n"
            "lexicon -d <id> — delete version (not active)\n"
            "lexicon -a <id> — activate version"
        )

    def _ensure_dirs(self) -> None:
        lexicon_data_root().mkdir(parents=True, exist_ok=True)

    def _build(self, context: CommandContext, _args: List[str]) -> CommandResult:
        self._ensure_dirs()
        session = context.db_session
        if session is None:
            return CommandResult.error_result("No database session in context")
        rows = build_lexicon_snapshot_rows(session)
        revision = compute_lexicon_revision(rows)
        new_id = uuid.uuid4().hex[:12]
        vdir = lexicon_version_dir(new_id)
        vdir.mkdir(parents=True, exist_ok=True)
        meta = snapshot_meta(lexicon_id=new_id, lexicon_revision=revision)
        entries_path = vdir / "entries.jsonl"
        with entries_path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        (vdir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        msg = f"lexicon built id={new_id} revision={revision} rows={len(rows)}"
        return CommandResult.success_result(msg, data={"id": new_id, "lexicon_revision": revision})

    def _list(self) -> CommandResult:
        self._ensure_dirs()
        active = None
        ap = lexicon_active_pointer_path()
        if ap.is_file():
            try:
                active = ap.read_text(encoding="utf-8").strip() or None
            except OSError:
                active = None
        lines = []
        root = lexicon_data_root()
        for p in sorted(root.iterdir()):
            if not p.is_dir():
                continue
            vid = p.name
            meta_f = p / "meta.json"
            meta = {}
            if meta_f.is_file():
                try:
                    meta = json.loads(meta_f.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}
            is_act = "yes" if active == vid else "no"
            rev = meta.get("lexicon_revision", "?")
            built = meta.get("built_at", "?")
            lines.append(f"{vid}\tactive={is_act}\trev={rev}\tbuilt_at={built}")
        if not lines:
            return CommandResult.success_result("(no lexicon versions)")
        return CommandResult.success_result("id\tactive\trev\tbuilt_at\n" + "\n".join(lines))

    def _delete(self, args: List[str]) -> CommandResult:
        if len(args) < 1:
            return CommandResult.usage_result("lexicon -d <id>")
        vid = args[0].strip()
        active = None
        ap = lexicon_active_pointer_path()
        if ap.is_file():
            try:
                active = ap.read_text(encoding="utf-8").strip()
            except OSError:
                active = None
        if active and active == vid:
            return CommandResult.error_result("Cannot delete active lexicon; activate another first")
        p = lexicon_version_dir(vid)
        if not p.is_dir():
            return CommandResult.error_result(f"Unknown lexicon id: {vid}")
        shutil.rmtree(p)
        return CommandResult.success_result(f"deleted {vid}")

    def _activate(self, args: List[str]) -> CommandResult:
        if len(args) < 1:
            return CommandResult.usage_result("lexicon -a <id>")
        vid = args[0].strip()
        p = lexicon_version_dir(vid)
        if not p.is_dir():
            return CommandResult.error_result(f"Unknown lexicon id: {vid}")
        self._ensure_dirs()
        ap = lexicon_active_pointer_path()
        tmp = Path(str(ap) + ".tmp")
        tmp.write_text(vid + "\n", encoding="utf-8")
        tmp.replace(ap)
        return CommandResult.success_result(f"active lexicon -> {vid}")


LEXICON_COMMAND = LexiconCommand()
