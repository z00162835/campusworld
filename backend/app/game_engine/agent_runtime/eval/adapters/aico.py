"""AICO adapter for the generic Agent Tool Eval runner."""
from __future__ import annotations

import os
import re
import shlex
import time
import uuid
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.commands.base import CommandContext, CommandResult
from app.commands.aico_exec import execute_aico_command
from app.core.database import get_db_session
from app.core.paths import get_backend_root
from app.game_engine.agent_runtime.eval.config import AicoEvalRuntimeConfig
from app.game_engine.agent_runtime.eval.schema import (
    AgentToolEvalCase,
    EvalPrediction,
    ExpectedToolCall,
    TraceEvent,
)
from app.models.system import AgentRunRecord


DEFAULT_AICO_TOOL_DESCRIPTIONS: Dict[str, str] = {
    'help': 'List available commands for the current caller, or show detailed help for one command.',
    'look': 'Inspect the current room or a visible target.',
    'time': 'Show current time.',
    'version': 'Show version information.',
    'whoami': 'Show current user and session identity.',
    'primer': 'Show the CampusWorld system primer.',
    'find': 'Find graph nodes by name, description, type, or location.',
    'describe': 'Show a single graph node details.',
    'agent': 'Inspect and drive agents (subcommands: list, status, tool, show).',
}


class AicoEvalAdapter:
    adapter_name = 'aico'

    def __init__(self, runtime_config: Optional[AicoEvalRuntimeConfig]=None):
        self._runtime_config = runtime_config or AicoEvalRuntimeConfig()
        self._ssh_session: Optional[AicoSshCommandSession] = None

    def run_live_case(self, case: AgentToolEvalCase) -> EvalPrediction:
        if self._runtime_config.require_live_env and os.environ.get('AICO_EVAL_LIVE') != '1':
            raise RuntimeError('live AICO eval requires AICO_EVAL_LIVE=1')
        if self._runtime_config.invoke_via.strip().lower() == 'ssh':
            if self._ssh_session is None:
                self._ssh_session = AicoSshCommandSession(self._runtime_config)
            return run_aico_ssh_case(
                case,
                runtime_config=self._runtime_config,
                ssh_runner=lambda _runtime, command_line: self._ssh_session.run(command_line) if self._ssh_session else '',
            )
        session = get_db_session()
        try:
            return run_aico_command_case(case, db_session=session, runtime_config=self._runtime_config)
        finally:
            session.close()

    def close(self) -> None:
        if self._ssh_session is not None:
            self._ssh_session.close()
            self._ssh_session = None


