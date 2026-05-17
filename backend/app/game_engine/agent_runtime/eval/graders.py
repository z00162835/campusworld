"""Deterministic graders for agent tool-use eval pairs."""
from __future__ import annotations

import re
from typing import Dict, List, Sequence, Set

from app.game_engine.agent_runtime.eval.schema import (
    AgentToolEvalCase,
    EvalPrediction,
    ExpectedToolCall,
    ScoreResult,
    TraceEvent,
)

_KNOWN_EMPTY_REPLY_FALLBACKS = (
    '抱歉，我没有能力处理此问题。你可以换一个问题。',
    '我这边暂时无法处理，请再描述一下你的目标。',
)


def grade_prediction(case: AgentToolEvalCase, prediction: EvalPrediction) -> List[ScoreResult]:
    scores = [
        _grade_live_trace_presence(prediction),
        _grade_final_reply_after_tool(prediction),
        _grade_expected_tools(case, prediction),
        _grade_mandatory_tools(case, prediction),
        _grade_forbidden_tools(case, prediction),
        _grade_tool_sequence(case, prediction),
        _grade_chain_assertions(case, prediction),
        _grade_expected_args(case, prediction),
        _grade_observation_evidence(case, prediction),
        _grade_illegal_tools(case, prediction),
        _grade_schema_violations(prediction),
        _grade_budget_and_permission(prediction),
    ]
    return scores


def verdict_from_scores(scores: Sequence[ScoreResult]) -> str:
    return 'pass' if all(s.passed for s in scores) else 'fail'


def _called_tools(prediction: EvalPrediction) -> Set[str]:
    names = {n for n in _normalize_names(prediction.predicted_tools)}
    names.update(_normalize_names([c.name for c in prediction.tool_calls]))
    names.update(_normalize_names([e.tool_name for e in prediction.trace if e.event_type in {'tool_exec', 'tool_observation'}]))
    return names


def _executed_tools(prediction: EvalPrediction) -> Set[str]:
    return set(_normalize_names([e.tool_name for e in prediction.trace if e.event_type == 'tool_exec' and e.ok is not False]))


def _grade_live_trace_presence(prediction: EvalPrediction) -> ScoreResult:
    metadata = prediction.metadata or {}
    if metadata.get('mode') != 'live' or metadata.get('adapter') != 'aico':
        return ScoreResult('live_trace_presence', True, 1.0, 'not an AICO live prediction')
    if metadata.get('require_db_trace') is False:
        return ScoreResult('live_trace_presence', True, 1.0, 'DB trace requirement disabled')
    db_trace = metadata.get('db_trace') if isinstance(metadata.get('db_trace'), dict) else {}
    found = bool(db_trace.get('found'))
    missing_events = [e for e in prediction.trace if e.event_type == 'live_trace_missing']
    return ScoreResult(
        'live_trace_presence',
        found and not missing_events,
        1.0 if found and not missing_events else 0.0,
        'AICO DB trace found' if found and not missing_events else 'AICO live command did not produce DB trace',
        {
            'found': found,
            'correlation_id': metadata.get('correlation_id') or db_trace.get('correlation_id'),
            'passthrough_suspected': bool(metadata.get('passthrough_suspected')),
            'elapsed_ms': metadata.get('elapsed_ms'),
        },
    )


def _grade_final_reply_after_tool(prediction: EvalPrediction) -> ScoreResult:
    """Fail when tools executed but final reply is empty/fallback."""
    observed_events = [
        e for e in prediction.trace
        if e.event_type in {'tool_exec', 'tool_observation'} and e.ok is not False
    ]
    if not observed_events:
        return ScoreResult(
            'final_reply_after_tool',
            True,
            1.0,
            'no successful tool observations; gate not applicable',
            {'observed_tool_count': 0},
        )
    final_reply = str(prediction.final_reply or '').strip()
    reasons: List[str] = []
    if not final_reply:
        reasons.append('final_reply_empty')
    if final_reply in _KNOWN_EMPTY_REPLY_FALLBACKS:
        reasons.append('known_fallback_reply')
    if any(e.event_type == 'empty_reply_fallback' for e in prediction.trace):
        reasons.append('trace_empty_reply_fallback')
    passed = not reasons
    observed_tools = sorted({e.tool_name for e in observed_events if e.tool_name})
    return ScoreResult(
        'final_reply_after_tool',
        passed,
        1.0 if passed else 0.0,
        'final reply present after tool observations' if passed else 'tool observations exist but final reply is empty/fallback',
        {
            'observed_tool_count': len(observed_events),
            'observed_tools': observed_tools,
            'final_reply_chars': len(final_reply),
            'reasons': reasons,
        },
    )


