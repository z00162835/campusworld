from __future__ import annotations

from pathlib import Path
import json

import pytest

from app.commands.base import CommandResult
from app.game_engine.agent_runtime.eval.config import (
    AicoEvalRuntimeConfig,
    EvalDatasetGovernanceConfig,
    EvalGatePolicyConfig,
    load_eval_config,
)
from app.game_engine.agent_runtime.eval.adapters import aico as aico_adapter
from app.game_engine.agent_runtime.eval.adapters.aico import (
    _aico_command_line_for_case,
    infer_ssh_command_outcome,
    normalize_aico_command_trace,
    run_aico_command_case,
    run_aico_ssh_case,
)
from app.game_engine.agent_runtime.eval.graders import grade_prediction, verdict_from_scores
from app.game_engine.agent_runtime.eval.promote import promoted_cases_from_pairs
from app.game_engine.agent_runtime.eval.review_cli import update_pair_statuses
from app.game_engine.agent_runtime.eval.runner import run_eval
from app.game_engine.agent_runtime.eval.metrics import evaluate_report_gates
from app.game_engine.agent_runtime.eval import streamlit_app as streamlit_mod
from app.game_engine.agent_runtime.eval.schema import (
    AgentToolEvalCase,
    EvalPair,
    EvalPrediction,
    ExpectedToolCall,
    ScoreResult,
    TraceEvent,
    load_cases_jsonl,
    load_pairs_jsonl,
    write_jsonl,
)
from app.game_engine.agent_runtime.eval.streamlit_app import (
    _CASES_SELECTED_CASE_WIDGET_KEY,
    _CASES_SELECT_PENDING_KEY,
    apply_pending_case_selection,
    build_case_from_form_state,
    case_editor_scope,
    case_editor_widget_keys,
    case_to_form_state,
    delete_case,
    ensure_case_editor_hydrated,
    filter_cases,
    filter_pairs,
    hydrate_case_editor_payload,
    new_case_template,
    pair_rows,
    prediction_trace_panels,
    promote_corrected_to_regression,
    queue_case_selection,
    read_case_editor_payload,
    ssh_eval_prerequisites,
    upsert_case,
    validate_case_dict_governance,
)


def _case_obj() -> dict:
    return {
        "example_id": "whoami_001",
        "agent_id": "aico",
        "user_message": "whoami",
        "available_tools": [
            {"name": "whoami", "description": "Show current user"},
            {"name": "look", "description": "Inspect room"},
        ],
        "expected_tools": ["whoami"],
        "mandatory_tools": ["whoami"],
        "forbidden_tools": ["agent"],
        "expected_args": {"whoami": [{"name": "whoami", "args": []}]},
        "expected_observation_contains": {"whoami": ["whoami observation"]},
        "data_source": "synthetic",
        "tags": ["identity"],
    }


@pytest.mark.unit
def test_case_schema_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    write_jsonl(path, [_case_obj()])
    cases = load_cases_jsonl(path)
    assert len(cases) == 1
    assert cases[0].example_id == "whoami_001"
    assert cases[0].expected_args["whoami"][0].args == []


@pytest.mark.unit
def test_case_schema_accepts_chain_assertions(tmp_path: Path) -> None:
    obj = _case_obj()
    obj["chain_assertions"] = [
        {
            "name": "type_code",
            "extract_from": "type",
            "pattern": "type_code[:=]\\s*(\\w+)",
            "assert_tool": "find",
            "arg_index": 1,
            "assert_match": "equals",
        }
    ]
    path = tmp_path / "cases.jsonl"
    write_jsonl(path, [obj])
    cases = load_cases_jsonl(path)
    assert cases[0].chain_assertions[0]["name"] == "type_code"


@pytest.mark.unit
def test_config_requires_db_trace_by_default() -> None:
    cfg = load_eval_config()
    assert cfg.aico.require_live_env is False
    assert cfg.aico.require_db_trace is True
    assert cfg.aico.invoke_via == "ssh"
    assert not hasattr(cfg.aico, "ssh_password")


@pytest.mark.unit
def test_config_ignores_legacy_plaintext_ssh_password(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({
            "aico": {
                "invoke_via": "ssh",
                "ssh_password": "do-not-use",
                "ssh_password_env": "AICO_EVAL_TEST_PASSWORD",
            }
        }),
        encoding="utf-8",
    )
    cfg = load_eval_config(path)
    assert cfg.aico.ssh_password_env == "AICO_EVAL_TEST_PASSWORD"
    assert not hasattr(cfg.aico, "ssh_password")


