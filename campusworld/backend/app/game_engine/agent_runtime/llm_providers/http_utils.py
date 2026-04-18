"""Shared HTTP helpers for LLM provider clients (httpx POST + JSON)."""

from __future__ import annotations

from typing import Any, Dict


def httpx_post_json(
    url: str,
    *,
    headers: Dict[str, str],
    body: Dict[str, Any],
    timeout: float,
) -> Dict[str, Any]:
    import httpx

    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict):
        raise RuntimeError("LLM response JSON root must be an object")
    return data