def _available_tools(case: AgentToolEvalCase) -> Set[str]:
    return set(_normalize_names([t.name for t in case.available_tools]))


def _grade_expected_tools(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    expected = set(_normalize_names(case.expected_tools))
    if not expected:
        return ScoreResult('expected_tools', True, 1.0, 'no expected tools specified')
    called = _called_tools(prediction)
    missing = sorted(expected - called)
    return ScoreResult(
        'expected_tools',
        not missing,
        1.0 if not missing else 0.0,
        'all expected tools present' if not missing else 'missing expected tools',
        {'missing': missing, 'expected': sorted(expected), 'called': sorted(called)},
    )


def _grade_mandatory_tools(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    mandatory = set(_normalize_names(case.mandatory_tools))
    if not mandatory:
        return ScoreResult('mandatory_observation', True, 1.0, 'no mandatory tools specified')
    observed = set(_normalize_names([
        e.tool_name
        for e in prediction.trace
        if e.event_type in {'tool_observation', 'tool_exec'} and e.ok is not False
    ]))
    missing = sorted(mandatory - observed)
    return ScoreResult(
        'mandatory_observation',
        not missing,
        1.0 if not missing else 0.0,
        'mandatory observations present' if not missing else 'missing mandatory observations',
        {'missing': missing, 'mandatory': sorted(mandatory), 'observed': sorted(observed)},
    )


def _grade_forbidden_tools(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    forbidden = set(_normalize_names(case.forbidden_tools))
    if not forbidden:
        return ScoreResult('forbidden_tools', True, 1.0, 'no forbidden tools specified')
    called = _called_tools(prediction)
    violations = sorted(forbidden & called)
    return ScoreResult(
        'forbidden_tools',
        not violations,
        1.0 if not violations else 0.0,
        'no forbidden tools called' if not violations else 'forbidden tools called',
        {'violations': violations},
    )


def _grade_tool_sequence(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    expected = list(case.expected_tool_sequence or [])
    if not expected:
        return ScoreResult('tool_sequence', True, 1.0, 'no expected tool sequence specified')
    actual = [
        ExpectedToolCall(name=e.tool_name, args=list(e.args))
        for e in prediction.trace
        if e.event_type == 'tool_exec' and e.tool_name
    ]
    matcher = (case.sequence_matcher or 'subsequence').lower()
    if matcher == 'exact':
        passed = len(actual) == len(expected) and all(_args_match(e, a) for (e, a) in zip(expected, actual))
        return ScoreResult(
            'tool_sequence',
            passed,
            1.0 if passed else 0.0,
            'exact tool sequence matched' if passed else 'exact tool sequence mismatch',
            {'expected': [_call_dict(c) for c in expected], 'actual': [_call_dict(c) for c in actual], 'matcher': matcher},
        )
    positions: List[int] = []
    cursor = 0
    for exp in expected:
        found = -1
        for i in range(cursor, len(actual)):
            if _args_match(exp, actual[i]):
                found = i
                break
        if found < 0:
            return ScoreResult(
                'tool_sequence',
                False,
                0.0,
                'expected tool sequence not found',
                {'expected': [_call_dict(c) for c in expected], 'actual': [_call_dict(c) for c in actual], 'matcher': matcher, 'matched_positions': positions, 'missing': _call_dict(exp)},
            )
        positions.append(found)
        cursor = found + 1
    return ScoreResult(
        'tool_sequence',
        True,
        1.0,
        'tool sequence matched as subsequence',
        {'expected': [_call_dict(c) for c in expected], 'actual': [_call_dict(c) for c in actual], 'matcher': matcher, 'matched_positions': positions},
    )


def _grade_chain_assertions(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    assertions = list(case.chain_assertions or [])
    if not assertions:
        return ScoreResult('chain_assertions', True, 1.0, 'no chain assertions specified')
    variables: Dict[str, str] = {}
    failures: List[Dict[str, object]] = []
    tool_execs = _tool_execs(prediction)

    for assertion in assertions:
        name = str(assertion.get('name') or assertion.get('var') or '').strip()
        source_tool = str(assertion.get('extract_from') or assertion.get('from_tool') or '').strip()
        pattern = str(assertion.get('pattern') or '').strip()
        if source_tool and pattern:
            if not name:
                failures.append({'assertion': assertion, 'reason': 'missing variable name'})
                continue
            source_text = _text_for_tool(prediction, source_tool)
            match = re.search(pattern, source_text, flags=re.MULTILINE)
            if not match:
                failures.append({'assertion': assertion, 'reason': 'extract pattern not found', 'tool': source_tool})
                continue
            group_raw = assertion.get('group', 1)
            try:
                group = int(group_raw)
            except (TypeError, ValueError):
                group = 1
            try:
                value = match.group(group)
            except IndexError:
                failures.append({'assertion': assertion, 'reason': 'extract group missing', 'group': group})
                continue
            variables[name] = str(value)
            if assertion.get('assert_tool'):
                ok = _assert_arg_uses_value(assertion, str(value), tool_execs)
                if not ok:
                    failures.append({'assertion': assertion, 'reason': 'extracted value not used by asserted tool', 'value': value})

    for assertion in assertions:
        assertion_type = str(assertion.get('type') or assertion.get('assert') or '').strip()
        if assertion.get('assert_tool') or assertion_type in {'arg_contains_var', 'arg_equals_var', 'arg_uses_var'}:
            if assertion.get('extract_from') and assertion.get('assert_tool'):
                continue
            var_name = str(assertion.get('var') or assertion.get('name') or '').strip()
            if not var_name:
                failures.append({'assertion': assertion, 'reason': 'missing referenced variable'})
                continue
            if var_name not in variables:
                failures.append({'assertion': assertion, 'reason': 'referenced variable was not extracted', 'var': var_name})
                continue
            value = variables[var_name]
            ok = _assert_arg_uses_value(assertion, value, tool_execs)
            if not ok:
                failures.append({'assertion': assertion, 'reason': 'variable not used by asserted tool', 'var': var_name, 'value': value})

    return ScoreResult(
        'chain_assertions',
        not failures,
        1.0 if not failures else 0.0,
        'chain assertions passed' if not failures else 'chain assertions failed',
        {'extracted': variables, 'failures': failures},
    )


def _grade_expected_args(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    if not case.expected_args:
        return ScoreResult('argument_accuracy', True, 1.0, 'no expected args specified')
    calls_by_tool: Dict[str, List[ExpectedToolCall]] = {}
    for c in prediction.tool_calls:
        calls_by_tool.setdefault(c.name.lower(), []).append(c)
    for e in prediction.trace:
        if e.event_type == 'tool_exec':
            calls_by_tool.setdefault(e.tool_name.lower(), []).append(ExpectedToolCall(name=e.tool_name, args=list(e.args)))
    missing: Dict[str, List[List[str]]] = {}
    for (tool, expected_calls) in case.expected_args.items():
        actual_calls = calls_by_tool.get(tool.lower(), [])
        for expected in expected_calls:
            if not any(_args_match(expected, actual) for actual in actual_calls):
                missing.setdefault(tool, []).append(list(expected.args))
    return ScoreResult(
        'argument_accuracy',
        not missing,
        1.0 if not missing else 0.0,
        'expected args matched' if not missing else 'expected args missing',
        {'missing': missing},
    )


def _grade_observation_evidence(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    if not case.expected_observation_contains:
        return ScoreResult('observation_evidence', True, 1.0, 'no observation snippets specified')
    missing: Dict[str, List[str]] = {}
    text_by_tool: Dict[str, str] = {}
    for e in prediction.trace:
        if e.event_type == 'tool_observation':
            text_by_tool[e.tool_name.lower()] = text_by_tool.get(e.tool_name.lower(), '') + '\n' + (e.text or '')
    for (tool, snippets) in case.expected_observation_contains.items():
        haystack = text_by_tool.get(tool.lower(), '')
        for snippet in snippets:
            if str(snippet) not in haystack:
                missing.setdefault(tool, []).append(str(snippet))
    return ScoreResult(
        'observation_evidence',
        not missing,
        1.0 if not missing else 0.0,
        'observation snippets present' if not missing else 'missing observation snippets',
        {'missing': missing},
    )


def _grade_illegal_tools(case: AgentToolEvalCase, prediction: EvalPrediction) -> ScoreResult:
    available = _available_tools(case)
    if not available:
        return ScoreResult('illegal_tool_rate', True, 0.0, 'available tool set not specified')
    called = _called_tools(prediction)
    illegal = sorted(called - available)
    return ScoreResult(
        'illegal_tool_rate',
        not illegal,
        0.0 if not illegal else 1.0,
        'no illegal tools' if not illegal else 'called tools outside available surface',
        {'illegal': illegal, 'available': sorted(available)},
    )


def _grade_schema_violations(prediction: EvalPrediction) -> ScoreResult:
    violations = [e for e in prediction.trace if e.event_type == 'schema_violation']
    return ScoreResult(
        'schema_violation_rate',
        not violations,
        0.0 if not violations else 1.0,
        'no schema violations' if not violations else 'schema violations present',
        {'count': len(violations)},
    )


def _grade_budget_and_permission(prediction: EvalPrediction) -> ScoreResult:
    failures = [
        e for e in prediction.trace
        if e.event_type in {'budget_cap', 'permission_denied'} or (e.event_type == 'tool_exec' and e.ok is False)
    ]
    return ScoreResult(
        'execution_failures',
        not failures,
        0.0 if not failures else 1.0,
        'no budget, permission, or execution failures' if not failures else 'execution failures present',
        {'count': len(failures), 'reasons': [e.reason for e in failures if e.reason]},
    )


def _tool_execs(prediction: EvalPrediction) -> List[ExpectedToolCall]:
    return [
        ExpectedToolCall(name=e.tool_name, args=list(e.args))
        for e in prediction.trace
        if e.event_type == 'tool_exec' and e.tool_name and e.ok is not False
    ]


def _text_for_tool(prediction: EvalPrediction, tool_name: str) -> str:
    wanted = tool_name.strip().lower()
    chunks: List[str] = []
    for e in prediction.trace:
        if e.tool_name.strip().lower() != wanted:
            continue
        if e.text:
            chunks.append(e.text)
        for key in ('message', 'message_preview', 'observation_text', 'output', 'result'):
            raw = e.data.get(key) if isinstance(e.data, dict) else None
            if raw is not None:
                chunks.append(str(raw))
    return '\n'.join(chunks)


def _assert_arg_uses_value(assertion: Dict[str, object], value: str, tool_execs: Sequence[ExpectedToolCall]) -> bool:
    tool = str(assertion.get('assert_tool') or assertion.get('tool') or '').strip().lower()
    if not tool:
        return False
    match_mode = str(assertion.get('assert_match') or assertion.get('match') or '').strip().lower()
    assertion_type = str(assertion.get('type') or assertion.get('assert') or '').strip().lower()
    if not match_mode:
        match_mode = 'equals' if assertion_type == 'arg_equals_var' else 'contains'
    arg_index_raw = assertion.get('arg_index')
    has_index = arg_index_raw is not None
    try:
        arg_index = int(arg_index_raw) if has_index else -1
    except (TypeError, ValueError):
        return False
    for call in tool_execs:
        if call.name.strip().lower() != tool:
            continue
        haystack = ''
        if has_index:
            if arg_index < 0 or arg_index >= len(call.args):
                continue
            haystack = str(call.args[arg_index])
        else:
            haystack = ' '.join(call.args)
        if match_mode == 'equals' and haystack == value:
            return True
        if match_mode in {'contains', 'uses'} and value in haystack:
            return True
        if match_mode == 'regex' and re.search(value, haystack):
            return True
    return False


def _args_match(expected: ExpectedToolCall, actual: ExpectedToolCall) -> bool:
    if expected.name.lower() != actual.name.lower():
        return False
    matcher = (expected.matcher or 'exact').lower()
    if matcher == 'contains':
        actual_joined = ' '.join(actual.args)
        return all(str(x) in actual_joined for x in expected.args)
    if matcher == 'regex':
        actual_joined = ' '.join(actual.args)
        return all(re.search(str(x), actual_joined) for x in expected.args)
    return list(expected.args) == list(actual.args)


def _call_dict(call: ExpectedToolCall) -> Dict[str, object]:
    return {'name': call.name, 'args': list(call.args), 'matcher': call.matcher}


def _normalize_names(names: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw in names:
        n = (raw or '').strip().lower()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out
