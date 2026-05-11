"""Lexicon snapshot admin command (gazetteer export)."""
from __future__ import annotations
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, List
from app.commands.base import AdminCommand, CommandContext, CommandResult, CommandType
from app.commands.i18n.command_resource import get_command_i18n_text
from app.commands.i18n.locale_text import normalize_locale, resolve_locale
from app.core.permissions import permission_checker
from app.game_engine.agent_runtime.tool_router.lexicon_export import build_lexicon_snapshot_rows, compute_lexicon_revision, snapshot_meta
from app.game_engine.agent_runtime.tool_router import paths as lexicon_paths
_USAGE_EN_FALLBACK = 'lexicon -b   — build a new snapshot from the graph database\nlexicon -l   — list versions\nlexicon -d <id> — delete a version (must not be active)\nlexicon -a <id> — activate a version'

class LexiconCommand(AdminCommand):
    """Offline lexicon builds and activation (admin)."""
    _PERM = 'admin.world.manage'

    def __init__(self):
        super().__init__('lexicon', '', [])
        self.command_type = CommandType.ADMIN

    def get_localized_usage(self, locale: str) -> str:
        return get_command_i18n_text('lexicon', 'usage.block', normalize_locale(locale), _USAGE_EN_FALLBACK).strip()

    def get_usage(self) -> str:
        return self.get_localized_usage('en-US')

    def _msg(self, context: CommandContext, key: str, default: str, **kwargs: Any) -> str:
        loc = resolve_locale(context)
        raw = get_command_i18n_text('lexicon', key, loc, default)
        if kwargs:
            try:
                return raw.format(**kwargs)
            except (KeyError, ValueError):
                return raw
        return raw

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return CommandResult.usage_result(self.get_localized_usage(resolve_locale(context)))
        if not permission_checker.check_permission(list(context.permissions or []), self._PERM):
            return CommandResult.error_result(self._msg(context, 'error.permission_denied', 'Permission denied for lexicon management.'))
        sub = str(args[0]).lower().strip()
        if sub == '-b':
            return self._build(context, args[1:])
        if sub == '-l':
            return self._list(context)
        if sub == '-d':
            return self._delete(context, args[1:])
        if sub == '-a':
            return self._activate(context, args[1:])
        return CommandResult.usage_result(self.get_localized_usage(resolve_locale(context)))

    def _ensure_dirs(self) -> None:
        lexicon_paths.lexicon_data_root().mkdir(parents=True, exist_ok=True)

    def _build(self, context: CommandContext, _args: List[str]) -> CommandResult:
        self._ensure_dirs()
        session = context.db_session
        if session is None:
            return CommandResult.error_result(self._msg(context, 'error.no_db_session', 'No database session in context'))
        rows = build_lexicon_snapshot_rows(session)
        revision = compute_lexicon_revision(rows)
        new_id = uuid.uuid4().hex[:12]
        vdir = lexicon_paths.lexicon_version_dir(new_id)
        vdir.mkdir(parents=True, exist_ok=True)
        meta = snapshot_meta(lexicon_id=new_id, lexicon_revision=revision)
        entries_path = vdir / 'entries.jsonl'
        with entries_path.open('w', encoding='utf-8') as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        (vdir / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        msg = self._msg(context, 'success.build', 'Lexicon built id={id} revision={revision} rows={rows}', id=new_id, revision=revision, rows=len(rows))
        return CommandResult.success_result(msg, data={'id': new_id, 'lexicon_revision': revision})

    def _list(self, context: CommandContext) -> CommandResult:
        self._ensure_dirs()
        active = None
        ap = lexicon_paths.lexicon_active_pointer_path()
        if ap.is_file():
            try:
                active = ap.read_text(encoding='utf-8').strip() or None
            except OSError:
                active = None
        lines: List[str] = []
        yes = self._msg(context, 'list.yes', 'yes')
        no = self._msg(context, 'list.no', 'no')
        root = lexicon_paths.lexicon_data_root()
        for p in sorted(root.iterdir()):
            if not p.is_dir():
                continue
            vid = p.name
            meta_f = p / 'meta.json'
            meta: dict = {}
            if meta_f.is_file():
                try:
                    loaded = json.loads(meta_f.read_text(encoding='utf-8'))
                    meta = loaded if isinstance(loaded, dict) else {}
                except (OSError, json.JSONDecodeError):
                    meta = {}
            is_act_label = yes if active == vid else no
            rev = meta.get('lexicon_revision', '?')
            built = meta.get('built_at', '?')
            lines.append(self._msg(context, 'list.row', '{id}\tactive={active}\trev={rev}\tbuilt_at={built_at}', id=vid, active=is_act_label, rev=rev, built_at=built))
        if not lines:
            return CommandResult.success_result(self._msg(context, 'success.empty_versions', '(no lexicon versions)'))
        header = self._msg(context, 'list.header', 'id\tactive\trev\tbuilt_at')
        return CommandResult.success_result(header + '\n' + '\n'.join(lines))

    def _delete(self, context: CommandContext, args: List[str]) -> CommandResult:
        if len(args) < 1:
            return CommandResult.usage_result(self._msg(context, 'usage_line.delete', 'lexicon -d <id>'))
        vid = args[0].strip()
        active = None
        ap = lexicon_paths.lexicon_active_pointer_path()
        if ap.is_file():
            try:
                active = ap.read_text(encoding='utf-8').strip()
            except OSError:
                active = None
        if active and active == vid:
            return CommandResult.error_result(self._msg(context, 'error.delete_active', 'Cannot delete the active lexicon; activate another version first.'))
        p = lexicon_paths.lexicon_version_dir(vid)
        if not p.is_dir():
            return CommandResult.error_result(self._msg(context, 'error.unknown_id', 'Unknown lexicon id: {id}', id=vid))
        shutil.rmtree(p)
        return CommandResult.success_result(self._msg(context, 'success.delete', 'Deleted {id}', id=vid))

    def _activate(self, context: CommandContext, args: List[str]) -> CommandResult:
        if len(args) < 1:
            return CommandResult.usage_result(self._msg(context, 'usage_line.activate', 'lexicon -a <id>'))
        vid = args[0].strip()
        p = lexicon_paths.lexicon_version_dir(vid)
        if not p.is_dir():
            return CommandResult.error_result(self._msg(context, 'error.unknown_id', 'Unknown lexicon id: {id}', id=vid))
        self._ensure_dirs()
        ap = lexicon_paths.lexicon_active_pointer_path()
        tmp = Path(str(ap) + '.tmp')
        tmp.write_text(vid + '\n', encoding='utf-8')
        tmp.replace(ap)
        return CommandResult.success_result(self._msg(context, 'success.activate', 'Active lexicon set to {id}', id=vid))
LEXICON_COMMAND = LexiconCommand()
