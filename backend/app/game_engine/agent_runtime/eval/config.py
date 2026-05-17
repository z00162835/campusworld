"""Configuration loading for AICO live tool evaluation."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / 'config.json'


@dataclass
class AicoEvalRuntimeConfig:
    require_live_env: bool = False
    require_db_trace: bool = True
    invoke_via: str = 'ssh'
    default_new_dialogue: bool = False
    user_id: str = '1'
    username: str = 'eval_user'
    permissions: List[str] = field(default_factory=lambda: ['player'])
    roles: List[str] = field(default_factory=list)
    log_path: Optional[Path] = None
    ssh_host: str = '127.0.0.1'
    ssh_port: int = 2222
    ssh_username: str = 'admin'
    ssh_password_env: str = 'AICO_EVAL_SSH_PASSWORD'
    ssh_command_timeout_seconds: float = 180.0


@dataclass
class EvalGateMetricConfig:
    op: str = 'eq'
    value: float = 0.0


@dataclass
class EvalGatePolicyConfig:
    enforce: bool = True
    tolerance: float = 1e-9
    live: Dict[str, EvalGateMetricConfig] = field(default_factory=dict)


@dataclass
class EvalDatasetGovernanceConfig:
    strict: bool = True
    require_tags: bool = True
    require_intent_metadata: bool = True
    require_dataset_tier: bool = True


@dataclass
class EvalToolConfig:
    config_path: Path
    adapter: str
    cases_path: Path
    pairs_path: Path
    report_path: Path
    corrected_pairs_path: Path
    regression_cases_path: Path
    cases_by_suite: Dict[str, Path]
    aico: AicoEvalRuntimeConfig
    gate_policy: EvalGatePolicyConfig
    dataset_governance: EvalDatasetGovernanceConfig


def load_eval_config(path: Optional[Path]=None) -> EvalToolConfig:
    cfg_path = (path or DEFAULT_CONFIG_PATH).resolve()
    raw: Dict[str, Any] = {}
    if cfg_path.exists():
        raw = json.loads(cfg_path.read_text(encoding='utf-8'))
    base_dir = cfg_path.parent
    aico_raw = raw.get('aico') if isinstance(raw.get('aico'), dict) else {}
    gate_raw = raw.get('gate_policy') if isinstance(raw.get('gate_policy'), dict) else {}
    gate_live_raw = gate_raw.get('live') if isinstance(gate_raw.get('live'), dict) else {}
    default_live_gates = {
        'live_trace_presence': EvalGateMetricConfig(op='gte', value=1.0),
        'final_reply_after_tool': EvalGateMetricConfig(op='gte', value=1.0),
        'illegal_tool_rate': EvalGateMetricConfig(op='lte', value=0.0),
        'schema_violation_rate': EvalGateMetricConfig(op='lte', value=0.0),
    }
    live_gates = dict(default_live_gates)
    for (metric_name, metric_cfg) in gate_live_raw.items():
        if not isinstance(metric_cfg, dict):
            continue
        live_gates[str(metric_name)] = EvalGateMetricConfig(
            op=str(metric_cfg.get('op') or default_live_gates.get(str(metric_name), EvalGateMetricConfig()).op),
            value=float(metric_cfg.get('value') if metric_cfg.get('value') is not None else default_live_gates.get(str(metric_name), EvalGateMetricConfig()).value),
        )
    gov_raw = raw.get('dataset_governance') if isinstance(raw.get('dataset_governance'), dict) else {}
    cases_by_suite_raw = raw.get('cases_by_suite') if isinstance(raw.get('cases_by_suite'), dict) else {}
    default_cases_rel = str(raw.get('cases_path') or 'data/aico_initial_cases.jsonl')
    cases_by_suite = {'gate': _resolve(base_dir, default_cases_rel)}
    for (suite, suite_path) in cases_by_suite_raw.items():
        name = str(suite).strip().lower()
        if not name:
            continue
        cases_by_suite[name] = _resolve(base_dir, suite_path)
    return EvalToolConfig(
        config_path=cfg_path,
        adapter=str(raw.get('adapter') or 'aico'),
        cases_path=cases_by_suite.get('gate') or _resolve(base_dir, default_cases_rel),
        pairs_path=_resolve(base_dir, raw.get('pairs_path') or 'data/pairs.live.jsonl'),
        report_path=_resolve(base_dir, raw.get('report_path') or 'data/report.live.json'),
        corrected_pairs_path=_resolve(base_dir, raw.get('corrected_pairs_path') or 'data/corrected_pairs.jsonl'),
        regression_cases_path=_resolve(base_dir, raw.get('regression_cases_path') or 'data/cases.regression.jsonl'),
        cases_by_suite=cases_by_suite,
        aico=AicoEvalRuntimeConfig(
            require_live_env=bool(aico_raw.get('require_live_env', False)),
            require_db_trace=bool(aico_raw.get('require_db_trace', True)),
            invoke_via=str(aico_raw.get('invoke_via') or 'ssh'),
            default_new_dialogue=bool(aico_raw.get('default_new_dialogue', False)),
            user_id=str(aico_raw.get('user_id') or '1'),
            username=str(aico_raw.get('username') or 'eval_user'),
            permissions=_list_str(aico_raw.get('permissions') or ['player']),
            roles=_list_str(aico_raw.get('roles') or []),
            log_path=_resolve_optional(base_dir, aico_raw.get('log_path')),
            ssh_host=str(aico_raw.get('ssh_host') or '127.0.0.1'),
            ssh_port=int(aico_raw.get('ssh_port') or 2222),
            ssh_username=str(aico_raw.get('ssh_username') or 'admin'),
            ssh_password_env=str(aico_raw.get('ssh_password_env') or 'AICO_EVAL_SSH_PASSWORD'),
            ssh_command_timeout_seconds=float(aico_raw.get('ssh_command_timeout_seconds') or 180.0),
        ),
        gate_policy=EvalGatePolicyConfig(
            enforce=bool(gate_raw.get('enforce', True)),
            tolerance=float(gate_raw.get('tolerance') if gate_raw.get('tolerance') is not None else 1e-9),
            live=live_gates,
        ),
        dataset_governance=EvalDatasetGovernanceConfig(
            strict=bool(gov_raw.get('strict', True)),
            require_tags=bool(gov_raw.get('require_tags', True)),
            require_intent_metadata=bool(gov_raw.get('require_intent_metadata', True)),
            require_dataset_tier=bool(gov_raw.get('require_dataset_tier', True)),
        ),
    )


def _resolve(base_dir: Path, value: Any) -> Path:
    path = Path(str(value))
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def _resolve_optional(base_dir: Path, value: Any) -> Optional[Path]:
    if value is None or str(value).strip() == '':
        return None
    return _resolve(base_dir, value)


def _list_str(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or '').split(',') if x.strip()]
