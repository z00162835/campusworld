"""
AICO 优化可观测：专用文件日志（与主应用日志分离）。

配置见 agents.llm.by_service_id.aico.observability；挂载由 ConfigManager 在加载/重载后调用 configure_aico_observability_logging。

全链路（仅开发向）：``enabled`` 且 ``level: DEBUG`` 时，在同一文件内额外记录每轮 LLM 的 system/user、LlmCallSpec、ToolGather 文本摘要、HTTP 往返摘要；长文本统一受 ``max_phase_output_chars`` 约束（0 表示不截断）。
"""

from __future__ import annotations

import contextvars
import json
import logging
from typing import Any, Dict, Optional

from app.core.log import LoggerNames
from app.core.log.manager import FlushingRotatingFileHandler
from app.core.paths import get_backend_root

_aico_run_id_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "aico_run_id", default=None
)
_aico_correlation_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "aico_correlation_id", default=None
)
# True only during run_npc_agent_nlp_tick for service_id=aico when dev-chain logging applies.
_aico_full_chain_tick_cv: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "aico_full_chain_tick", default=False
)

# Alias for tests and call sites that prefer a module-level string.
AICO_OBSERVABILITY_LOGGER_NAME = LoggerNames.AICO_AGENT

_DEFAULT_LOG_REL = "logs/agent/aico.log"


def get_aico_observability_config(config_manager: Any) -> Dict[str, Any]:
    """Return agents.llm.by_service_id.aico.observability dict or {}."""
    if config_manager is None:
        return {}
    raw = config_manager.get("agents.llm.by_service_id.aico.observability")
    return raw if isinstance(raw, dict) else {}


def is_aico_observability_enabled(config_manager: Any) -> bool:
    cfg = get_aico_observability_config(config_manager)
    return bool(cfg.get("enabled"))


def get_aico_max_phase_output_chars(config_manager: Any) -> int:
    cfg = get_aico_observability_config(config_manager)
    try:
        v = int(cfg.get("max_phase_output_chars", 4000))
        return v
    except (TypeError, ValueError):
        return 4000


def is_aico_dev_chain_verbose(config_manager: Any) -> bool:
    """True when observability is on and level is DEBUG (full-chain logging)."""
    if not is_aico_observability_enabled(config_manager):
        return False
    cfg = get_aico_observability_config(config_manager)
    return str(cfg.get("level") or "INFO").upper() == "DEBUG"


def should_emit_aico_full_chain_logs(config_manager: Any) -> bool:
    """YAML DEBUG + only during an AICO npc_agent tick (see set_aico_full_chain_tick)."""
    return is_aico_dev_chain_verbose(config_manager) and is_aico_full_chain_tick()


def set_aico_observability_context(*, run_id: str, correlation_id: Optional[str]) -> None:
    _aico_run_id_cv.set(run_id)
    _aico_correlation_cv.set(correlation_id)


def clear_aico_observability_context() -> None:
    _aico_run_id_cv.set(None)
    _aico_correlation_cv.set(None)


def set_aico_full_chain_tick(active: bool) -> None:
    """Mark current NLP tick as AICO + DEBUG full-chain (see run_npc_agent_nlp_tick)."""
    _aico_full_chain_tick_cv.set(active)


def clear_aico_full_chain_tick() -> None:
    _aico_full_chain_tick_cv.set(False)


def is_aico_full_chain_tick() -> bool:
    return bool(_aico_full_chain_tick_cv.get())


def get_aico_run_id_from_context() -> Optional[str]:
    return _aico_run_id_cv.get()


def get_aico_correlation_from_context() -> Optional[str]:
    return _aico_correlation_cv.get()


def truncate_for_aico_log(text: str, max_chars: int) -> str:
    if not text:
        return ""
    if max_chars <= 0:
        return text
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…"


def _json_preview(obj: Any, max_chars: int) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(obj)
    if max_chars <= 0:
        return s
    return truncate_for_aico_log(s, max_chars)