def infer_ssh_command_outcome(
    *,
    trace_found: bool,
    require_db_trace: bool,
    passthrough_suspected: bool,
    events: Sequence[TraceEvent],
    ssh_error: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Derive SSH command success from transport errors and live trace evidence."""
    if ssh_error:
        return False, ssh_error
    if passthrough_suspected:
        return False, 'passthrough_suspected'
    if require_db_trace and not trace_found:
        return False, 'db_trace_not_found'
    if any(e.event_type == 'live_trace_missing' and e.ok is False for e in events):
        return False, 'live_trace_missing'
    return True, None


def run_aico_ssh_case(
    case: AgentToolEvalCase,
    *,
    runtime_config: Optional[AicoEvalRuntimeConfig]=None,
    ssh_runner: Optional[Callable[[AicoEvalRuntimeConfig, str], str]]=None,
    trace_loader: Optional[Callable[[Any, int], Tuple[List[Mapping[str, Any]], Dict[str, Any]]]]=None,
    log_loader: Optional[Callable[[str], List[str]]]=None,
) -> EvalPrediction:
    """Run ``aico`` through the real SSH command channel and load DB trace evidence."""
    runtime = runtime_config or AicoEvalRuntimeConfig()
    command_line = _aico_command_line_for_case(case, runtime)
    session = get_db_session()
    before_id = 0
    started = time.time()
    try:
        before_id = _latest_agent_run_id(session)
    finally:
        session.close()

    ssh_error: Optional[str] = None
    try:
        output = (ssh_runner or run_ssh_command)(runtime, command_line)
    except Exception as exc:
        output = ''
        ssh_error = str(exc)

    session = get_db_session()
    try:
        trace_fn = trace_loader or load_latest_aico_run_trace_after_id
        (raw_trace, trace_meta) = trace_fn(session, before_id)
    finally:
        session.close()
    events = normalize_aico_command_trace(raw_trace)
    trace_found = bool(trace_meta.get('found')) if isinstance(trace_meta, dict) else False
    if runtime.require_db_trace and not trace_found:
        events.append(
            TraceEvent(
                event_type='live_trace_missing',
                ok=False,
                reason='agent_run_records_not_found_after_ssh_command',
                data={'after_run_id': before_id, 'db_trace': dict(trace_meta)},
            )
        )
    passthrough_suspected = bool(not trace_found and output.strip() == case.user_message.strip())
    (command_success, command_error) = infer_ssh_command_outcome(
        trace_found=trace_found,
        require_db_trace=bool(runtime.require_db_trace),
        passthrough_suspected=passthrough_suspected,
        events=events,
        ssh_error=ssh_error,
    )
    logs = (log_loader or (lambda cid: collect_aico_log_excerpt(cid, log_path=runtime.log_path)))(str(trace_meta.get('correlation_id') or ''))
    tool_calls = _tool_calls_from_events(events)
    predicted = _dedupe([c.name for c in tool_calls] + [e.tool_name for e in events if e.event_type == 'tool_exec'])
    return EvalPrediction(
        predicted_tools=predicted,
        tool_calls=tool_calls,
        final_reply=output.strip(),
        trace=events,
        metadata={
            'adapter': 'aico',
            'mode': 'live',
            'invoke_via': 'ssh',
            'require_db_trace': bool(runtime.require_db_trace),
            'invocation': 'aico -nd' if _case_wants_new_dialogue(case, runtime) else 'aico',
            'command_line': command_line,
            'command_success': command_success,
            'command_error': command_error,
            'elapsed_ms': round((time.time() - started) * 1000.0, 3),
            'db_trace': trace_meta,
            'passthrough_suspected': passthrough_suspected,
            'aico_log_excerpt': logs,
            'ssh': {
                'host': runtime.ssh_host,
                'port': runtime.ssh_port,
                'username': runtime.ssh_username,
                'session_scope': 'eval_run',
            },
        },
    )


def run_aico_command_case(
    case: AgentToolEvalCase,
    *,
    db_session,
    command_runner: Callable[[CommandContext, List[str]], CommandResult]=execute_aico_command,
    trace_loader: Optional[Callable[[Any, str], Tuple[List[Mapping[str, Any]], Dict[str, Any]]]]=None,
    log_loader: Optional[Callable[[str], List[str]]]=None,
    runtime_config: Optional[AicoEvalRuntimeConfig]=None,
) -> EvalPrediction:
    """Run the real ``aico`` command path and convert DB/log evidence to an eval prediction.

    ``aico <message>`` is the default. Set ``case.metadata.aico_new_dialogue``
    to true to run ``aico -nd <message>`` for cases that must start a separate
    conversation thread.
    """
    runtime = runtime_config or AicoEvalRuntimeConfig()
    correlation_id = str(case.metadata.get('session_id') or f'aico_eval_{case.example_id}_{uuid.uuid4().hex[:8]}')
    context = CommandContext(
        user_id=str(case.metadata.get('user_id') or os.environ.get('AICO_EVAL_USER_ID') or runtime.user_id),
        username=str(case.metadata.get('username') or os.environ.get('AICO_EVAL_USERNAME') or runtime.username),
        session_id=correlation_id,
        permissions=_split_csv(case.metadata.get('permissions') or os.environ.get('AICO_EVAL_PERMISSIONS') or runtime.permissions),
        roles=_split_csv(case.metadata.get('roles') or os.environ.get('AICO_EVAL_ROLES') or runtime.roles),
        db_session=db_session,
        metadata={'eval_example_id': case.example_id, 'eval_mode': 'live_command'},
    )
    argv = _aico_argv_for_case(case, runtime)
    started = time.time()
    result = command_runner(context, argv)
    db_session.commit()
    trace_fn = trace_loader or load_latest_aico_run_trace
    (raw_trace, trace_meta) = trace_fn(db_session, correlation_id)
    events = normalize_aico_command_trace(raw_trace)
    trace_found = bool(trace_meta.get('found')) if isinstance(trace_meta, dict) else False
    if runtime.require_db_trace and not trace_found:
        events.append(
            TraceEvent(
                event_type='live_trace_missing',
                ok=False,
                reason='agent_run_records_not_found',
                data={'correlation_id': correlation_id, 'db_trace': dict(trace_meta)},
            )
        )
    logs = (log_loader or (lambda cid: collect_aico_log_excerpt(cid, log_path=runtime.log_path)))(correlation_id)
    tool_calls = _tool_calls_from_events(events)
    predicted = _dedupe([c.name for c in tool_calls] + [e.tool_name for e in events if e.event_type == 'tool_exec'])
    final_reply = str(result.message or '')
    passthrough_suspected = (
        bool(result.success)
        and not trace_found
        and not raw_trace
        and final_reply.strip() == case.user_message.strip()
    )
    return EvalPrediction(
        predicted_tools=predicted,
        tool_calls=tool_calls,
        final_reply=final_reply,
        trace=events,
        metadata={
            'adapter': 'aico',
            'mode': 'live',
            'require_db_trace': bool(runtime.require_db_trace),
            'invocation': 'aico -nd' if _case_wants_new_dialogue(case, runtime) else 'aico',
            'argv': argv,
            'command_success': bool(result.success),
            'command_error': result.error,
            'correlation_id': correlation_id,
            'elapsed_ms': round((time.time() - started) * 1000.0, 3),
            'db_trace': trace_meta,
            'passthrough_suspected': passthrough_suspected,
            'aico_log_excerpt': logs,
        },
    )


def load_latest_aico_run_trace(db_session, correlation_id: str) -> Tuple[List[Mapping[str, Any]], Dict[str, Any]]:
    row = (
        db_session.query(AgentRunRecord)
        .filter(AgentRunRecord.correlation_id == str(correlation_id))
        .order_by(AgentRunRecord.id.desc())
        .first()
    )
    if row is None:
        return ([], {'found': False, 'correlation_id': correlation_id})
    trace = row.command_trace if isinstance(row.command_trace, list) else []
    return (
        trace,
        {
            'found': True,
            'run_id': str(row.run_id),
            'row_id': int(row.id),
            'agent_node_id': int(row.agent_node_id),
            'phase': row.phase,
            'status': row.status,
            'correlation_id': row.correlation_id,
        },
    )


def load_latest_aico_run_trace_after_id(db_session, after_run_id: int) -> Tuple[List[Mapping[str, Any]], Dict[str, Any]]:
    row = (
        db_session.query(AgentRunRecord)
        .filter(AgentRunRecord.id > int(after_run_id or 0))
        .order_by(AgentRunRecord.id.desc())
        .first()
    )
    if row is None:
        return ([], {'found': False, 'after_run_id': int(after_run_id or 0)})
    trace = row.command_trace if isinstance(row.command_trace, list) else []
    return (
        trace,
        {
            'found': True,
            'run_id': str(row.run_id),
            'row_id': int(row.id),
            'agent_node_id': int(row.agent_node_id),
            'phase': row.phase,
            'status': row.status,
            'correlation_id': row.correlation_id,
            'after_run_id': int(after_run_id or 0),
        },
    )


class AicoSshCommandSession:
    """Persistent SSH shell used for one eval run, preserving conversation state."""

    def __init__(self, runtime: AicoEvalRuntimeConfig):
        self._runtime = runtime
        self._client = None
        self._channel = None

    def run(self, command_line: str) -> str:
        self._connect()
        self._channel.send((command_line + '\n').encode('utf-8'))
        raw = _read_until_ssh_prompt(self._channel, timeout=float(self._runtime.ssh_command_timeout_seconds or 180.0))
        return _strip_ssh_command_frame(raw, command_line)

    def close(self) -> None:
        if self._channel is not None:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _connect(self) -> None:
        if self._channel is not None and not getattr(self._channel, 'closed', False):
            return
        _quiet_paramiko_logs()
        try:
            import paramiko
        except ImportError as exc:
            raise RuntimeError('paramiko is required for SSH-backed AICO eval') from exc
        password = os.environ.get(self._runtime.ssh_password_env, '').strip() if self._runtime.ssh_password_env else ''
        if not password:
            raise RuntimeError(f'SSH-backed AICO eval requires password env var: {self._runtime.ssh_password_env}')
        timeout = float(self._runtime.ssh_command_timeout_seconds or 180.0)
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self._runtime.ssh_host,
            port=int(self._runtime.ssh_port),
            username=self._runtime.ssh_username,
            password=password,
            look_for_keys=False,
            allow_agent=False,
            timeout=min(timeout, 30.0),
            auth_timeout=min(timeout, 30.0),
            banner_timeout=min(timeout, 30.0),
        )
        self._channel = self._client.invoke_shell(term='xterm')
        self._channel.settimeout(1.0)
        _read_until_ssh_prompt(self._channel, timeout=timeout)


def run_ssh_command(runtime: AicoEvalRuntimeConfig, command_line: str) -> str:
    session = AicoSshCommandSession(runtime)
    try:
        return session.run(command_line)
    finally:
        session.close()


def collect_aico_log_excerpt(correlation_id: str, *, log_path: Optional[Path]=None, max_lines: int=200) -> List[str]:
    if not str(correlation_id or '').strip():
        return []
    path = log_path or _default_aico_log_path()
    if path is None or not path.exists():
        return []
    needle = str(correlation_id)
    matches: List[str] = []
    try:
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
            if needle in line:
                matches.append(line)
    except OSError:
        return []
    return matches[-max_lines:]


def normalize_aico_command_trace(entries: Iterable[Mapping[str, Any]]) -> List[TraceEvent]:
    """Map existing AICO command_trace rows into generic trace events."""
    out: List[TraceEvent] = []
    for entry in entries:
        step = str(entry.get('step') or '')
        event_type = {
            'tool_exec': 'tool_exec',
            'tool_cap': 'budget_cap',
            'tool_router': 'tool_router',
            'mandatory_observation_gap': 'mandatory_gap',
            'tool_call_filtered': 'schema_violation',
            'guard_block': 'permission_denied',
        }.get(step, step or 'trace')
        out.append(
            TraceEvent(
                event_type=event_type,
                tool_name=str(entry.get('tool_name') or entry.get('command_name') or ''),
                args=[str(x) for x in entry.get('args') or []],
                ok=entry.get('success') if isinstance(entry.get('success'), bool) else None,
                text=_first_trace_text(entry),
                phase=str(entry.get('phase') or ''),
                reason=str(entry.get('reason') or entry.get('detail') or entry.get('error') or ''),
                data=dict(entry),
            )
        )
    return out


def _aico_argv_for_case(case: AgentToolEvalCase, runtime_config: Optional[AicoEvalRuntimeConfig]=None) -> List[str]:
    if _case_wants_new_dialogue(case, runtime_config):
        return ['-nd', case.user_message]
    return [case.user_message]


def _aico_command_line_for_case(case: AgentToolEvalCase, runtime_config: Optional[AicoEvalRuntimeConfig]=None) -> str:
    argv = ['aico'] + _aico_argv_for_case(case, runtime_config)
    return ' '.join(shlex.quote(str(part)) for part in argv)


def _case_wants_new_dialogue(case: AgentToolEvalCase, runtime_config: Optional[AicoEvalRuntimeConfig]=None) -> bool:
    raw = case.metadata.get('aico_new_dialogue')
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in {'1', 'true', 'yes', 'y'}
    if os.environ.get('AICO_EVAL_NEW_DIALOGUE') == '1':
        return True
    runtime = runtime_config or AicoEvalRuntimeConfig()
    return bool(runtime.default_new_dialogue)


def _tool_calls_from_events(events: Sequence[TraceEvent]) -> List[ExpectedToolCall]:
    calls: List[ExpectedToolCall] = []
    for e in events:
        if e.event_type == 'tool_exec' and e.tool_name:
            calls.append(ExpectedToolCall(name=e.tool_name, args=list(e.args)))
    return calls


def _split_csv(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or '').split(',') if x.strip()]


def _latest_agent_run_id(db_session) -> int:
    row = db_session.query(AgentRunRecord.id).order_by(AgentRunRecord.id.desc()).first()
    return int(row[0]) if row else 0


def _quiet_paramiko_logs() -> None:
    for name in ('paramiko', 'paramiko.transport'):
        logging.getLogger(name).setLevel(logging.WARNING)


def _read_until_ssh_prompt(channel, *, timeout: float) -> str:
    deadline = time.time() + timeout
    chunks: List[str] = []
    while time.time() < deadline:
        try:
            if channel.recv_ready():
                data = channel.recv(8192)
                if not data:
                    break
                chunks.append(data.decode('utf-8', errors='replace'))
                joined = ''.join(chunks)
                if _SSH_PROMPT_RE.search(joined):
                    return joined
            else:
                time.sleep(0.05)
        except Exception as exc:
            if 'timed out' not in str(exc).lower() and 'timeout' not in str(exc).lower():
                raise
    raise TimeoutError('timed out waiting for SSH command prompt')


_SSH_PROMPT_RE = re.compile(r'\[[^\]\r\n]+@\d{2}:\d{2}:\d{2}\]\s+[^\r\n>]*>\s*$', re.MULTILINE)


def _strip_ssh_command_frame(raw: str, command_line: str) -> str:
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    text = _SSH_PROMPT_RE.sub('', text).strip()
    lines = text.splitlines()
    if lines and lines[0].strip() == command_line.strip():
        lines = lines[1:]
    return '\n'.join(lines).strip()


def _first_trace_text(entry: Mapping[str, Any]) -> str:
    for key in ('text', 'message', 'message_preview', 'observation_text', 'output', 'result'):
        raw = entry.get(key)
        if raw is not None:
            return str(raw)
    return ''


def _default_aico_log_path() -> Optional[Path]:
    raw = os.environ.get('AICO_EVAL_LOG_PATH')
    if raw:
        return Path(raw)
    try:
        from app.core.config_manager import get_config
        cm = get_config()
        obs = cm.get('agents.llm.by_service_id.aico.observability') or {}
        rel = obs.get('log_path') if isinstance(obs, dict) else None
        return (get_backend_root(cm) / str(rel or 'logs/agent/aico.log')).resolve()
    except Exception:
        return None


def _dedupe(names: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in names:
        n = str(raw).strip()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