@pytest.mark.unit
def test_config_loads_gate_policy_and_suite_paths(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({
            "cases_path": "data/gate.jsonl",
            "cases_by_suite": {"smoke": "data/smoke.jsonl"},
            "gate_policy": {
                "tolerance": 1e-6,
                "live": {"illegal_tool_rate": {"op": "lte", "value": 0.1}},
            },
            "aico": {"permissions": ["player"]},
        }),
        encoding="utf-8",
    )
    cfg = load_eval_config(path)
    assert cfg.cases_by_suite["gate"].name == "gate.jsonl"
    assert cfg.cases_by_suite["smoke"].name == "smoke.jsonl"
    assert cfg.gate_policy.tolerance == pytest.approx(1e-6)
    assert cfg.gate_policy.live["illegal_tool_rate"].op == "lte"
    assert cfg.gate_policy.live["illegal_tool_rate"].value == pytest.approx(0.1)
    assert cfg.aico.permissions == ["player"]


@pytest.mark.unit
def test_grader_passes_happy_path() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(
        predicted_tools=["whoami"],
        final_reply="当前用户：admin",
        tool_calls=[ExpectedToolCall(name="whoami", args=[])],
        trace=[
            TraceEvent(event_type="tool_exec", tool_name="whoami", args=[], ok=True),
            TraceEvent(event_type="tool_observation", tool_name="whoami", args=[], ok=True, text="whoami observation"),
        ],
    )
    scores = grade_prediction(case, pred)
    assert verdict_from_scores(scores) == "pass"


@pytest.mark.unit
def test_grader_flags_missing_aico_live_trace() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(
        final_reply="whoami",
        trace=[TraceEvent(event_type="live_trace_missing", ok=False, reason="agent_run_records_not_found")],
        metadata={
            "adapter": "aico",
            "mode": "live",
            "require_db_trace": True,
            "db_trace": {"found": False, "correlation_id": "cid"},
            "passthrough_suspected": True,
            "elapsed_ms": 4.2,
        },
    )
    scores = grade_prediction(case, pred)
    live_score = next(s for s in scores if s.name == "live_trace_presence")
    assert live_score.passed is False
    assert live_score.details["passthrough_suspected"] is True


@pytest.mark.unit
def test_grader_flags_forbidden_and_missing_mandatory() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(
        predicted_tools=["agent"],
        tool_calls=[ExpectedToolCall(name="agent", args=[])],
        trace=[TraceEvent(event_type="tool_exec", tool_name="agent", ok=True)],
    )
    scores = grade_prediction(case, pred)
    failed = {s.name for s in scores if not s.passed}
    assert "forbidden_tools" in failed
    assert "mandatory_observation" in failed


@pytest.mark.unit
def test_grader_flags_empty_final_reply_after_tool_observation() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(
        predicted_tools=["whoami"],
        final_reply="",
        trace=[TraceEvent(event_type="tool_exec", tool_name="whoami", args=[], ok=True)],
    )
    score = next(s for s in grade_prediction(case, pred) if s.name == "final_reply_after_tool")
    assert score.passed is False
    assert "final_reply_empty" in score.details["reasons"]


@pytest.mark.unit
def test_grader_ignores_empty_final_reply_without_tool_observation() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(predicted_tools=[], final_reply="", trace=[])
    score = next(s for s in grade_prediction(case, pred) if s.name == "final_reply_after_tool")
    assert score.passed is True
    assert score.details["observed_tool_count"] == 0


@pytest.mark.unit
def test_grader_accepts_ordered_tool_sequence_subsequence() -> None:
    obj = _case_obj()
    obj["expected_tool_sequence"] = [
        {"name": "find", "args": ["-n", "AICO"]},
        {"name": "describe", "args": ["#42"], "matcher": "contains"},
    ]
    obj["sequence_matcher"] = "subsequence"
    obj["available_tools"].extend([
        {"name": "find", "description": "Find graph nodes"},
        {"name": "describe", "description": "Show graph node details"},
    ])
    obj["expected_tools"] = ["find", "describe"]
    obj["mandatory_tools"] = []
    obj["expected_args"] = {}
    obj["expected_observation_contains"] = {}
    obj["forbidden_tools"] = []
    case = AgentToolEvalCase.from_obj(obj)
    pred = EvalPrediction(
        predicted_tools=["help", "find", "describe"],
        trace=[
            TraceEvent(event_type="tool_exec", tool_name="help", args=["find"], ok=True),
            TraceEvent(event_type="tool_exec", tool_name="find", args=["-n", "AICO"], ok=True),
            TraceEvent(event_type="tool_exec", tool_name="describe", args=["#42"], ok=True),
        ],
    )
    seq_score = next(s for s in grade_prediction(case, pred) if s.name == "tool_sequence")
    assert seq_score.passed is True
    assert seq_score.details["matched_positions"] == [1, 2]


