"""Streamlit report UI for AICO live tool evaluation."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[4]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.game_engine.agent_runtime.eval.config import DEFAULT_CONFIG_PATH, AicoEvalRuntimeConfig, EvalToolConfig, load_eval_config
from app.game_engine.agent_runtime.eval.promote import promoted_cases_from_pairs
from app.game_engine.agent_runtime.eval.metrics import build_report, evaluate_report_gates, report_passes_initial_gates
from app.game_engine.agent_runtime.eval.runner import (
    adapter_by_name,
    resolve_cases_path_for_suite,
    validate_case_governance,
    write_report,
)
from app.game_engine.agent_runtime.eval.schema import AgentToolEvalCase, EvalPair, load_cases_jsonl, load_pairs_jsonl, write_jsonl


def _configure_streamlit_eval_logging() -> None:
    """Reduce noisy third-party DEBUG output in the Streamlit eval UI process."""
    import logging

    logging.getLogger().setLevel(logging.INFO)
    for name in (
        'fsevents',
        'watchdog',
        'watchdog.observers',
        'watchdog.observers.inotify_buffer',
        'watchfiles',
        'streamlit',
        'streamlit.runtime',
        'streamlit.runtime.scriptrunner',
        'streamlit.runtime.media_file_storage',
        'paramiko',
        'paramiko.transport',
        'asyncio',
        'urllib3',
        'requests',
        'sqlalchemy',
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


_configure_streamlit_eval_logging()


def load_dashboard_data(*, pairs_path: Path, report_path: Optional[Path]=None) -> Dict[str, Any]:
    pairs = load_pairs_jsonl(pairs_path)
    report: Dict[str, Any] = {}
    if report_path and report_path.exists():
        report = json.loads(report_path.read_text(encoding='utf-8'))
    return {'pairs': pairs, 'report': report}


def _validate_in_backend_root(path: Path, name: str) -> Path:
    """Resolve path and verify it stays within BACKEND_ROOT."""
    resolved = path.resolve()
    try:
        resolved.relative_to(BACKEND_ROOT.resolve())
    except ValueError:
        raise ValueError(f'{name} path escapes backend root: {path}')
    return resolved


def load_cases_rows(cases_path: Path) -> List[Dict[str, Any]]:
    return [c.to_dict() for c in load_cases_jsonl(cases_path)]


def case_rows(cases: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for case in cases:
        metadata = case.get('metadata') if isinstance(case, Mapping) else {}
        metadata = metadata if isinstance(metadata, Mapping) else {}
        rows.append({
            'example_id': str(case.get('example_id') or ''),
            'agent_id': str(case.get('agent_id') or 'aico'),
            'language': str(case.get('language') or ''),
            'intent': str(metadata.get('intent') or ''),
            'dataset_tier': str(metadata.get('dataset_tier') or ''),
            'tags': ','.join([str(x) for x in (case.get('tags') or [])]),
            'expected_tools': ','.join([str(x) for x in (case.get('expected_tools') or [])]),
            'mandatory_tools': ','.join([str(x) for x in (case.get('mandatory_tools') or [])]),
            'user_message': str(case.get('user_message') or ''),
        })
    return rows


def filter_cases(
    cases: Iterable[Mapping[str, Any]],
    *,
    q: str='',
    intent: str='',
    tag: str='',
    language: str='',
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    q_lower = q.strip().lower()
    intent_lower = intent.strip().lower()
    tag_lower = tag.strip().lower()
    lang_lower = language.strip().lower()
    for case in cases:
        metadata = case.get('metadata') if isinstance(case, Mapping) else {}
        metadata = metadata if isinstance(metadata, Mapping) else {}
        fields = [
            str(case.get('example_id') or ''),
            str(case.get('user_message') or ''),
            str(case.get('context_snapshot') or ''),
            str(metadata.get('intent') or ''),
            ','.join([str(x) for x in (case.get('tags') or [])]),
        ]
        if q_lower and q_lower not in ' '.join(fields).lower():
            continue
        if intent_lower and str(metadata.get('intent') or '').strip().lower() != intent_lower:
            continue
        if tag_lower and tag_lower not in {str(x).strip().lower() for x in (case.get('tags') or [])}:
            continue
        if lang_lower and str(case.get('language') or '').strip().lower() != lang_lower:
            continue
        out.append(dict(case))
    return out


def upsert_case(cases: List[Dict[str, Any]], case_obj: Mapping[str, Any]) -> List[Dict[str, Any]]:
    validated = AgentToolEvalCase.from_obj(dict(case_obj)).to_dict()
    example_id = validated['example_id']
    out = [dict(c) for c in cases if str(c.get('example_id') or '') != example_id]
    out.append(validated)
    out.sort(key=lambda x: str(x.get('example_id') or ''))
    return out


def delete_case(cases: List[Dict[str, Any]], example_id: str) -> List[Dict[str, Any]]:
    return [dict(c) for c in cases if str(c.get('example_id') or '') != str(example_id or '')]


def _split_csv_field(value: str) -> List[str]:
    return [x.strip() for x in str(value or '').split(',') if x.strip()]


def _join_csv_field(values: Iterable[Any]) -> str:
    return ', '.join(str(x).strip() for x in values if str(x).strip())


def _parse_json_object_field(raw: str, *, field_name: str) -> Dict[str, Any]:
    text = str(raw or '').strip()
    if not text:
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError(f'{field_name} must be a JSON object')
    return parsed


def _parse_json_list_field(raw: str, *, field_name: str) -> List[Any]:
    text = str(raw or '').strip()
    if not text:
        return []
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError(f'{field_name} must be a JSON array')
    return parsed


def new_case_template(*, default_suite: str) -> Dict[str, Any]:
    return {
        'example_id': '',
        'agent_id': 'aico',
        'user_message': '',
        'context_snapshot': '',
        'available_tools': [],
        'expected_tools': [],
        'mandatory_tools': [],
        'forbidden_tools': [],
        'expected_args': {},
        'expected_tool_sequence': [],
        'sequence_matcher': 'subsequence',
        'chain_assertions': [],
        'expected_observation_contains': {},
        'tags': ['live'],
        'data_source': 'synthetic',
        'language': 'zh',
        'metadata': {
            'intent': '',
            'dataset_tier': default_suite,
            'dataset_version': '2026-05-gate-v1',
            'case_owner': 'agent-runtime',
        },
    }


def validate_case_dict_governance(
    case_dict: Mapping[str, Any],
    *,
    suite: str,
    config: EvalToolConfig,
) -> None:
    case = AgentToolEvalCase.from_obj(dict(case_dict))
    validate_case_governance([case], expected_suite=suite, config=config)


def case_to_form_state(case: Mapping[str, Any], *, default_suite: str) -> Dict[str, Any]:
    metadata = case.get('metadata') if isinstance(case.get('metadata'), Mapping) else {}
    metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    tools = case.get('available_tools') if isinstance(case.get('available_tools'), list) else []
    tool_rows = []
    for tool in tools:
        if not isinstance(tool, Mapping):
            continue
        name = str(tool.get('name') or '').strip()
        if not name:
            continue
        tool_rows.append({'name': name, 'description': str(tool.get('description') or '')})
    return {
        'example_id': str(case.get('example_id') or ''),
        'agent_id': str(case.get('agent_id') or 'aico'),
        'user_message': str(case.get('user_message') or ''),
        'context_snapshot': str(case.get('context_snapshot') or ''),
        'language': str(case.get('language') or ''),
        'data_source': str(case.get('data_source') or 'synthetic'),
        'tags_csv': _join_csv_field(case.get('tags') or []),
        'expected_tools_csv': _join_csv_field(case.get('expected_tools') or []),
        'mandatory_tools_csv': _join_csv_field(case.get('mandatory_tools') or []),
        'forbidden_tools_csv': _join_csv_field(case.get('forbidden_tools') or []),
        'sequence_matcher': str(case.get('sequence_matcher') or 'subsequence'),
        'intent': str(metadata.get('intent') or ''),
        'dataset_tier': str(metadata.get('dataset_tier') or default_suite),
        'dataset_version': str(metadata.get('dataset_version') or ''),
        'case_owner': str(metadata.get('case_owner') or 'agent-runtime'),
        'aico_new_dialogue': bool(metadata.get('aico_new_dialogue')),
        'available_tools_rows': tool_rows,
        'expected_args_json': json.dumps(case.get('expected_args') or {}, ensure_ascii=False, indent=2),
        'expected_tool_sequence_json': json.dumps(case.get('expected_tool_sequence') or [], ensure_ascii=False, indent=2),
        'chain_assertions_json': json.dumps(case.get('chain_assertions') or [], ensure_ascii=False, indent=2),
        'expected_observation_contains_json': json.dumps(
            case.get('expected_observation_contains') or {},
            ensure_ascii=False,
            indent=2,
        ),
    }


def build_case_from_form_state(
    form: Mapping[str, Any],
    *,
    base_case: Optional[Mapping[str, Any]] = None,
    default_suite: str,
) -> Dict[str, Any]:
    base = dict(base_case) if base_case else new_case_template(default_suite=default_suite)
    metadata = dict(base.get('metadata') or {}) if isinstance(base.get('metadata'), Mapping) else {}
    metadata['intent'] = str(form.get('intent') or '').strip()
    metadata['dataset_tier'] = str(form.get('dataset_tier') or default_suite).strip().lower()
    metadata['dataset_version'] = str(form.get('dataset_version') or '').strip()
    metadata['case_owner'] = str(form.get('case_owner') or 'agent-runtime').strip() or 'agent-runtime'
    if bool(form.get('aico_new_dialogue')):
        metadata['aico_new_dialogue'] = True
    else:
        metadata.pop('aico_new_dialogue', None)
    tool_rows = form.get('available_tools_rows') if isinstance(form.get('available_tools_rows'), list) else []
    available_tools: List[Dict[str, str]] = []
    for row in tool_rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        available_tools.append({'name': name, 'description': str(row.get('description') or '')})
    case_obj = {
        'example_id': str(form.get('example_id') or '').strip(),
        'agent_id': str(form.get('agent_id') or 'aico').strip() or 'aico',
        'user_message': str(form.get('user_message') or '').strip(),
        'context_snapshot': str(form.get('context_snapshot') or '').strip(),
        'language': str(form.get('language') or '').strip(),
        'data_source': str(form.get('data_source') or 'synthetic').strip() or 'synthetic',
        'tags': _split_csv_field(str(form.get('tags_csv') or '')),
        'expected_tools': _split_csv_field(str(form.get('expected_tools_csv') or '')),
        'mandatory_tools': _split_csv_field(str(form.get('mandatory_tools_csv') or '')),
        'forbidden_tools': _split_csv_field(str(form.get('forbidden_tools_csv') or '')),
        'sequence_matcher': str(form.get('sequence_matcher') or 'subsequence').strip() or 'subsequence',
        'available_tools': available_tools,
        'expected_args': _parse_json_object_field(str(form.get('expected_args_json') or ''), field_name='expected_args'),
        'expected_tool_sequence': _parse_json_list_field(
            str(form.get('expected_tool_sequence_json') or ''),
            field_name='expected_tool_sequence',
        ),
        'chain_assertions': _parse_json_list_field(
            str(form.get('chain_assertions_json') or ''),
            field_name='chain_assertions',
        ),
        'expected_observation_contains': _parse_json_object_field(
            str(form.get('expected_observation_contains_json') or ''),
            field_name='expected_observation_contains',
        ),
        'metadata': metadata,
    }
    return AgentToolEvalCase.from_obj(case_obj).to_dict()


_CASE_EDITOR_ACTIVE_SCOPE = 'case_editor_active_scope'
_CASE_EDITOR_CASES_KEY = 'case_editor_cases_state_key'
_CASES_SELECTED_CASE_WIDGET_KEY = 'cases_selected_case_id'
_CASES_SELECT_PENDING_KEY = 'cases_select_pending_case_id'


def apply_pending_case_selection(session: MutableMapping[str, Any]) -> None:
    """Apply a queued case id before the selectbox widget is drawn."""
    pending = session.pop(_CASES_SELECT_PENDING_KEY, None)
    if pending is not None:
        session[_CASES_SELECTED_CASE_WIDGET_KEY] = pending


def queue_case_selection(session: MutableMapping[str, Any], case_id: str) -> None:
    """Queue case selection for the next rerun (after widget-bound keys exist)."""
    session[_CASES_SELECT_PENDING_KEY] = case_id
    session.pop(_CASE_EDITOR_ACTIVE_SCOPE, None)


def case_editor_scope(*, cases_state_key: str, selected_case_id: str) -> str:
    return f'{cases_state_key}::{selected_case_id or "__new__"}'


def case_editor_widget_keys(scope: str) -> Dict[str, str]:
    base = f'case_edit::{scope}::'
    return {
        'example_id': f'{base}example_id',
        'agent_id': f'{base}agent_id',
        'data_source': f'{base}data_source',
        'user_message': f'{base}user_message',
        'context_snapshot': f'{base}context_snapshot',
        'language': f'{base}language',
        'intent': f'{base}intent',
        'dataset_tier': f'{base}dataset_tier',
        'dataset_version': f'{base}dataset_version',
        'case_owner': f'{base}case_owner',
        'aico_new_dialogue': f'{base}aico_new_dialogue',
        'sequence_matcher': f'{base}sequence_matcher',
        'tags_csv': f'{base}tags_csv',
        'expected_tools_csv': f'{base}expected_tools_csv',
        'mandatory_tools_csv': f'{base}mandatory_tools_csv',
        'forbidden_tools_csv': f'{base}forbidden_tools_csv',
        'available_tools_seed': f'{base}available_tools_seed',
        'available_tools': f'{base}available_tools',
        'expected_args_json': f'{base}expected_args_json',
        'expected_tool_sequence_json': f'{base}expected_tool_sequence_json',
        'chain_assertions_json': f'{base}chain_assertions_json',
        'expected_observation_contains_json': f'{base}expected_observation_contains_json',
        'raw_json': f'{base}raw_json',
    }


def hydrate_case_editor_payload(
    form_state: Mapping[str, Any],
    *,
    scope: str,
    session: Dict[str, Any],
    raw_case: Optional[Mapping[str, Any]] = None,
) -> None:
    """Load case fields into session-backed widget keys (call when selection/scope changes)."""
    keys = case_editor_widget_keys(scope)
    session[keys['example_id']] = str(form_state.get('example_id') or '')
    session[keys['agent_id']] = str(form_state.get('agent_id') or 'aico')
    session[keys['data_source']] = str(form_state.get('data_source') or 'synthetic')
    session[keys['user_message']] = str(form_state.get('user_message') or '')
    session[keys['context_snapshot']] = str(form_state.get('context_snapshot') or '')
    session[keys['language']] = str(form_state.get('language') or '')
    session[keys['intent']] = str(form_state.get('intent') or '')
    session[keys['dataset_tier']] = str(form_state.get('dataset_tier') or '')
    session[keys['dataset_version']] = str(form_state.get('dataset_version') or '')
    session[keys['case_owner']] = str(form_state.get('case_owner') or 'agent-runtime')
    session[keys['aico_new_dialogue']] = bool(form_state.get('aico_new_dialogue'))
    session[keys['sequence_matcher']] = str(form_state.get('sequence_matcher') or 'subsequence')
    session[keys['tags_csv']] = str(form_state.get('tags_csv') or '')
    session[keys['expected_tools_csv']] = str(form_state.get('expected_tools_csv') or '')
    session[keys['mandatory_tools_csv']] = str(form_state.get('mandatory_tools_csv') or '')
    session[keys['forbidden_tools_csv']] = str(form_state.get('forbidden_tools_csv') or '')
    tool_rows = form_state.get('available_tools_rows') if isinstance(form_state.get('available_tools_rows'), list) else []
    session[keys['available_tools_seed']] = list(tool_rows) if tool_rows else [{'name': '', 'description': ''}]
    session.pop(keys['available_tools'], None)
    session[keys['expected_args_json']] = str(form_state.get('expected_args_json') or '{}')
    session[keys['expected_tool_sequence_json']] = str(form_state.get('expected_tool_sequence_json') or '[]')
    session[keys['chain_assertions_json']] = str(form_state.get('chain_assertions_json') or '[]')
    session[keys['expected_observation_contains_json']] = str(form_state.get('expected_observation_contains_json') or '{}')
    raw_source = raw_case if raw_case is not None else form_state
    session[keys['raw_json']] = json.dumps(dict(raw_source), ensure_ascii=False, indent=2)


def read_case_editor_payload(scope: str, session: Mapping[str, Any]) -> Dict[str, Any]:
    """Read current editor widget values from session state."""
    keys = case_editor_widget_keys(scope)

    def _tools_rows() -> List[Dict[str, Any]]:
        raw = session.get(keys['available_tools'])
        if raw is None:
            raw = session.get(keys['available_tools_seed'])
        if hasattr(raw, 'to_dict'):
            raw = raw.to_dict('records')
        if not isinstance(raw, list):
            return []
        return [dict(x) for x in raw if isinstance(x, Mapping)]

    return {
        'example_id': str(session.get(keys['example_id']) or ''),
        'agent_id': str(session.get(keys['agent_id']) or 'aico'),
        'data_source': str(session.get(keys['data_source']) or 'synthetic'),
        'user_message': str(session.get(keys['user_message']) or ''),
        'context_snapshot': str(session.get(keys['context_snapshot']) or ''),
        'language': str(session.get(keys['language']) or ''),
        'intent': str(session.get(keys['intent']) or ''),
        'dataset_tier': str(session.get(keys['dataset_tier']) or ''),
        'dataset_version': str(session.get(keys['dataset_version']) or ''),
        'case_owner': str(session.get(keys['case_owner']) or 'agent-runtime'),
        'aico_new_dialogue': bool(session.get(keys['aico_new_dialogue'])),
        'sequence_matcher': str(session.get(keys['sequence_matcher']) or 'subsequence'),
        'tags_csv': str(session.get(keys['tags_csv']) or ''),
        'expected_tools_csv': str(session.get(keys['expected_tools_csv']) or ''),
        'mandatory_tools_csv': str(session.get(keys['mandatory_tools_csv']) or ''),
        'forbidden_tools_csv': str(session.get(keys['forbidden_tools_csv']) or ''),
        'available_tools_rows': _tools_rows(),
        'expected_args_json': str(session.get(keys['expected_args_json']) or ''),
        'expected_tool_sequence_json': str(session.get(keys['expected_tool_sequence_json']) or ''),
        'chain_assertions_json': str(session.get(keys['chain_assertions_json']) or ''),
        'expected_observation_contains_json': str(session.get(keys['expected_observation_contains_json']) or ''),
        'raw_json': str(session.get(keys['raw_json']) or ''),
    }


def ensure_case_editor_hydrated(
    *,
    scope: str,
    form_state: Mapping[str, Any],
    session: Dict[str, Any],
    raw_case: Optional[Mapping[str, Any]] = None,
    force: bool = False,
) -> None:
    if force or session.get(_CASE_EDITOR_ACTIVE_SCOPE) != scope:
        hydrate_case_editor_payload(form_state, scope=scope, session=session, raw_case=raw_case)
        session[_CASE_EDITOR_ACTIVE_SCOPE] = scope


def run_eval_from_streamlit(
    *,
    config_path: Path,
    adapter_name: Optional[str]=None,
    suite: str='gate',
    cases_path: Optional[Path]=None,
    out_path: Optional[Path]=None,
    report_path: Optional[Path]=None,
    enforce_gates: bool=True,
    skip_dataset_governance: bool=False,
) -> Dict[str, Any]:
    cfg = load_eval_config(config_path)
    adapter_name = adapter_name or cfg.adapter
    chosen_cases_path = cases_path or resolve_cases_path_for_suite(cfg, suite)
    out_path = out_path or cfg.pairs_path
    report_path = report_path or cfg.report_path
    if cases_path:
        chosen_cases_path = _validate_in_backend_root(cases_path, 'cases')
    if out_path:
        out_path = _validate_in_backend_root(out_path, 'out')
    if report_path:
        report_path = _validate_in_backend_root(report_path, 'report')
    if not skip_dataset_governance:
        validate_case_governance(load_cases_jsonl(chosen_cases_path), expected_suite=suite, config=cfg)
    adapter = adapter_by_name(adapter_name, config=cfg)
    from app.game_engine.agent_runtime.eval.runner import run_eval as _run_eval

    pairs = _run_eval(config=cfg, adapter_name=adapter_name, cases_path=chosen_cases_path, adapter=adapter)
    write_jsonl(out_path, [p.to_dict() for p in pairs])
    report = build_report(
        pairs,
        adapter=adapter_name,
        mode='live',
        live_gate_thresholds=cfg.gate_policy.live,
    )
    write_report(report_path, report)
    gate_enforced = cfg.gate_policy.enforce and enforce_gates
    (gate_passed, gate_failures) = evaluate_report_gates(report, mode='live', tolerance=cfg.gate_policy.tolerance)
    exit_code = 0
    if gate_enforced and not report_passes_initial_gates(report, tolerance=cfg.gate_policy.tolerance):
        exit_code = 2
    _configure_streamlit_eval_logging()
    return {
        'exit_code': exit_code,
        'pairs': len(pairs),
        'suite': suite,
        'cases_path': str(chosen_cases_path),
        'out_path': str(out_path),
        'report_path': str(report_path),
        'gate_enforced': gate_enforced,
        'gate_passed': gate_passed,
        'gate_failures': gate_failures,
    }


def pair_rows(pairs: Iterable[EvalPair]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in pairs:
        failed = [s.name for s in p.scores if not s.passed]
        rows.append({
            'example_id': p.case.example_id,
            'verdict': p.verdict,
            'status': p.correction.status,
            'user_message': p.case.user_message,
            'expected_tools': ','.join(p.case.expected_tools),
            'mandatory_tools': ','.join(p.case.mandatory_tools),
            'predicted_tools': ','.join(p.prediction.predicted_tools),
            'failure_reasons': ','.join(failed),
            'tags': ','.join(p.case.tags),
            'data_source': p.case.data_source,
            'language': p.case.language,
        })
    return rows


def filter_pairs(pairs: Iterable[EvalPair], *, verdict: str='', tool: str='', failure_reason: str='', tag: str='') -> List[EvalPair]:
    out: List[EvalPair] = []
    for p in pairs:
        if verdict and p.verdict != verdict:
            continue
        tools = set(p.case.expected_tools) | set(p.case.mandatory_tools) | set(p.prediction.predicted_tools)
        if tool and tool not in tools:
            continue
        failures = {s.name for s in p.scores if not s.passed}
        if failure_reason and failure_reason not in failures:
            continue
        if tag and tag not in set(p.case.tags):
            continue
        out.append(p)
    return out


def export_corrected_pairs(path: Path, pairs: Iterable[EvalPair]) -> None:
    write_jsonl(path, [p.to_dict() for p in pairs])


def ssh_eval_prerequisites(aico_cfg: AicoEvalRuntimeConfig) -> Dict[str, Any]:
    """Check whether SSH-backed live eval can run in the current environment."""
    invoke_via = str(aico_cfg.invoke_via or 'ssh').strip().lower()
    if invoke_via != 'ssh':
        return {
            'ready': True,
            'invoke_via': invoke_via,
            'password_env': aico_cfg.ssh_password_env,
            'message': 'Non-SSH invoke_via; SSH password env is not required.',
        }
    env_name = str(aico_cfg.ssh_password_env or 'AICO_EVAL_SSH_PASSWORD')
    ready = bool(os.environ.get(env_name, '').strip())
    return {
        'ready': ready,
        'invoke_via': invoke_via,
        'password_env': env_name,
        'message': (
            f'{env_name} is set.'
            if ready
            else f'Set {env_name} in your shell before clicking Run eval now.'
        ),
    }


def promote_corrected_to_regression(*, corrected_pairs_path: Path, regression_cases_path: Path) -> int:
    """Promote reviewed pairs from corrected_pairs.jsonl into regression cases JSONL."""
    pairs = load_pairs_jsonl(corrected_pairs_path)
    cases = promoted_cases_from_pairs(pairs)
    write_jsonl(regression_cases_path, [c.to_dict() for c in cases])
    return len(cases)


def prediction_trace_panels(prediction: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract trace panels for Streamlit display."""
    metadata = prediction.get('metadata') if isinstance(prediction.get('metadata'), Mapping) else {}
    metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    return {
        'command_line': metadata.get('command_line'),
        'invoke_via': metadata.get('invoke_via'),
        'command_success': metadata.get('command_success'),
        'command_error': metadata.get('command_error'),
        'elapsed_ms': metadata.get('elapsed_ms'),
        'passthrough_suspected': metadata.get('passthrough_suspected'),
        'db_trace': metadata.get('db_trace'),
        'ssh': metadata.get('ssh'),
        'trace': prediction.get('trace') or [],
        'scores_hint': 'See Scores section below.',
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='AICO Live Tool Eval Streamlit report')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument('--pairs', type=Path, default=None)
    parser.add_argument('--report', type=Path, default=None)
    parser.add_argument('--export', type=Path, default=None)
    return parser.parse_args()


