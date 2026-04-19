"""Shared HTTP helpers for LLM provider clients (httpx POST + JSON)."""

from __future__ import annotations

import time
from typing import Any, Dict


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