@pytest.mark.unit
def test_grader_accepts_tool_chain_data_dependency() -> None:
    obj = _case_obj()
    obj["available_tools"] = [
        {"name": "type", "description": "Resolve semantic type"},
        {"name": "find", "description": "Find graph nodes by type"},
    ]
    obj["expected_tools"] = ["type", "find"]
    obj["mandatory_tools"] = ["type", "find"]
    obj["expected_args"] = {}
    obj["expected_observation_contains"] = {}
    obj["forbidden_tools"] = []
    obj["expected_tool_sequence"] = [
        {"name": "type", "args": ["家具"], "matcher": "contains"},
        {"name": "find", "args": ["-t", "furniture"], "matcher": "exact"},
    ]
    obj["chain_assertions"] = [
        {
            "name": "type_code",
            "extract_from": "type",
            "pattern": "type_code[:=]\\s*(\\w+)",
            "assert_tool": "find",
            "arg_index": 1,
            "assert_match": "equals",
        }
    ]
    case = AgentToolEvalCase.from_obj(obj)
    pred = EvalPrediction(
        predicted_tools=["type", "find"],
        final_reply="There are 3 furniture nodes.",
        trace=[
            TraceEvent(event_type="tool_exec", tool_name="type", args=["家具"], ok=True, text="type_code=furniture"),
            TraceEvent(event_type="tool_exec", tool_name="find", args=["-t", "furniture"], ok=True, text="chair\ntable\nsofa"),
        ],
    )
    chain_score = next(s for s in grade_prediction(case, pred) if s.name == "chain_assertions")
    assert chain_score.passed is True
    assert chain_score.details["extracted"]["type_code"] == "furniture"


@pytest.mark.unit
def test_grader_rejects_tool_chain_when_followup_arg_ignores_extracted_value() -> None:
    obj = _case_obj()
    obj["available_tools"] = [
        {"name": "type", "description": "Resolve semantic type"},
        {"name": "find", "description": "Find graph nodes by type"},
    ]
    obj["expected_tools"] = ["type", "find"]
    obj["mandatory_tools"] = []
    obj["expected_args"] = {}
    obj["expected_observation_contains"] = {}
    obj["forbidden_tools"] = []
    obj["expected_tool_sequence"] = []
    obj["chain_assertions"] = [
        {"name": "type_code", "extract_from": "type", "pattern": "type_code[:=]\\s*(\\w+)"},
        {"type": "arg_equals_var", "var": "type_code", "tool": "find", "arg_index": 1},
    ]
    case = AgentToolEvalCase.from_obj(obj)
    pred = EvalPrediction(
        predicted_tools=["type", "find"],
        trace=[
            TraceEvent(event_type="tool_exec", tool_name="type", args=["家具"], ok=True, text="type_code=furniture"),
            TraceEvent(event_type="tool_exec", tool_name="find", args=["-t", "device"], ok=True),
        ],
    )
    chain_score = next(s for s in grade_prediction(case, pred) if s.name == "chain_assertions")
    assert chain_score.passed is False
    assert chain_score.details["failures"][0]["reason"] == "variable not used by asserted tool"


@pytest.mark.unit
def test_grader_rejects_wrong_tool_sequence_order() -> None:
    obj = _case_obj()
    obj["expected_tool_sequence"] = [
        {"name": "find", "args": ["-n", "AICO"]},
        {"name": "describe", "args": ["#42"]},
    ]
    obj["available_tools"].extend([
        {"name": "find", "description": "Find graph nodes"},
        {"name": "describe", "description": "Show graph node details"},
    ])
    obj["expected_tools"] = ["find", "describe"]
    obj["mandatory_tools"] = []
    obj["expected_args"] = {}
    obj["expected_observation_contains"] = {}
    obj["forbidden_tools"] = []
    case = AgentToolEvalCase.from_obj(obj)
    pred = EvalPrediction(
        predicted_tools=["describe", "find"],
        trace=[
            TraceEvent(event_type="tool_exec", tool_name="describe", args=["#42"], ok=True),
            TraceEvent(event_type="tool_exec", tool_name="find", args=["-n", "AICO"], ok=True),
        ],
    )
    seq_score = next(s for s in grade_prediction(case, pred) if s.name == "tool_sequence")
    assert seq_score.passed is False
    assert seq_score.details["missing"]["name"] == "describe"


@pytest.mark.unit
def test_infer_ssh_command_outcome_flags_missing_trace() -> None:
    (ok, err) = infer_ssh_command_outcome(
        trace_found=False,
        require_db_trace=True,
        passthrough_suspected=False,
        events=[],
    )
    assert ok is False
    assert err == 'db_trace_not_found'