def main() -> None:  # pragma: no cover - exercised manually with Streamlit.
    _configure_streamlit_eval_logging()
    args = _parse_args()
    cfg = load_eval_config(args.config)
    pairs_path = args.pairs or cfg.pairs_path
    report_path = args.report or cfg.report_path
    export_path = args.export or cfg.corrected_pairs_path

    import pandas as pd
    import plotly.express as px
    import streamlit as st

    data = load_dashboard_data(pairs_path=pairs_path, report_path=report_path)
    pairs: List[EvalPair] = data['pairs']
    report = data['report']
    st.set_page_config(page_title='AICO Live Tool Eval', layout='wide')
    st.title('AICO Live Tool Eval')
    st.caption('Default workspace: edit cases, run live eval, analyze results, review, and promote.')
    st.caption(f'Config: {cfg.config_path}')

    prereq = ssh_eval_prerequisites(cfg.aico)
    if prereq['ready']:
        st.success(prereq['message'])
    else:
        st.warning(prereq['message'])

    st.subheader('1. Run Evaluation')
    suite_options = sorted(cfg.cases_by_suite.keys())
    run_c1, run_c2, run_c3 = st.columns(3)
    selected_suite = run_c1.selectbox(
        'Suite',
        suite_options,
        index=suite_options.index('gate') if 'gate' in suite_options else 0,
        key='run_suite',
    )
    custom_cases_path = run_c2.text_input('Cases path override (optional)', key='run_cases_path')
    custom_out_path = run_c3.text_input('Pairs output override (optional)', key='run_out_path')
    run_c4, run_c5, run_c6 = st.columns(3)
    custom_report_path = run_c4.text_input('Report output override (optional)', key='run_report_path')
    enforce_gates = run_c5.checkbox('Enforce gates', value=True, key='run_enforce_gates')
    skip_dataset_governance = run_c6.checkbox('Skip dataset governance', value=False, key='run_skip_governance')
    if st.button('Run eval now', type='primary', key='run_eval_now'):
        with st.spinner('Running live eval...'):
            try:
                payload = run_eval_from_streamlit(
                    config_path=cfg.config_path,
                    adapter_name=cfg.adapter,
                    suite=selected_suite,
                    cases_path=Path(custom_cases_path).expanduser() if custom_cases_path.strip() else None,
                    out_path=Path(custom_out_path).expanduser() if custom_out_path.strip() else None,
                    report_path=Path(custom_report_path).expanduser() if custom_report_path.strip() else None,
                    enforce_gates=enforce_gates,
                    skip_dataset_governance=skip_dataset_governance,
                )
            except Exception as exc:  # pragma: no cover - streamlit runtime flow
                st.error(f'Eval run failed: {exc}')
            else:
                if payload['exit_code'] != 0:
                    st.warning(f"Eval completed, but gate checks failed (exit={payload['exit_code']}).")
                    failures = payload.get('gate_failures') or []
                    if failures:
                        st.caption('Failed gate metrics')
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        'metric': str(item.get('metric') or ''),
                                        'value': item.get('value'),
                                        'op': str(item.get('op') or ''),
                                        'target': item.get('target'),
                                    }
                                    for item in failures
                                ]
                            ),
                            width='stretch',
                        )
                else:
                    st.success(f"Eval completed: {payload['pairs']} pairs.")
                st.json(payload)
                pairs_path = Path(payload['out_path'])
                report_path = Path(payload['report_path'])
                data = load_dashboard_data(pairs_path=pairs_path, report_path=report_path)
                pairs = data['pairs']
                report = data['report']

    st.subheader('2. Results Overview')
    left, mid, right = st.columns(3)
    left.metric('Pairs', report.get('n_pairs', len(pairs)))
    mid.metric('Pass rate', f"{float(report.get('pass_rate', 0.0)):.1%}")
    right.metric('Mode', str(report.get('mode', 'live')))

    rows = pair_rows(pairs)
    df = pd.DataFrame(rows)
    if not df.empty:
        st.subheader('3. Failure Distribution')
        failures = df['failure_reasons'].str.split(',').explode()
        failures = failures[failures != '']
        if not failures.empty:
            st.plotly_chart(px.histogram(failures, x='failure_reasons'), width='stretch')

    st.subheader('4. Pair Browser')
    c1, c2, c3, c4 = st.columns(4)
    verdict = c1.selectbox('Verdict', ['', 'pass', 'fail'], key='pairs_verdict')
    tool = c2.text_input('Tool', key='pairs_tool')
    failure = c3.text_input('Failure reason', key='pairs_failure_reason')
    tag = c4.text_input('Tag', key='pairs_tag')
    visible = filter_pairs(pairs, verdict=verdict, tool=tool, failure_reason=failure, tag=tag)
    st.dataframe(pd.DataFrame(pair_rows(visible)), width='stretch')

    st.subheader('5. Trace Viewer')
    ids = [p.case.example_id for p in visible]
    selected_id = st.selectbox('Example', ids, key='trace_example_id') if ids else None
    selected = next((p for p in visible if p.case.example_id == selected_id), None)
    if selected:
        st.write(selected.case.user_message)
        pred_dict = selected.prediction.to_dict()
        panels = prediction_trace_panels(pred_dict)
        t1, t2, t3 = st.columns(3)
        t1.metric('Command success', str(panels.get('command_success')))
        t2.metric('Invoke via', str(panels.get('invoke_via') or ''))
        t3.metric('Elapsed ms', str(panels.get('elapsed_ms') or ''))
        st.code(str(panels.get('command_line') or ''), language='bash')
        st.markdown('**DB trace**')
        st.json(panels.get('db_trace') or {})
        st.markdown('**Normalized trace events**')
        st.json(panels.get('trace') or [])
        st.markdown('**Scores**')
        st.json([s.to_dict() for s in selected.scores])
        with st.expander('Full prediction JSON', expanded=False):
            st.json(pred_dict)

    st.subheader('6. Review And Promote')
    st.caption(
        'Update review status below, export to corrected_pairs.jsonl, then promote into regression cases. '
        f'Export path: {export_path}'
    )
    edited = st.data_editor(pd.DataFrame(pair_rows(pairs)), width='stretch', num_rows='fixed', key='review_pairs_editor')
    status_by_id = {str(r['example_id']): str(r.get('status') or 'unreviewed') for r in edited.to_dict('records')} if not edited.empty else {}
    for p in pairs:
        if p.case.example_id in status_by_id:
            p.correction.status = status_by_id[p.case.example_id]
    rev_c1, rev_c2 = st.columns(2)
    if rev_c1.button('Export corrected pairs', key='review_export_corrected'):
        export_corrected_pairs(export_path, pairs)
        st.success(f'Wrote {export_path}')
    if rev_c2.button('Promote corrected pairs to regression', key='review_promote_regression'):
        try:
            if not export_path.exists():
                st.warning(f'Export corrected pairs first: {export_path}')
            else:
                count = promote_corrected_to_regression(
                    corrected_pairs_path=export_path,
                    regression_cases_path=cfg.regression_cases_path,
                )
                st.success(f'Wrote {count} regression cases to {cfg.regression_cases_path}')
        except Exception as exc:  # pragma: no cover - streamlit runtime flow
            st.error(f'Promote failed: {exc}')

    st.subheader('7. Case Dataset Query & Editor')
    cases_default_path = cfg.cases_by_suite.get(selected_suite, cfg.cases_path)
    cases_path_input = st.text_input('Cases JSONL path', value=str(cases_default_path), key='cases_jsonl_path')
    cases_path_raw = Path(cases_path_input).expanduser()
    cases_path_resolved = cases_path_raw.resolve()
    try:
        cases_path_resolved.relative_to(BACKEND_ROOT.resolve())
    except ValueError:
        st.error(f'Path escapes backend root: {cases_path_input}')
        st.session_state[f'cases::{cases_path_input}'] = []
        st.stop()
        cases_path = cases_path_resolved  # unreachable; satisfies type checker
    cases_path = cases_path_resolved
    load_cases_clicked = st.button('Reload cases from disk', key='cases_load')
    state_key = f'cases::{cases_path}'
    if st.session_state.get(_CASE_EDITOR_CASES_KEY) != state_key:
        st.session_state[_CASE_EDITOR_CASES_KEY] = state_key
        st.session_state.pop(_CASE_EDITOR_ACTIVE_SCOPE, None)
    if load_cases_clicked or state_key not in st.session_state:
        try:
            st.session_state[state_key] = load_cases_rows(cases_path)
            st.session_state.pop(_CASE_EDITOR_ACTIVE_SCOPE, None)
        except Exception as exc:  # pragma: no cover - streamlit runtime flow
            st.error(f'Load cases failed: {exc}')
            st.session_state[state_key] = []
    cases_rows_state: List[Dict[str, Any]] = st.session_state.get(state_key, [])

    q1, q2, q3, q4 = st.columns(4)
    q_text = q1.text_input('Query', key='cases_query')
    q_intent = q2.text_input('Intent', key='cases_intent')
    q_tag = q3.text_input('Tag', key='cases_tag')
    q_lang = q4.text_input('Language', key='cases_language')
    filtered_cases = filter_cases(cases_rows_state, q=q_text, intent=q_intent, tag=q_tag, language=q_lang)
    st.dataframe(pd.DataFrame(case_rows(filtered_cases)), width='stretch')

    pick_c1, pick_c2 = st.columns([3, 1])
    selected_case_ids = ['__new__'] + [str(c.get('example_id') or '') for c in filtered_cases]
    apply_pending_case_selection(st.session_state)
    with pick_c1:
        selected_case_id = st.selectbox(
            'Case to edit',
            selected_case_ids,
            key=_CASES_SELECTED_CASE_WIDGET_KEY,
        )
    with pick_c2:
        if st.button('New case', key='cases_new_case'):
            queue_case_selection(st.session_state, '__new__')
            st.rerun()

    if selected_case_id == '__new__':
        initial_case = new_case_template(default_suite=selected_suite)
    else:
        initial_case = next(
            (c for c in cases_rows_state if str(c.get('example_id') or '') == selected_case_id),
            new_case_template(default_suite=selected_suite),
        )
    form_state = case_to_form_state(initial_case, default_suite=selected_suite)
    editor_scope = case_editor_scope(cases_state_key=state_key, selected_case_id=selected_case_id)
    ensure_case_editor_hydrated(
        scope=editor_scope,
        form_state=form_state,
        session=st.session_state,
        raw_case=initial_case,
    )
    widget_keys = case_editor_widget_keys(editor_scope)

    intent_options = ['', 'execute', 'informational', 'verify_state', 'list', 'count', 'inspect', 'inspect_space', 'help_then_execute']
    language_options = ['', 'en', 'zh']
    sequence_options = ['subsequence', 'exact']
    tier_options = sorted({selected_suite, *cfg.cases_by_suite.keys(), form_state['dataset_tier']})
    tier_options = [x for i, x in enumerate(tier_options) if x and x not in tier_options[:i]]

    st.markdown('#### Case Form Editor')
    st.caption('Fields reload when you change **Case to edit** or click **New case**. Save writes to the JSONL path above.')

    id_c1, id_c2, id_c3 = st.columns(3)
    id_c1.text_input('Example ID', key=widget_keys['example_id'])
    id_c2.text_input('Agent ID', key=widget_keys['agent_id'])
    id_c3.text_input('Data source', key=widget_keys['data_source'])
    st.text_area('User message', height=100, key=widget_keys['user_message'])
    st.text_area('Context snapshot', height=80, key=widget_keys['context_snapshot'])
    meta_c1, meta_c2, meta_c3, meta_c4 = st.columns(4)
    meta_c1.selectbox('Language', language_options, key=widget_keys['language'])
    meta_c2.selectbox('Intent', intent_options, key=widget_keys['intent'])
    meta_c3.selectbox('Dataset tier', tier_options, key=widget_keys['dataset_tier'])
    meta_c4.text_input('Dataset version', key=widget_keys['dataset_version'])
    gov_c1, gov_c2, gov_c3 = st.columns(3)
    gov_c1.text_input('Case owner', key=widget_keys['case_owner'])
    gov_c2.checkbox('AICO new dialogue (-nd)', key=widget_keys['aico_new_dialogue'])
    gov_c3.selectbox('Sequence matcher', sequence_options, key=widget_keys['sequence_matcher'])
    tool_c1, tool_c2, tool_c3, tool_c4 = st.columns(4)
    tool_c1.text_input('Tags (comma-separated)', key=widget_keys['tags_csv'])
    tool_c2.text_input('Expected tools', key=widget_keys['expected_tools_csv'])
    tool_c3.text_input('Mandatory tools', key=widget_keys['mandatory_tools_csv'])
    tool_c4.text_input('Forbidden tools', key=widget_keys['forbidden_tools_csv'])
    st.caption('Available tools')
    tools_seed = st.session_state.get(widget_keys['available_tools_seed']) or [{'name': '', 'description': ''}]
    st.data_editor(
        pd.DataFrame(tools_seed),
        width='stretch',
        num_rows='dynamic',
        key=widget_keys['available_tools'],
        column_config={
            'name': st.column_config.TextColumn('Tool name', required=True),
            'description': st.column_config.TextColumn('Description'),
        },
    )
    with st.expander('Assertions (JSON)', expanded=False):
        st.text_area('expected_args', height=120, key=widget_keys['expected_args_json'])
        st.text_area('expected_tool_sequence', height=120, key=widget_keys['expected_tool_sequence_json'])
        st.text_area('chain_assertions', height=120, key=widget_keys['chain_assertions_json'])
        st.text_area('expected_observation_contains', height=100, key=widget_keys['expected_observation_contains_json'])

    act_c1, act_c2, act_c3 = st.columns(3)
    validate_clicked = act_c1.button('Validate case', key='cases_validate_case')
    save_clicked = act_c2.button('Save case (upsert)', type='primary', key='cases_save_case')
    reload_editor_clicked = act_c3.button('Reset form from disk', key='cases_reset_editor')

    if reload_editor_clicked:
        ensure_case_editor_hydrated(
            scope=editor_scope,
            form_state=form_state,
            session=st.session_state,
            raw_case=initial_case,
            force=True,
        )
        st.success('Form reset from loaded case.')

    form_payload = read_case_editor_payload(editor_scope, st.session_state)

    if validate_clicked or save_clicked:
        try:
            parsed_case = build_case_from_form_state(
                form_payload,
                base_case=initial_case,
                default_suite=selected_suite,
            )
        except Exception as exc:  # pragma: no cover - streamlit runtime flow
            st.error(f'Case validation failed: {exc}')
        else:
            try:
                validate_case_dict_governance(parsed_case, suite=selected_suite, config=cfg)
            except Exception as exc:  # pragma: no cover - streamlit runtime flow
                st.error(f'Dataset governance check failed: {exc}')
            else:
                if validate_clicked:
                    st.success('Case form is valid.')
                if save_clicked:
                    updated = upsert_case(cases_rows_state, parsed_case)
                    write_jsonl(cases_path, updated)
                    st.session_state[state_key] = updated
                    new_id = str(parsed_case['example_id'])
                    queue_case_selection(st.session_state, new_id)
                    st.success(f'Saved case `{new_id}` to {cases_path}')
                    st.rerun()

    with st.expander('Advanced JSON editor', expanded=False):
        st.text_area('Raw case JSON', height=280, key=widget_keys['raw_json'])
        adv_c1, adv_c2 = st.columns(2)
        if adv_c1.button('Validate raw JSON', key='cases_validate_raw_json'):
            try:
                parsed_raw = json.loads(str(st.session_state.get(widget_keys['raw_json']) or ''))
                AgentToolEvalCase.from_obj(parsed_raw)
                validate_case_dict_governance(parsed_raw, suite=selected_suite, config=cfg)
            except Exception as exc:  # pragma: no cover - streamlit runtime flow
                st.error(f'Validation failed: {exc}')
            else:
                st.success('Raw JSON is valid.')
        if adv_c2.button('Save raw JSON (upsert)', key='cases_save_raw_json'):
            try:
                parsed = json.loads(str(st.session_state.get(widget_keys['raw_json']) or ''))
                AgentToolEvalCase.from_obj(parsed)
                validate_case_dict_governance(parsed, suite=selected_suite, config=cfg)
                updated = upsert_case(cases_rows_state, parsed)
                write_jsonl(cases_path, updated)
                st.session_state[state_key] = updated
                queue_case_selection(st.session_state, str(parsed.get('example_id') or ''))
                st.success(f'Saved raw JSON case to {cases_path}')
                st.rerun()
            except Exception as exc:  # pragma: no cover - streamlit runtime flow
                st.error(f'Save failed: {exc}')

    if st.button('Delete selected case', key='cases_delete_selected'):
        if selected_case_id == '__new__':
            st.warning('Please select an existing case.')
        else:
            updated = delete_case(cases_rows_state, selected_case_id)
            write_jsonl(cases_path, updated)
            st.session_state[state_key] = updated
            queue_case_selection(st.session_state, '__new__')
            st.success(f'Deleted {selected_case_id}')
            st.rerun()


if __name__ == '__main__':
    main()