def log_aico_llm_call(
    config_manager: Any,
    *,
    phase: str,
    system: str,
    user: str,
    spec: Any,
    skipped: bool,
) -> None:
    if not should_emit_aico_full_chain_logs(config_manager):
        return
    budget = get_aico_max_phase_output_chars(config_manager)
    log = logging.getLogger(LoggerNames.AICO_AGENT)
    mode = getattr(spec, "mode", None)
    spec_dict = {
        "mode": mode.value if mode is not None and hasattr(mode, "value") else str(mode),
        "model": getattr(spec, "model", None),
        "temperature": getattr(spec, "temperature", None),
        "max_tokens": getattr(spec, "max_tokens", None),
        "timeout_sec": getattr(spec, "timeout_sec", None),
    }
    log.debug(
        "aico_llm_call phase=%s skipped=%s run_id=%s correlation_id=%s spec=%s\n--- system ---\n%s\n--- user ---\n%s",
        phase,
        skipped,
        get_aico_run_id_from_context(),
        get_aico_correlation_from_context(),
        spec_dict,
        truncate_for_aico_log(system or "", budget),
        truncate_for_aico_log(user or "", budget),
    )


def log_aico_tool_observations_text(config_manager: Any, *, phase: str, observation_text: str) -> None:
    if not should_emit_aico_full_chain_logs(config_manager) or not (observation_text or "").strip():
        return
    budget = get_aico_max_phase_output_chars(config_manager)
    log = logging.getLogger(LoggerNames.AICO_AGENT)
    log.debug(
        "aico_tool_observations phase=%s run_id=%s correlation_id=%s chars=%s\n%s",
        phase,
        get_aico_run_id_from_context(),
        get_aico_correlation_from_context(),
        len(observation_text),
        truncate_for_aico_log(observation_text, budget),
    )


def log_aico_http_exchange(
    config_manager: Any,
    *,
    url: str,
    status_code: int,
    elapsed_ms: float,
    request_body: Any,
    response_data: Any,
) -> None:
    if not should_emit_aico_full_chain_logs(config_manager):
        return
    budget = get_aico_max_phase_output_chars(config_manager)
    log = logging.getLogger(LoggerNames.AICO_AGENT)
    req_preview = _json_preview(request_body, budget)
    resp_preview = _json_preview(response_data, budget)
    log.debug(
        "aico_http url=%s status=%s elapsed_ms=%.2f run_id=%s correlation_id=%s\n--- request ---\n%s\n--- response ---\n%s",
        url,
        status_code,
        elapsed_ms,
        get_aico_run_id_from_context(),
        get_aico_correlation_from_context(),
        req_preview,
        resp_preview,
    )


def _parse_size(size_str: str) -> int:
    size_str = (size_str or "10MB").upper().strip()
    if size_str.endswith("KB"):
        return int(size_str[:-2]) * 1024
    if size_str.endswith("MB"):
        return int(size_str[:-2]) * 1024 * 1024
    if size_str.endswith("GB"):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    try:
        return int(size_str)
    except ValueError:
        return 10 * 1024 * 1024


def configure_aico_observability_logging(config_manager: Any) -> None:
    """
    Idempotent: (re)attach a dedicated FileHandler for app.agent.aico when enabled.
    When disabled, clears handlers on that logger; logger does not propagate to root.
    """
    logger = logging.getLogger(LoggerNames.AICO_AGENT)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    logger.propagate = False
    obs = get_aico_observability_config(config_manager)
    if not obs.get("enabled"):
        # No handlers while disabled; NOTSET avoids pinning a level until re-enabled.
        logger.setLevel(logging.NOTSET)
        logger.propagate = True
        return

    level_name = str(obs.get("level") or "INFO").upper()
    try:
        logger.setLevel(getattr(logging, level_name))
    except AttributeError:
        logger.setLevel(logging.INFO)

    log_rel = str(obs.get("log_path") or _DEFAULT_LOG_REL).strip() or _DEFAULT_LOG_REL
    backend_root = get_backend_root(config_manager)
    full_path = (backend_root / log_rel).resolve()
    full_path.parent.mkdir(parents=True, exist_ok=True)

    max_size = _parse_size(str(obs.get("max_file_size") or "10MB"))
    try:
        backup_count = int(obs.get("backup_count", 5))
    except (TypeError, ValueError):
        backup_count = 5

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"
    if config_manager is not None:
        log_global = config_manager.get("logging", {}) or {}
        if isinstance(log_global, dict):
            fmt = log_global.get("format", fmt)
            date_fmt = log_global.get("date_format", date_fmt)

    formatter = logging.Formatter(fmt, date_fmt)
    fh = FlushingRotatingFileHandler(
        full_path,
        maxBytes=max_size,
        backupCount=backup_count,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