@pytest.mark.unit
def test_run_aico_ssh_case_sets_command_success_from_trace() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())

    def ssh_runner(_runtime, _command_line):
        return 'whoami output'

    def trace_loader(_db, _after_id):
        return (
            [{"step": "tool_exec", "phase": "plan", "command_name": "whoami", "args": [], "success": True}],
            {"found": True, "correlation_id": "cid-1"},
        )

    pred = run_aico_ssh_case(
        case,
        ssh_runner=ssh_runner,
        trace_loader=trace_loader,
        log_loader=lambda _cid: [],
    )
    assert pred.metadata["command_success"] is True
    assert pred.metadata["command_error"] is None


@pytest.mark.unit
def test_run_aico_ssh_case_marks_failure_on_passthrough() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())

    def ssh_runner(_runtime, _command_line):
        return case.user_message

    def trace_loader(_db, _after_id):
        return ([], {"found": False})

    pred = run_aico_ssh_case(
        case,
        runtime_config=AicoEvalRuntimeConfig(require_db_trace=True),
        ssh_runner=ssh_runner,
        trace_loader=trace_loader,
        log_loader=lambda _cid: [],
    )
    assert pred.metadata["command_success"] is False
    assert pred.metadata["passthrough_suspected"] is True


@pytest.mark.unit
def test_ssh_eval_prerequisites_requires_password_env(monkeypatch) -> None:
    monkeypatch.delenv("AICO_EVAL_SSH_PASSWORD", raising=False)
    status = ssh_eval_prerequisites(AicoEvalRuntimeConfig(invoke_via="ssh", ssh_password_env="AICO_EVAL_SSH_PASSWORD"))
    assert status["ready"] is False
    monkeypatch.setenv("AICO_EVAL_SSH_PASSWORD", "secret")
    status_ok = ssh_eval_prerequisites(AicoEvalRuntimeConfig(invoke_via="ssh", ssh_password_env="AICO_EVAL_SSH_PASSWORD"))
    assert status_ok["ready"] is True


@pytest.mark.unit
def test_promote_corrected_to_regression_writes_cases(tmp_path: Path) -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pair = EvalPair(case=case, prediction=EvalPrediction(predicted_tools=["whoami"]), scores=[], verdict="pass")
    pair.correction.status = "accepted"
    corrected = tmp_path / "corrected.jsonl"
    regression = tmp_path / "regression.jsonl"
    write_jsonl(corrected, [pair.to_dict()])
    count = promote_corrected_to_regression(corrected_pairs_path=corrected, regression_cases_path=regression)
    assert count == 1
    rows = load_cases_jsonl(regression)
    assert rows[0].metadata.get("promoted_from_pair") is True


@pytest.mark.unit
def test_prediction_trace_panels_extracts_metadata() -> None:
    panels = prediction_trace_panels({
        "metadata": {
            "command_line": "aico whoami",
            "invoke_via": "ssh",
            "command_success": True,
            "db_trace": {"found": True},
            "aico_log_excerpt": ["line1"],
        },
        "trace": [{"event_type": "tool_exec"}],
    })
    assert panels["command_line"] == "aico whoami"
    assert panels["db_trace"]["found"] is True
    assert "aico_log_excerpt" not in panels


@pytest.mark.unit
def test_aico_adapter_normalizes_existing_trace() -> None:
    rows = [
        {"step": "tool_exec", "phase": "plan", "command_name": "look", "args": [], "success": True, "message_preview": "room observation"},
        {"step": "tool_call_filtered", "phase": "plan", "dropped": ["aico"]},
        {"step": "mandatory_observation_gap", "missing": ["whoami"]},
    ]
    events = normalize_aico_command_trace(rows)
    assert events[0].event_type == "tool_exec"
    assert events[0].tool_name == "look"
    assert events[0].text == "room observation"
    assert events[1].event_type == "schema_violation"
    assert events[2].event_type == "mandatory_gap"


