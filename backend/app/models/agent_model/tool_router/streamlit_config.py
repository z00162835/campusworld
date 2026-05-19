"""Configuration loader for tool-router Streamlit hub."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_STREAMLIT_CONFIG_PATH = Path(__file__).resolve().parent / "streamlit_config.json"


@dataclass
class ToolRouterStreamlitConfig:
    model_presets: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ui_defaults: Dict[str, Any] = field(default_factory=dict)
    noisy_loggers: List[str] = field(default_factory=list)
    deprecated_model_ids: Dict[str, str] = field(default_factory=dict)
    training_limits: Dict[str, Dict[str, Any]] = field(default_factory=dict)


def _default_model_presets() -> Dict[str, Dict[str, Any]]:
    return {
        "Qwen2.5-0.5B (baseline)": {
            "base_model": "Qwen/Qwen2.5-0.5B-Instruct",
            "epochs": 2,
            "batch_size": 2,
            "grad_accum": 8,
            "lr": 2e-4,
            "max_seq_len": 2048,
            "completion_tokens_router": 256,
            "completion_tokens_slot": 384,
            "bf16": True,
        },
        "Qwen3-4B (candidate)": {
            "base_model": "Qwen/Qwen3-4B-Instruct-2507",
            "epochs": 2,
            "batch_size": 1,
            "grad_accum": 16,
            "lr": 1.5e-4,
            "max_seq_len": 2048,
            "completion_tokens_router": 256,
            "completion_tokens_slot": 384,
            "bf16": True,
        },
        "Custom": {},
    }


def _default_ui_defaults() -> Dict[str, Any]:
    return {
        "sample_default_path_router": "app/models/agent_model/tool_router/data/shards/router_train_part00.jsonl",
        "sample_default_path_slot": "app/models/agent_model/tool_router/data/shards/slot_train_part00.jsonl",
        "training_output_dir_router": "artifacts/tool_router/router_head/manual_run",
        "training_output_dir_slot": "artifacts/tool_router/slot/manual_run",
        "eval_gold_default": "app/models/agent_model/tool_router/data/shards/router_test_part00.jsonl",
        "eval_pred_default": "app/models/agent_model/tool_router/data/shards/router_pred.jsonl",
        "eval_validate_gold_default": True,
        "log_tail_max_chars": 20000,
    }


def _default_noisy_loggers() -> List[str]:
    return [
        "fsevents",
        "watchdog",
        "watchdog.observers",
        "watchdog.observers.fsevents",
        "watchdog.events",
    ]


def _default_deprecated_model_ids() -> Dict[str, str]:
    return {
        "Qwen/Qwen3-4B-Instruct": "Qwen/Qwen3-4B-Instruct-2507",
    }


def _default_training_limits() -> Dict[str, Dict[str, Any]]:
    return {
        "epochs": {"min": 1, "max": 50, "step": 1},
        "batch_size": {"min": 1, "max": 64, "step": 1},
        "grad_accum": {"min": 1, "max": 128, "step": 1},
        "lr": {"min": 1e-7, "max": 1e-1, "step": 1e-4},
        "max_seq_len": {"min": 64, "max": 8192, "step": 64},
        "completion_tokens": {"min": 32, "max": 2048, "step": 32},
    }


def load_streamlit_config(path: Path | None = None) -> ToolRouterStreamlitConfig:
    cfg_path = (path or DEFAULT_STREAMLIT_CONFIG_PATH).resolve()
    raw: Dict[str, Any] = {}
    if cfg_path.exists():
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    model_presets = raw.get("model_presets")
    if not isinstance(model_presets, dict) or not model_presets:
        model_presets = _default_model_presets()
    ui_defaults = raw.get("ui_defaults")
    if not isinstance(ui_defaults, dict):
        ui_defaults = {}
    merged_ui_defaults = _default_ui_defaults()
    merged_ui_defaults.update(ui_defaults)
    noisy_loggers = raw.get("noisy_loggers")
    if not isinstance(noisy_loggers, list) or not noisy_loggers:
        noisy_loggers = _default_noisy_loggers()
    noisy_loggers = [str(x).strip() for x in noisy_loggers if str(x).strip()]
    deprecated_model_ids = raw.get("deprecated_model_ids")
    if not isinstance(deprecated_model_ids, dict):
        deprecated_model_ids = _default_deprecated_model_ids()
    training_limits = raw.get("training_limits")
    if not isinstance(training_limits, dict):
        training_limits = {}
    merged_training_limits = _default_training_limits()
    for key, cfg in training_limits.items():
        if not isinstance(cfg, dict):
            continue
        merged_training_limits[str(key)] = {
            **merged_training_limits.get(str(key), {}),
            **cfg,
        }
    return ToolRouterStreamlitConfig(
        model_presets=model_presets,
        ui_defaults=merged_ui_defaults,
        noisy_loggers=noisy_loggers,
        deprecated_model_ids={str(k): str(v) for k, v in deprecated_model_ids.items()},
        training_limits=merged_training_limits,
    )
