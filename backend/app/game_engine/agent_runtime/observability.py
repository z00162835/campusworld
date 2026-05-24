"""Generic observability hooks for agent runtime frameworks."""
from __future__ import annotations
from contextlib import contextmanager
import contextvars
from typing import Any, Callable, ContextManager, Iterator, Optional, Protocol


_runtime_run_id_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('agent_runtime_run_id', default=None)
_runtime_correlation_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('agent_runtime_correlation_id', default=None)
_runtime_logger_name_cv: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('agent_runtime_logger_name', default=None)
_runtime_http_exchange_logger_cv: contextvars.ContextVar[Optional[Callable[..., None]]] = contextvars.ContextVar('agent_runtime_http_exchange_logger', default=None)


def get_agent_runtime_run_id_from_context() -> Optional[str]:
    return _runtime_run_id_cv.get()


def get_agent_runtime_correlation_from_context() -> Optional[str]:
    return _runtime_correlation_cv.get()


def get_agent_runtime_logger_name_from_context() -> Optional[str]:
    return _runtime_logger_name_cv.get()


@contextmanager
def agent_runtime_observability_context(*, run_id: str, correlation_id: Optional[str], logger_name: Optional[str]=None, http_exchange_logger: Optional[Callable[..., None]]=None) -> Iterator[None]:
    run_token = _runtime_run_id_cv.set(run_id)
    corr_token = _runtime_correlation_cv.set(correlation_id)
    logger_token = _runtime_logger_name_cv.set(logger_name)
    http_logger_token = _runtime_http_exchange_logger_cv.set(http_exchange_logger)
    try:
        yield
    finally:
        _runtime_http_exchange_logger_cv.reset(http_logger_token)
        _runtime_logger_name_cv.reset(logger_token)
        _runtime_correlation_cv.reset(corr_token)
        _runtime_run_id_cv.reset(run_token)


def log_agent_runtime_http_exchange(config: Any, *, url: str, status_code: int, elapsed_ms: float, request_body: Any, response_data: Any) -> None:
    logger = _runtime_http_exchange_logger_cv.get()
    if logger is None:
        return
    logger(config, url=url, status_code=status_code, elapsed_ms=elapsed_ms, request_body=request_body, response_data=response_data)


class AgentRuntimeObservability(Protocol):
    """Framework-facing observability adapter.

    Runtime frameworks call this interface without depending on a product
    instance such as AICO. Profiles may provide concrete adapters.
    """

    def run_scope(self, *, run_id: str, correlation_id: Optional[str]) -> ContextManager[None]:
        ...

    def should_log_full_chain(self, config: Any) -> bool:
        ...

    def log_llm_call(self, config: Any, *, phase: str, system: str, user: str, spec: Any, skipped: bool) -> None:
        ...

    def log_tool_observations_text(self, config: Any, *, phase: str, observation_text: str) -> None:
        ...

    def log_http_exchange(self, config: Any, *, url: str, status_code: int, elapsed_ms: float, request_body: Any, response_data: Any) -> None:
        ...


class NoopAgentRuntimeObservability:
    """Default adapter for non-observed agent runtime profiles."""

    @contextmanager
    def run_scope(self, *, run_id: str, correlation_id: Optional[str]) -> Iterator[None]:
        with agent_runtime_observability_context(run_id=run_id, correlation_id=correlation_id):
            yield

    def should_log_full_chain(self, config: Any) -> bool:
        _ = config
        return False

    def log_llm_call(self, config: Any, *, phase: str, system: str, user: str, spec: Any, skipped: bool) -> None:
        _ = (config, phase, system, user, spec, skipped)
        return None

    def log_tool_observations_text(self, config: Any, *, phase: str, observation_text: str) -> None:
        _ = (config, phase, observation_text)
        return None

    def log_http_exchange(self, config: Any, *, url: str, status_code: int, elapsed_ms: float, request_body: Any, response_data: Any) -> None:
        _ = (config, url, status_code, elapsed_ms, request_body, response_data)
        return None