@pytest.mark.unit
def test_runner_live_outputs_pair_with_injected_adapter(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.jsonl"
    write_jsonl(cases_path, [_case_obj()])

    class _Adapter:
        adapter_name = "fake"

        def run_live_case(self, _case):
            return EvalPrediction(
                predicted_tools=["whoami"],
                final_reply="当前用户：admin",
                tool_calls=[ExpectedToolCall(name="whoami", args=[])],
                trace=[
                    TraceEvent(event_type="tool_exec", tool_name="whoami", args=[], ok=True),
                    TraceEvent(event_type="tool_observation", tool_name="whoami", args=[], ok=True, text="whoami observation"),
                ],
            )

    pairs = run_eval(config=load_eval_config(), adapter_name="aico", cases_path=cases_path, adapter=_Adapter())
    assert len(pairs) == 1
    assert pairs[0].verdict == "pass"


@pytest.mark.unit
def test_runner_main_returns_non_zero_when_gate_fails(monkeypatch, tmp_path: Path) -> None:
    from app.game_engine.agent_runtime.eval import runner as eval_runner

    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(final_reply="", trace=[TraceEvent(event_type="tool_exec", tool_name="whoami", ok=True)])
    pair = EvalPair(
        case=case,
        prediction=pred,
        scores=[
            ScoreResult("live_trace_presence", True, 1.0),
            ScoreResult("final_reply_after_tool", False, 0.0),
            ScoreResult("illegal_tool_rate", True, 0.0),
            ScoreResult("schema_violation_rate", True, 0.0),
        ],
        verdict="fail",
    )

    class _Cfg:
        adapter = "aico"
        cases_path = tmp_path / "cases.jsonl"
        cases_by_suite = {"gate": cases_path}
        pairs_path = tmp_path / "pairs.jsonl"
        report_path = tmp_path / "report.json"
        config_path = tmp_path / "config.json"
        gate_policy = EvalGatePolicyConfig(enforce=True)
        dataset_governance = EvalDatasetGovernanceConfig(strict=False)

    monkeypatch.setattr(eval_runner, "load_eval_config", lambda _path: _Cfg())
    monkeypatch.setattr(eval_runner, "run_eval", lambda **_kwargs: [pair])
    monkeypatch.setattr(eval_runner, "load_cases_jsonl", lambda _path: [case])
    monkeypatch.setattr(
        eval_runner,
        "DEFAULT_CONFIG_PATH",
        tmp_path / "config.json",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["runner.py", "--out", str(tmp_path / "pairs.out.jsonl"), "--report", str(tmp_path / "report.out.json")],
    )

    rc = eval_runner.main()
    assert rc != 0


@pytest.mark.unit
def test_runner_main_allows_gate_failure_with_no_enforce_flag(monkeypatch, tmp_path: Path) -> None:
    from app.game_engine.agent_runtime.eval import runner as eval_runner

    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(final_reply="", trace=[TraceEvent(event_type="tool_exec", tool_name="whoami", ok=True)])
    pair = EvalPair(
        case=case,
        prediction=pred,
        scores=[
            ScoreResult("live_trace_presence", True, 1.0),
            ScoreResult("final_reply_after_tool", False, 0.0),
            ScoreResult("illegal_tool_rate", True, 0.0),
            ScoreResult("schema_violation_rate", True, 0.0),
        ],
        verdict="fail",
    )

    class _Cfg:
        adapter = "aico"
        cases_path = tmp_path / "cases.jsonl"
        cases_by_suite = {"gate": cases_path}
        pairs_path = tmp_path / "pairs.jsonl"
        report_path = tmp_path / "report.json"
        config_path = tmp_path / "config.json"
        gate_policy = EvalGatePolicyConfig(enforce=True)
        dataset_governance = EvalDatasetGovernanceConfig(strict=False)

    monkeypatch.setattr(eval_runner, "load_eval_config", lambda _path: _Cfg())
    monkeypatch.setattr(eval_runner, "run_eval", lambda **_kwargs: [pair])
    monkeypatch.setattr(eval_runner, "load_cases_jsonl", lambda _path: [case])
    monkeypatch.setattr(
        eval_runner,
        "DEFAULT_CONFIG_PATH",
        tmp_path / "config.json",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "runner.py",
            "--no-enforce-gates",
            "--out",
            str(tmp_path / "pairs.out.jsonl"),
            "--report",
            str(tmp_path / "report.out.json"),
        ],
    )

    rc = eval_runner.main()
    assert rc == 0


@pytest.mark.unit
def test_runner_main_fails_on_dataset_governance_validation(monkeypatch, tmp_path: Path) -> None:
    from app.game_engine.agent_runtime.eval import runner as eval_runner

    case_obj = _case_obj()
    case_obj["tags"] = []
    bad_case = AgentToolEvalCase.from_obj(case_obj)

    class _Cfg:
        adapter = "aico"
        cases_path = tmp_path / "cases.jsonl"
        cases_by_suite = {"gate": cases_path}
        pairs_path = tmp_path / "pairs.jsonl"
        report_path = tmp_path / "report.json"
        config_path = tmp_path / "config.json"
        gate_policy = EvalGatePolicyConfig(enforce=True)
        dataset_governance = EvalDatasetGovernanceConfig(strict=True)

    monkeypatch.setattr(eval_runner, "load_eval_config", lambda _path: _Cfg())
    monkeypatch.setattr(eval_runner, "load_cases_jsonl", lambda _path: [bad_case])
    monkeypatch.setattr("sys.argv", ["runner.py"])

    with pytest.raises(ValueError, match="dataset governance validation failed"):
        eval_runner.main()


