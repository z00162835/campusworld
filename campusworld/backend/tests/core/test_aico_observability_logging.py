"""Tests for AICO dedicated observability logging."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from app.core.log.aico_observability import (
    AICO_OBSERVABILITY_LOGGER_NAME,
    clear_aico_full_chain_tick,
    clear_aico_observability_context,
    configure_aico_observability_logging,
    get_aico_max_phase_output_chars,
    is_aico_dev_chain_verbose,
    is_aico_observability_enabled,
    log_aico_llm_call,
    set_aico_full_chain_tick,
    set_aico_observability_context,
    should_emit_aico_full_chain_logs,
    truncate_for_aico_log,
)
from app.core.log import LoggerNames
from app.game_engine.agent_runtime.agent_llm_config import yaml_llm_base_from_by_service_id
from app.game_engine.agent_runtime.llm_client import LlmCallSpec
from app.game_engine.agent_runtime.aico_observability_hooks import AicoObservabilityTickHooks
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.thinking_pipeline import ThinkingPhaseId


def _config_get(mapping):
    def get(key, default=None):
        return mapping.get(key, default)

    return get


@pytest.mark.unit
def test_yaml_llm_base_strips_observability(monkeypatch):
    mock_cm = MagicMock()
    mock_cm.get_nested.return_value = {
        "aico": {
            "model": "m1",
            "system_prompt": "sys",
            "observability": {"enabled": True, "log_path": "x.log"},
        }
    }
    monkeypatch.setattr(
        "app.game_engine.agent_runtime.agent_llm_config.get_config",
        lambda: mock_cm,
    )
    cfg = yaml_llm_base_from_by_service_id("aico", "aico")
    assert cfg.model == "m1"
    assert cfg.system_prompt == "sys"


@pytest.mark.unit
def test_is_aico_observability_enabled():
    cm = MagicMock()
    cm.get.return_value = {"enabled": True}
    assert is_aico_observability_enabled(cm) is True
    cm.get.return_value = {"enabled": False}
    assert is_aico_observability_enabled(cm) is False


@pytest.mark.unit
def test_should_emit_aico_full_chain_requires_tick_flag():
    cm = MagicMock()
    cm.get.return_value = {"enabled": True, "level": "DEBUG"}
    assert should_emit_aico_full_chain_logs(cm) is False
    set_aico_full_chain_tick(True)
    try:
        assert should_emit_aico_full_chain_logs(cm) is True
    finally:
        clear_aico_full_chain_tick()


@pytest.mark.unit
def test_is_aico_dev_chain_verbose():
    cm = MagicMock()
    cm.get.return_value = {"enabled": True, "level": "DEBUG"}
    assert is_aico_dev_chain_verbose(cm) is True
    cm.get.return_value = {"enabled": True, "level": "INFO"}
    assert is_aico_dev_chain_verbose(cm) is False
    cm.get.return_value = {"enabled": False, "level": "DEBUG"}
    assert is_aico_dev_chain_verbose(cm) is False


@pytest.mark.unit
def test_truncate_for_aico_log():
    assert truncate_for_aico_log("abcdef", 3) == "abc…"
    assert truncate_for_aico_log("ab", 10) == "ab"
    assert truncate_for_aico_log("xy", 0) == "xy"


@pytest.mark.unit
def test_log_aico_llm_call_debug(caplog):
    caplog.set_level(logging.DEBUG, LoggerNames.AICO_AGENT)
    cm = MagicMock()
    cm.get.side_effect = _config_get(
        {
            "agents.llm.by_service_id.aico.observability": {
                "enabled": True,
                "level": "DEBUG",
                "max_phase_output_chars": 1000,
            }
        }
    )
    set_aico_observability_context(run_id="run-test", correlation_id="corr-test")
    set_aico_full_chain_tick(True)
    try:
        log_aico_llm_call(
            cm,
            phase="plan",
            system="sys",
            user="usr",
            spec=LlmCallSpec(),
            skipped=False,
        )
    finally:
        clear_aico_full_chain_tick()
        clear_aico_observability_context()
    assert "aico_llm_call" in caplog.text
    assert "run-test" in caplog.text
    assert "corr-test" in caplog.text


@pytest.mark.unit
def test_get_aico_max_phase_output_chars():
    cm = MagicMock()
    cm.get.return_value = {"max_phase_output_chars": 100}
    assert get_aico_max_phase_output_chars(cm) == 100
    cm.get.return_value = {}
    assert get_aico_max_phase_output_chars(cm) == 4000


@pytest.mark.unit
def test_configure_aico_observability_logging_writes_file(monkeypatch, tmp_path):
    obs = {
        "enabled": True,
        "log_path": "test_aico.log",
        "level": "INFO",
        "max_file_size": "1MB",
        "backup_count": 2,
    }
    cm = MagicMock()
    cm.get.side_effect = _config_get(
        {
            "agents.llm.by_service_id.aico.observability": obs,
            "logging": {"format": "%(message)s", "date_format": "%H:%M:%S"},
        }
    )
    monkeypatch.setattr(
        "app.core.log.aico_observability.get_backend_root",
        lambda _cm: tmp_path,
    )

    configure_aico_observability_logging(cm)
    log = logging.getLogger(AICO_OBSERVABILITY_LOGGER_NAME)
    log.info("hello_aico_obs")

    p = tmp_path / "test_aico.log"
    assert p.exists()
    assert b"hello_aico_obs" in p.read_bytes()

    cm.get.side_effect = _config_get({"agents.llm.by_service_id.aico.observability": {"enabled": False}})
    configure_aico_observability_logging(cm)


@pytest.mark.unit
def test_aico_observability_hooks_truncates():
    records = []

    class _Log:
        def info(self, msg, *args):
            records.append((msg, args))

    hooks = AicoObservabilityTickHooks(_Log(), max_phase_output_chars=4)
    ctx = FrameworkRunContext(agent_node_id=1, correlation_id="c1", payload={"message": "hello world"})
    hooks.on_before_phase(ThinkingPhaseId.plan, ctx)
    hooks.on_after_phase(
        ThinkingPhaseId.do,
        ctx,
        phase_llm_output="abcdefghij",
        skipped=False,
    )
    assert any("aico_tick_start" in r[0] for r in records)
    end = next(r for r in records if "aico_phase_end" in r[0])
    assert end[1][3] is False
    assert end[1][4] == 10
    assert "abcd" in end[1][5]


@pytest.mark.unit
def test_aico_observability_hooks_logs_skipped():
    records = []

    class _Log:
        def info(self, msg, *args):
            records.append((msg, args))

    hooks = AicoObservabilityTickHooks(_Log(), max_phase_output_chars=100)
    ctx = FrameworkRunContext(agent_node_id=2, correlation_id="c2", payload={"message": "x"})
    hooks.on_after_phase(ThinkingPhaseId.plan, ctx, phase_llm_output="", skipped=True)
    end = next(r for r in records if "aico_phase_end" in r[0])
    assert end[1][3] is True
    assert end[1][4] == 0
