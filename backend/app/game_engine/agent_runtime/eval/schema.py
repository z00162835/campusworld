"""Schemas and JSONL helpers for generic agent tool-use evaluation."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional


@dataclass
class EvalToolSchema:
    name: str
    description: str = ''

    @classmethod
    def from_obj(cls, obj: Mapping[str, Any]) -> 'EvalToolSchema':
        name = str(obj.get('name') or '').strip()
        if not name:
            raise ValueError('tool schema name is required')
        return cls(name=name, description=str(obj.get('description') or ''))


@dataclass
class ExpectedToolCall:
    name: str
    args: List[str] = field(default_factory=list)
    matcher: str = 'exact'

    @classmethod
    def from_obj(cls, obj: Any) -> 'ExpectedToolCall':
        if isinstance(obj, str):
            return cls(name=obj)
        if not isinstance(obj, Mapping):
            raise ValueError('expected tool call must be string or object')
        name = str(obj.get('name') or '').strip()
        if not name:
            raise ValueError('expected tool call name is required')
        args_raw = obj.get('args') or []
        if not isinstance(args_raw, list):
            raise ValueError('expected tool call args must be a list')
        return cls(
            name=name,
            args=[str(x) for x in args_raw],
            matcher=str(obj.get('matcher') or 'exact'),
        )


@dataclass
class AgentToolEvalCase:
    example_id: str
    user_message: str
    agent_id: str = 'aico'
    context_snapshot: str = ''
    stm_snippet: Optional[str] = None
    available_tools: List[EvalToolSchema] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)
    mandatory_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    expected_args: Dict[str, List[ExpectedToolCall]] = field(default_factory=dict)
    expected_tool_sequence: List[ExpectedToolCall] = field(default_factory=list)
    sequence_matcher: str = 'subsequence'
    chain_assertions: List[Dict[str, Any]] = field(default_factory=list)
    expected_observation_contains: Dict[str, List[str]] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    data_source: str = 'synthetic'
    language: str = ''
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_obj(cls, obj: Mapping[str, Any], *, line_no: Optional[int]=None) -> 'AgentToolEvalCase':
        prefix = f'line {line_no}: ' if line_no is not None else ''
        eid = str(obj.get('example_id') or '').strip()
        if not eid:
            raise ValueError(prefix + 'example_id is required')
        msg = str(obj.get('user_message') or '').strip()
        if not msg:
            raise ValueError(prefix + 'user_message is required')
        tools_raw = obj.get('available_tools') or obj.get('tool_schemas') or []
        if tools_raw and not isinstance(tools_raw, list):
            raise ValueError(prefix + 'available_tools must be a list')
        expected_args_raw = obj.get('expected_args') or {}
        if not isinstance(expected_args_raw, Mapping):
            raise ValueError(prefix + 'expected_args must be an object')
        expected_args: Dict[str, List[ExpectedToolCall]] = {}
        for (tool_name, calls_raw) in expected_args_raw.items():
            if isinstance(calls_raw, Mapping) or isinstance(calls_raw, str):
                calls = [calls_raw]
            elif isinstance(calls_raw, list):
                calls = calls_raw
            else:
                raise ValueError(prefix + f'expected_args for {tool_name} must be object/list/string')
            expected_args[str(tool_name)] = [ExpectedToolCall.from_obj(c) for c in calls]
        seq_raw = obj.get('expected_tool_sequence') or []
        if not isinstance(seq_raw, list):
            raise ValueError(prefix + 'expected_tool_sequence must be a list')
        chain_raw = obj.get('chain_assertions') or []
        if not isinstance(chain_raw, list):
            raise ValueError(prefix + 'chain_assertions must be a list')
        chain_assertions: List[Dict[str, Any]] = []
        for assertion in chain_raw:
            if not isinstance(assertion, Mapping):
                raise ValueError(prefix + 'chain_assertions entries must be objects')
            chain_assertions.append(dict(assertion))
        obs_raw = obj.get('expected_observation_contains') or {}
        if not isinstance(obs_raw, Mapping):
            raise ValueError(prefix + 'expected_observation_contains must be an object')
        metadata = obj.get('metadata') or {}
        if not isinstance(metadata, dict):
            raise ValueError(prefix + 'metadata must be an object')
        return cls(
            example_id=eid,
            user_message=msg,
            agent_id=str(obj.get('agent_id') or 'aico'),
            context_snapshot=str(obj.get('context_snapshot') or obj.get('world_snapshot') or ''),
            stm_snippet=obj.get('stm_snippet') if obj.get('stm_snippet') is None else str(obj.get('stm_snippet')),
            available_tools=[EvalToolSchema.from_obj(x) for x in tools_raw],
            expected_tools=_list_str(obj.get('expected_tools') or obj.get('gold_tool_names') or []),
            mandatory_tools=_list_str(obj.get('mandatory_tools') or obj.get('mandatory_subset') or []),
            forbidden_tools=_list_str(obj.get('forbidden_tools') or []),
            expected_args=expected_args,
            expected_tool_sequence=[ExpectedToolCall.from_obj(x) for x in seq_raw],
            sequence_matcher=str(obj.get('sequence_matcher') or 'subsequence'),
            chain_assertions=chain_assertions,
            expected_observation_contains={str(k): _list_str(v) for (k, v) in obs_raw.items()},
            tags=_list_str(obj.get('tags') or []),
            data_source=str(obj.get('data_source') or 'synthetic'),
            language=str(obj.get('language') or ''),
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceEvent:
    event_type: str
    tool_name: str = ''
    args: List[str] = field(default_factory=list)
    ok: Optional[bool] = None
    text: str = ''
    phase: str = ''
    reason: str = ''
    data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_obj(cls, obj: Mapping[str, Any]) -> 'TraceEvent':
        return cls(
            event_type=str(obj.get('event_type') or obj.get('step') or ''),
            tool_name=str(obj.get('tool_name') or obj.get('command_name') or ''),
            args=_list_str(obj.get('args') or []),
            ok=obj.get('ok') if isinstance(obj.get('ok'), bool) else obj.get('success') if isinstance(obj.get('success'), bool) else None,
            text=str(obj.get('text') or obj.get('message') or ''),
            phase=str(obj.get('phase') or ''),
            reason=str(obj.get('reason') or obj.get('detail') or obj.get('error') or ''),
            data=dict(obj.get('data') or {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalPrediction:
    predicted_tools: List[str] = field(default_factory=list)
    tool_calls: List[ExpectedToolCall] = field(default_factory=list)
    final_reply: str = ''
    trace: List[TraceEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoreResult:
    name: str
    passed: bool
    value: Optional[float] = None
    reason: str = ''
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PairCorrection:
    status: str = 'unreviewed'
    corrected_expected_tools: Optional[List[str]] = None
    corrected_mandatory_tools: Optional[List[str]] = None
    corrected_forbidden_tools: Optional[List[str]] = None
    corrected_expected_args: Optional[Dict[str, List[ExpectedToolCall]]] = None
    reviewer_note: str = ''
    discard_reason: str = ''

    @classmethod
    def from_obj(cls, obj: Optional[Mapping[str, Any]]) -> 'PairCorrection':
        if not obj:
            return cls()
        cea_raw = obj.get('corrected_expected_args')
        cea = None
        if isinstance(cea_raw, Mapping):
            cea = {}
            for (k, v) in cea_raw.items():
                raw_calls = v if isinstance(v, list) else [v]
                cea[str(k)] = [ExpectedToolCall.from_obj(x) for x in raw_calls]
        return cls(
            status=str(obj.get('status') or 'unreviewed'),
            corrected_expected_tools=_optional_list_str(obj.get('corrected_expected_tools')),
            corrected_mandatory_tools=_optional_list_str(obj.get('corrected_mandatory_tools')),
            corrected_forbidden_tools=_optional_list_str(obj.get('corrected_forbidden_tools')),
            corrected_expected_args=cea,
            reviewer_note=str(obj.get('reviewer_note') or ''),
            discard_reason=str(obj.get('discard_reason') or ''),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvalPair:
    case: AgentToolEvalCase
    prediction: EvalPrediction
    scores: List[ScoreResult]
    verdict: str
    correction: PairCorrection = field(default_factory=PairCorrection)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _list_str(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        raise ValueError('expected list of strings')
    return [str(x) for x in value]


def _optional_list_str(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    return _list_str(value)


def load_cases_jsonl(path: Path) -> List[AgentToolEvalCase]:
    rows: List[AgentToolEvalCase] = []
    for (i, line) in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f'line {i}: case must be an object')
        rows.append(AgentToolEvalCase.from_obj(obj, line_no=i))
    return rows


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, default=_json_default))
            fh.write('\n')


def load_pairs_jsonl(path: Path) -> List[EvalPair]:
    pairs: List[EvalPair] = []
    for (i, line) in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f'line {i}: pair must be an object')
        pairs.append(pair_from_obj(obj, line_no=i))
    return pairs


def pair_from_obj(obj: Mapping[str, Any], *, line_no: Optional[int]=None) -> EvalPair:
    case_obj = obj.get('case')
    pred_obj = obj.get('prediction')
    if not isinstance(case_obj, Mapping) or not isinstance(pred_obj, Mapping):
        prefix = f'line {line_no}: ' if line_no is not None else ''
        raise ValueError(prefix + 'pair requires case and prediction objects')
    tool_calls = pred_obj.get('tool_calls') or []
    trace = pred_obj.get('trace') or []
    scores = obj.get('scores') or []
    return EvalPair(
        case=AgentToolEvalCase.from_obj(case_obj, line_no=line_no),
        prediction=EvalPrediction(
            predicted_tools=_list_str(pred_obj.get('predicted_tools') or []),
            tool_calls=[ExpectedToolCall.from_obj(x) for x in tool_calls],
            final_reply=str(pred_obj.get('final_reply') or ''),
            trace=[TraceEvent.from_obj(x) for x in trace],
            metadata=dict(pred_obj.get('metadata') or {}),
        ),
        scores=[ScoreResult(name=str(s.get('name') or ''), passed=bool(s.get('passed')), value=s.get('value'), reason=str(s.get('reason') or ''), details=dict(s.get('details') or {})) for s in scores if isinstance(s, Mapping)],
        verdict=str(obj.get('verdict') or 'unknown'),
        correction=PairCorrection.from_obj(obj.get('correction') if isinstance(obj.get('correction'), Mapping) else None),
    )


def _json_default(obj: Any) -> Any:
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if hasattr(obj, '__dict__'):
        return asdict(obj)
    return str(obj)