@pytest.mark.unit
def test_evaluate_report_gates_supports_operator_thresholds() -> None:
    report = {
        "mode": "live",
        "scores": {
            "final_reply_after_tool": 1.0,
            "illegal_tool_rate": 0.05,
        },
        "gate_thresholds": {
            "live": {
                "final_reply_after_tool": {"op": "gte", "value": 1.0},
                "illegal_tool_rate": {"op": "lte", "value": 0.1},
            }
        },
    }
    (passed, failures) = evaluate_report_gates(report, mode="live", tolerance=1e-9)
    assert passed is True
    assert failures == []


@pytest.mark.unit
def test_aico_adapter_reuses_one_ssh_session_for_multiple_cases(monkeypatch) -> None:
    aico_adapter.logging.getLogger("paramiko.transport").setLevel(aico_adapter.logging.DEBUG)
    aico_adapter._quiet_paramiko_logs()
    assert aico_adapter.logging.getLogger("paramiko.transport").level == aico_adapter.logging.WARNING

    class _Query:
        def order_by(self, *_args):
            return self

        def first(self):
            return (0,)

    class _DB:
        def query(self, *_args):
            return _Query()

        def close(self):
            pass

    class _FakeSshSession:
        created = 0
        closed = 0
        commands = []

        def __init__(self, _runtime):
            type(self).created += 1

        def run(self, command_line):
            type(self).commands.append(command_line)
            return "final"

        def close(self):
            type(self).closed += 1

    monkeypatch.setattr(aico_adapter, "AicoSshCommandSession", _FakeSshSession)
    monkeypatch.setattr(aico_adapter, "get_db_session", lambda: _DB())
    monkeypatch.setattr(
        aico_adapter,
        "load_latest_aico_run_trace_after_id",
        lambda _db, _after_id: (
            [{"step": "tool_exec", "phase": "plan", "command_name": "whoami", "args": [], "success": True}],
            {"found": True, "row_id": 1, "correlation_id": "cid"},
        ),
    )
    adapter = aico_adapter.AicoEvalAdapter(runtime_config=AicoEvalRuntimeConfig(invoke_via="ssh"))
    adapter.run_live_case(AgentToolEvalCase.from_obj(_case_obj()))
    adapter.run_live_case(AgentToolEvalCase.from_obj(_case_obj()))
    adapter.close()
    assert _FakeSshSession.created == 1
    assert _FakeSshSession.commands == ["aico whoami", "aico whoami"]
    assert _FakeSshSession.closed == 1


@pytest.mark.unit
def test_pairs_jsonl_review_and_promote(tmp_path: Path) -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pred = EvalPrediction(predicted_tools=["whoami"])
    pair = EvalPair(case=case, prediction=pred, scores=[], verdict="pass")
    path = tmp_path / "pairs.jsonl"
    write_jsonl(path, [pair.to_dict()])
    pairs = load_pairs_jsonl(path)
    reviewed = update_pair_statuses(pairs, example_id="whoami_001", status="accepted", note="ok")
    promoted = promoted_cases_from_pairs(reviewed)
    assert promoted[0].metadata["promoted_from_pair"] is True
    assert promoted[0].metadata["review_status"] == "accepted"


@pytest.mark.unit
def test_streamlit_helpers_filter_and_rows() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    pair = EvalPair(
        case=case,
        prediction=EvalPrediction(predicted_tools=["whoami"]),
        scores=[],
        verdict="pass",
    )
    rows = pair_rows([pair])
    assert rows[0]["example_id"] == "whoami_001"
    assert filter_pairs([pair], verdict="pass", tool="whoami", tag="identity") == [pair]
    assert filter_pairs([pair], verdict="fail") == []


@pytest.mark.unit
def test_case_editor_hydrate_and_read_roundtrip() -> None:
    base = _case_obj()
    base["metadata"] = {"intent": "execute", "dataset_tier": "gate", "dataset_version": "v1"}
    form = case_to_form_state(base, default_suite="gate")
    session: dict = {}
    scope = case_editor_scope(cases_state_key="cases::/tmp/cases.jsonl", selected_case_id="whoami_001")
    hydrate_case_editor_payload(form, scope=scope, session=session, raw_case=base)
    session["edited"] = True
    session[case_editor_widget_keys(scope)["user_message"]] = "updated message"
    payload = read_case_editor_payload(scope, session)
    assert payload["user_message"] == "updated message"
    rebuilt = build_case_from_form_state(payload, base_case=base, default_suite="gate")
    assert rebuilt["example_id"] == "whoami_001"


