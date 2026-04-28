"""Shared HTTP helpers for LLM provider clients (httpx POST + JSON)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict

# Response / request previews for ERROR logs (full bodies can exceed provider limits).
_MAX_ERROR_RESPONSE_CHARS = 12_000
_MAX_REQUEST_SUMMARY_CHARS = 8_000


def _summarize_llm_request_body(body: Dict[str, Any]) -> str:
    """Compact JSON for failure logs — avoids dumping megabyte ``system`` / messages."""
    out: Dict[str, Any] = {}
    for k, v in body.items():
        if k == "messages" and isinstance(v, list):
            parts = []
            for m in v[:8]:
                if not isinstance(m, dict):
                    parts.append(str(m)[:200])
                    continue
                role = m.get("role", "?")
                content = m.get("content")
                if isinstance(content, list):
                    types = [
                        str(b.get("type", "?"))
                        for b in content
                        if isinstance(b, dict)
                    ]
                    parts.append(f"{role}:blocks={len(content)} types={types[:6]}")
                else:
                    t = str(content or "")
                    parts.append(f"{role}:text_len={len(t)}")
            out["messages"] = parts
            if len(v) > 8:
                out["messages_total"] = len(v)
        elif k == "tools" and isinstance(v, list):
            names = []
            for t in v[:32]:
                if isinstance(t, dict):
                    names.append(str(t.get("name") or "?"))
                else:
                    names.append(str(t)[:80])
            out["tools"] = names
            if len(v) > 32:
                out["tools_total"] = len(v)
        elif k == "system":
            s = str(v) if v is not None else ""
            out["system"] = f"<str chars={len(s)}>"
        else:
            out[k] = v
    try:
        s = json.dumps(out, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(out)
    if len(s) > _MAX_REQUEST_SUMMARY_CHARS:
        return s[: _MAX_REQUEST_SUMMARY_CHARS] + "…"
    return s


def _log_llm_http_error(
    *,
    url: str,
    status_code: int,
    elapsed_ms: float,
    body: Dict[str, Any],
    response_text: str,
) -> None:
    """Always-on ERROR log so MiniMax/OpenAI 4xx/5xx can be diagnosed without DEBUG."""
    rt = (response_text or "").strip()
    if len(rt) > _MAX_ERROR_RESPONSE_CHARS:
        rt = rt[:_MAX_ERROR_RESPONSE_CHARS] + "…"
    summary = _summarize_llm_request_body(body)
    prefix = ""
    try:
        from app.core.log import LoggerNames
        from app.core.log.aico_observability import (
            get_aico_correlation_from_context,
            get_aico_run_id_from_context,
        )

        rid = get_aico_run_id_from_context()
        corr = get_aico_correlation_from_context()
        if rid is not None or corr is not None:
            prefix = f"run_id={rid!s} correlation_id={corr!s}\n"
            log = logging.getLogger(LoggerNames.AICO_AGENT)
        else:
            log = logging.getLogger("app.game_engine.llm_http")
    except Exception:
        log = logging.getLogger("app.game_engine.llm_http")

    log.error(
        "%sllm_http_error status=%s elapsed_ms=%.2f url=%s\n--- response body ---\n%s\n"
        "--- request summary (truncated) ---\n%s",
        prefix,
        status_code,
        elapsed_ms,
        url,
        rt or "(empty)",
        summary,
    )


def httpx_post_json(
    url: str,
    *,
    headers: Dict[str, str],
    body: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:
    import httpx

    t0 = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=body)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        status = r.status_code
        if status >= 400:
            try:
                raw = r.text or ""
            except Exception:
                raw = ""
            _log_llm_http_error(
                url=url,
                status_code=status,
                elapsed_ms=elapsed_ms,
                body=body,
                response_text=raw,
            )
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("LLM response JSON root must be an object")
    try:
        from app.core.config_manager import get_config
        from app.core.log.aico_observability import log_aico_http_exchange

        log_aico_http_exchange(
            get_config(),
            url=url,
            status_code=status,
            elapsed_ms=elapsed_ms,
            request_body=body,
            response_data=data,
        )
    except Exception:
        pass
    return data