@pytest.mark.unit
def test_ensure_case_editor_hydrated_only_on_scope_change() -> None:
    from app.game_engine.agent_runtime.eval.streamlit_app import _CASE_EDITOR_ACTIVE_SCOPE, case_editor_widget_keys

    session: dict = {}
    form_a = case_to_form_state(_case_obj(), default_suite="gate")
    form_b = dict(form_a)
    form_b["user_message"] = "other"
    scope_a = case_editor_scope(cases_state_key="k", selected_case_id="a")
    scope_b = case_editor_scope(cases_state_key="k", selected_case_id="b")
    ensure_case_editor_hydrated(scope=scope_a, form_state=form_a, session=session, raw_case=form_a)
    keys_a = case_editor_widget_keys(scope_a)
    session[keys_a["user_message"]] = "manual edit"
    ensure_case_editor_hydrated(scope=scope_a, form_state=form_a, session=session, raw_case=form_a)
    assert session[keys_a["user_message"]] == "manual edit"
    ensure_case_editor_hydrated(scope=scope_b, form_state=form_b, session=session, raw_case=form_b)
    keys_b = case_editor_widget_keys(scope_b)
    assert session[keys_b["user_message"]] == "other"
    assert session[_CASE_EDITOR_ACTIVE_SCOPE] == scope_b


@pytest.mark.unit
def test_queue_and_apply_pending_case_selection() -> None:
    session: dict = {}
    queue_case_selection(session, 'saved_case_001')
    assert session[_CASES_SELECT_PENDING_KEY] == 'saved_case_001'
    apply_pending_case_selection(session)
    assert session[_CASES_SELECTED_CASE_WIDGET_KEY] == 'saved_case_001'
    assert _CASES_SELECT_PENDING_KEY not in session


@pytest.mark.unit
def test_validate_case_dict_governance_requires_tags() -> None:
    cfg = load_eval_config(Path('app/game_engine/agent_runtime/eval/config.json'))
    bad = _case_obj()
    bad['tags'] = []
    bad['metadata'] = {'intent': 'execute', 'dataset_tier': 'gate', 'dataset_version': 'v1'}
    with pytest.raises(ValueError, match='missing tags'):
        validate_case_dict_governance(bad, suite='gate', config=cfg)


@pytest.mark.unit
def test_gate_initial_cases_pass_dataset_governance() -> None:
    from app.game_engine.agent_runtime.eval.runner import validate_case_governance

    cfg = load_eval_config(Path('app/game_engine/agent_runtime/eval/config.json'))
    cases = load_cases_jsonl(cfg.cases_by_suite['gate'])
    validate_case_governance(cases, expected_suite='gate', config=cfg)
    assert len(cases) >= 21


@pytest.mark.unit
def test_case_form_state_round_trip() -> None:
    base = _case_obj()
    base["metadata"] = {
        "intent": "execute",
        "dataset_tier": "gate",
        "dataset_version": "2026-05-gate-v1",
        "case_owner": "agent-runtime",
    }
    form = case_to_form_state(base, default_suite="gate")
    rebuilt = build_case_from_form_state(form, base_case=base, default_suite="gate")
    assert rebuilt["example_id"] == "whoami_001"
    assert rebuilt["expected_tools"] == ["whoami"]
    assert rebuilt["metadata"]["intent"] == "execute"
    assert rebuilt["metadata"]["dataset_tier"] == "gate"
    assert len(rebuilt["available_tools"]) == 2


@pytest.mark.unit
def test_new_case_template_uses_suite_tier() -> None:
    case = new_case_template(default_suite="smoke")
    assert case["metadata"]["dataset_tier"] == "smoke"


@pytest.mark.unit
def test_case_helpers_filter_upsert_delete() -> None:
    base = _case_obj()
    base["metadata"] = {"intent": "execute", "dataset_tier": "gate"}
    rows = [base]
    assert len(filter_cases(rows, q="whoami")) == 1
    assert len(filter_cases(rows, intent="execute")) == 1
    new_case = dict(base)
    new_case["example_id"] = "whoami_002"
    new_case["user_message"] = "who am i now"
    updated = upsert_case(rows, new_case)
    assert {x["example_id"] for x in updated} == {"whoami_001", "whoami_002"}
    replaced = dict(new_case)
    replaced["user_message"] = "identity please"
    updated2 = upsert_case(updated, replaced)
    assert len([x for x in updated2 if x["example_id"] == "whoami_002"]) == 1
    deleted = delete_case(updated2, "whoami_001")
    assert [x["example_id"] for x in deleted] == ["whoami_002"]


@pytest.mark.unit
def test_streamlit_run_eval_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    cases_path = tmp_path / "cases.jsonl"
    write_jsonl(cases_path, [_case_obj()])
    config_path.write_text(
        json.dumps(
            {
                "adapter": "aico",
                "cases_path": "cases.jsonl",
                "pairs_path": "pairs.jsonl",
                "report_path": "report.json",
                "aico": {"permissions": ["player"]},
            }
        ),
        encoding="utf-8",
    )

    case = AgentToolEvalCase.from_obj(_case_obj())
    pair = EvalPair(
        case=case,
        prediction=EvalPrediction(predicted_tools=["whoami"], final_reply="ok"),
        scores=[ScoreResult("live_trace_presence", True, 1.0)],
        verdict="pass",
    )

    class _DummyAdapter:
        adapter_name = "dummy"

    monkeypatch.setattr(streamlit_mod, "adapter_by_name", lambda _name, config: _DummyAdapter())
    from app.game_engine.agent_runtime.eval import runner as eval_runner

    monkeypatch.setattr(eval_runner, "run_eval", lambda **_kwargs: [pair])
    payload = streamlit_mod.run_eval_from_streamlit(
        config_path=config_path,
        suite="gate",
        enforce_gates=False,
        skip_dataset_governance=True,
    )
    assert payload["exit_code"] == 0
    assert Path(payload["out_path"]).exists()
    assert Path(payload["report_path"]).exists()


@pytest.mark.unit
def test_live_command_case_invokes_aico_default_path() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    seen = {}

    def runner(ctx, argv):
        seen["session_id"] = ctx.session_id
        seen["argv"] = list(argv)
        return CommandResult.success_result("final")

    def trace_loader(_db, correlation_id):
        return (
            [{"step": "tool_exec", "phase": "plan", "command_name": "whoami", "args": [], "success": True}],
            {"found": True, "correlation_id": correlation_id, "run_id": "r1"},
        )

    class _DB:
        def commit(self):
            seen["committed"] = True

    pred = run_aico_command_case(
        case,
        db_session=_DB(),
        command_runner=runner,
        trace_loader=trace_loader,
        log_loader=lambda correlation_id: [f"correlation_id={correlation_id}"],
    )
    assert seen["argv"] == ["whoami"]
    assert seen["committed"] is True
    assert pred.final_reply == "final"
    assert pred.predicted_tools == ["whoami"]
    assert pred.metadata["invocation"] == "aico"
    assert pred.metadata["aico_log_excerpt"]


@pytest.mark.unit
def test_live_command_case_marks_missing_db_trace_as_passthrough_suspect() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())

    def runner(_ctx, _argv):
        return CommandResult.success_result("whoami")

    class _DB:
        def commit(self):
            pass

    pred = run_aico_command_case(
        case,
        db_session=_DB(),
        command_runner=runner,
        trace_loader=lambda _db, cid: ([], {"found": False, "correlation_id": cid}),
        log_loader=lambda _cid: [],
    )
    assert pred.metadata["db_trace"]["found"] is False
    assert pred.metadata["passthrough_suspected"] is True
    assert any(e.event_type == "live_trace_missing" for e in pred.trace)


@pytest.mark.unit
def test_live_command_case_invokes_aico_new_dialogue() -> None:
    obj = _case_obj()
    obj["metadata"] = {"aico_new_dialogue": True}
    case = AgentToolEvalCase.from_obj(obj)
    seen = {}

    def runner(_ctx, argv):
        seen["argv"] = list(argv)
        return CommandResult.success_result("final")

    class _DB:
        def commit(self):
            pass

    pred = run_aico_command_case(
        case,
        db_session=_DB(),
        command_runner=runner,
        trace_loader=lambda _db, cid: ([], {"found": False, "correlation_id": cid}),
        log_loader=lambda _cid: [],
    )
    assert seen["argv"] == ["-nd", "whoami"]
    assert pred.metadata["invocation"] == "aico -nd"


@pytest.mark.unit
def test_ssh_command_line_matches_real_aico_shell_invocation() -> None:
    case = AgentToolEvalCase.from_obj(_case_obj())
    assert _aico_command_line_for_case(case) == "aico whoami"
    obj = _case_obj()
    obj["user_message"] = "我是谁？当前登录用户是谁？"
    obj["metadata"] = {"aico_new_dialogue": True}
    nd_case = AgentToolEvalCase.from_obj(obj)
    assert _aico_command_line_for_case(nd_case) == "aico -nd '我是谁？当前登录用户是谁？'"
