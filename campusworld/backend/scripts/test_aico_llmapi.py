#!/usr/bin/env python3
"""
Probe LLM HTTP connectivity for ``agents.llm.by_service_id.<service_id>``.

Loads merged config like the app (``settings.yaml`` + ``settings.<ENV>.yaml`` via
``ConfigLoader``). All endpoints and keys come from YAML: ``base_url``,
``api_key_env``, ``model``, etc. No regional CLI — point ``base_url`` at your
vendor (e.g. MiniMax native ``.../text/chatcompletion_v2`` or Anthropic-compat
``.../anthropic``).

- MiniMax native: Bearer, ``chatcompletion_v2`` shape
  (https://platform.minimax.io/docs/api-reference/text-post)
- MiniMax Anthropic-compatible: Bearer + ``x-api-key``, ``POST .../v1/messages``
  (https://platform.minimax.io/docs/api-reference/text-anthropic-api)

Optional YAML: ``extra.minimax_http_api: native | anthropic`` overrides URL
heuristics. Otherwise: URL contains ``chatcompletion`` or ``/text/`` → native;
contains ``anthropic`` → Anthropic Messages.

Usage (from backend/):
  export AICO_OPENAI_API_KEY=...
  python scripts/test_aico_llmapi.py
  python scripts/test_aico_llmapi.py -v --config config/settings.dev.yaml
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

LLM_BY_SERVICE_PATH = ("agents", "llm", "by_service_id")

# This script uses print() for output; keep stdlib/third-party loggers quiet (httpx/httpcore DEBUG, campusworld INFO on import).
_NOISY_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "urllib3.connectionpool",
    "campusworld",
    "campusworld.logging",
    "campusworld.config_manager",
    "campusworld.config_loader",
)


def _silence_noisy_loggers() -> None:
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
    # One-shot bootstrap line from LoggingManager ("默认日志文件已配置") uses this logger.
    logging.getLogger("campusworld.logging").setLevel(logging.ERROR)


def _normalize_api_key(raw: str) -> str:
    s = (raw or "").strip()
    if s.lower().startswith("bearer "):
        s = s[7:].strip()
    return s


def _try_load_dotenv() -> bool:
    dotenv_path = BACKEND_ROOT / ".env"
    if not dotenv_path.exists():
        return False
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        print(f"Note: {dotenv_path} exists but python-dotenv is not installed; skipped.")
        return False
    load_dotenv(dotenv_path=dotenv_path, override=False)
    return True


def _get_by_path(root: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    cur: Any = root
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _load_merged_settings(*, config_dir: Path, env: str) -> Dict[str, Any]:
    from app.core.config_manager import ConfigLoader

    loader = ConfigLoader(config_dir, env)
    base = loader.load_base_config() or {}
    overlay = loader.load_env_config() or {}
    return loader._merge_config(base, overlay)


def _get_llm_service_config(merged: Dict[str, Any], service_id: str) -> Dict[str, Any]:
    reg = _get_by_path(merged, LLM_BY_SERVICE_PATH)
    if not isinstance(reg, dict):
        raise KeyError(
            f"missing or invalid {' -> '.join(LLM_BY_SERVICE_PATH)} in merged config"
        )
    if service_id not in reg:
        raise KeyError(f"missing service_id {service_id!r} under agents.llm.by_service_id")
    block = reg[service_id]
    if not isinstance(block, dict):
        raise TypeError(f"agents.llm.by_service_id.{service_id} must be a mapping")
    return block


def _provider_is_minimax(provider: str) -> bool:
    return (provider or "").strip().lower() in ("minimax", "minmax")


def _openai_chat_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        b = "https://api.openai.com/v1"
    if b.endswith("/chat/completions"):
        return b
    return f"{b}/chat/completions"


def _minimax_mode(base_url: str, extra: Dict[str, Any]) -> str:
    """Return 'native' or 'anthropic'."""
    raw = extra.get("minimax_http_api")
    if raw is not None:
        v = str(raw).strip().lower()
        if v in ("anthropic", "native"):
            return v
    b = (base_url or "").lower()
    if "anthropic" in b:
        return "anthropic"
    if "chatcompletion" in b or "/text/" in b:
        return "native"
    return "native"


def _minimax_native_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("agents.llm: base_url is required for MinMax")
    if "chatcompletion" in b:
        return b
    return f"{b}/v1/text/chatcompletion_v2"


def _minimax_anthropic_url(base_url: str) -> str:
    b = (base_url or "").strip().rstrip("/")
    if not b:
        raise ValueError("agents.llm: base_url is required for MinMax Anthropic mode")
    if b.endswith("/v1/messages"):
        return b
    if b.endswith("/anthropic"):
        return f"{b}/v1/messages"
    if "/anthropic" in b:
        return f"{b}/v1/messages"
    return f"{b}/anthropic/v1/messages"


def _extra_for_body(extra: Dict[str, Any]) -> Dict[str, Any]:
    """Do not send transport hints to the HTTP API."""
    return {k: v for k, v in extra.items() if k != "minimax_http_api"}


def _anthropic_temperature(value: Any) -> Optional[float]:
    try:
        t = float(value)
    except (TypeError, ValueError):
        return None
    if t <= 0.0:
        return 0.01
    if t > 1.0:
        return 1.0
    return t


def _extract_minimax_native(data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    br = data.get("base_resp")
    if isinstance(br, dict) and br.get("status_code") not in (None, 0):
        return "", f"MiniMax base_resp: {br.get('status_code')!r} {br.get('status_msg', '')!r}"
    choices = data.get("choices") or []
    if not choices:
        return "", "empty choices[]"
    first = choices[0]
    if isinstance(first, dict):
        msg = first.get("message") or first.get("delta")
        if isinstance(msg, dict) and msg.get("content") is not None:
            return str(msg["content"]).strip(), None
    return "", "could not parse choices[0].message.content"


def _extract_anthropic_messages(data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    err = data.get("error")
    if isinstance(err, dict):
        return "", f"API error: {err.get('message') or err.get('type')!r}"
    content = data.get("content")
    if not isinstance(content, list):
        return "", "missing content[] (Anthropic response shape)"
    texts = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            texts.append(str(block.get("text") or ""))
    out = "\n".join(p.strip() for p in texts if p.strip()).strip()
    return (out, None) if out else ("", "no text blocks in content[]")


def _extract_openai_chat(data: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return "", "empty or invalid choices[]"
    msg = (choices[0].get("message") or choices[0].get("delta")) or {}
    if isinstance(msg, dict) and msg.get("content") is not None:
        return str(msg["content"]).strip(), None
    return "", "could not parse choices[0].message.content"


def run_probe(
    *,
    cfg: Dict[str, Any],
    user_prompt: str,
    timeout_sec: float,
    verbose: bool,
) -> int:
    import httpx

    _silence_noisy_loggers()

    provider = str(cfg.get("provider") or "")
    base_url = str(cfg.get("base_url") or "")
    api_key_env = str(cfg.get("api_key_env") or "").strip()
    model = str(cfg.get("model") or "").strip()
    temperature = cfg.get("temperature", 0.2)
    raw_max = cfg.get("max_tokens", 256)
    extra = cfg.get("extra") if isinstance(cfg.get("extra"), dict) else {}

    try:
        max_tokens = max(1, min(int(raw_max) if raw_max is not None else 256, 512))
    except (TypeError, ValueError):
        max_tokens = 256

    if not api_key_env:
        print("error: api_key_env is empty in LLM config block")
        return 2
    api_key = _normalize_api_key(os.environ.get(api_key_env, "") or "")
    if not api_key:
        print(f"error: environment variable {api_key_env!r} is not set or empty")
        return 2
    if not model:
        print("error: model is empty in LLM config block")
        return 2

    system_prompt = str(
        cfg.get("system_prompt")
        or "You are a helpful assistant. Reply briefly for connectivity tests."
    )

    minimax = _provider_is_minimax(provider)
    kind = "openai_chat"
    mm_mode: Optional[str] = None

    if minimax:
        mm_mode = _minimax_mode(base_url, extra)
        if mm_mode == "anthropic" and (
            "chatcompletion" in (base_url or "").lower() or "/text/" in (base_url or "").lower()
        ):
            print(
                "error: extra.minimax_http_api: anthropic conflicts with a native text base_url; "
                "set base_url to your vendor's Anthropic root (e.g. https://api.example.com/anthropic)"
            )
            return 2
        kind = "minimax_native" if mm_mode == "native" else "anthropic_messages"
        xb = _extra_for_body(extra)
        if mm_mode == "native":
            url = _minimax_native_url(base_url)
            body = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "temperature": float(temperature) if temperature is not None else 0.2,
                "max_completion_tokens": int(max_tokens),
            }
            body.update(xb)
        else:
            url = _minimax_anthropic_url(base_url)
            body = {
                "model": model,
                "max_tokens": int(max_tokens),
                "system": system_prompt,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": user_prompt}],
                    }
                ],
                "stream": False,
            }
            t_anth = _anthropic_temperature(temperature)
            if t_anth is not None:
                body["temperature"] = t_anth
            body.update(xb)
        headers = (
            {
                "Authorization": f"Bearer {api_key}",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            if kind == "anthropic_messages"
            else {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )
    else:
        url = _openai_chat_url(base_url)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": float(temperature) if temperature is not None else 0.2,
            "max_tokens": int(max_tokens),
        }
        body.update(_extra_for_body(extra))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    print(f"provider: {provider or '(default openai-compatible)'}")
    if minimax and mm_mode is not None:
        print(f"minimax transport: {mm_mode} (base_url + optional extra.minimax_http_api)")
    print(f"POST {url}")
    print(f"model: {model}")
    if verbose:
        print("request body:")
        print(json.dumps(body, ensure_ascii=False, indent=2))

    try:
        with httpx.Client(timeout=timeout_sec) as client:
            r = client.post(url, headers=headers, json=body)
    except httpx.RequestError as e:
        print(f"error: request failed: {e}")
        return 1

    print(f"HTTP {r.status_code}")
    if r.status_code >= 400:
        print(r.text[:2000])
        return 1

    try:
        data = r.json()
    except Exception:
        print("error: response is not JSON")
        print(r.text[:2000])
        return 1

    if verbose:
        print("response JSON:")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:8000])

    if not isinstance(data, dict):
        print("error: JSON root is not an object")
        return 1

    if kind == "minimax_native":
        text, warn = _extract_minimax_native(data)
    elif kind == "anthropic_messages":
        text, warn = _extract_anthropic_messages(data)
    else:
        text, warn = _extract_openai_chat(data)
    if warn:
        print(f"warning: {warn}")
    if text:
        preview = text if len(text) <= 500 else text[:500] + "…"
        print("assistant content:")
        print(preview)
        print("ok: endpoint reachable and returned assistant text")
        return 0

    print("error: no assistant text parsed from response")
    if not verbose:
        print("(run with --verbose for full JSON)")
    return 1


def main() -> int:
    _silence_noisy_loggers()

    parser = argparse.ArgumentParser(description="Test agents.llm HTTP API from merged YAML.")
    parser.add_argument("--config-dir", type=Path, default=None, help="Config directory (default: backend/config)")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Any file under config/ — its parent is used as config_dir",
    )
    parser.add_argument(
        "--env",
        default=None,
        metavar="ENVIRONMENT",
        help="Merge overlay (default: $ENVIRONMENT or development)",
    )
    parser.add_argument("--service-id", default="aico", help="agents.llm.by_service_id key")
    parser.add_argument("--prompt", default="Reply with exactly one word: OK.", help="User message")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout (seconds)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print request/response JSON")
    args = parser.parse_args()

    if args.config is not None:
        p = args.config if args.config.is_absolute() else (BACKEND_ROOT / args.config).resolve()
        if not p.is_file():
            print(f"error: config file not found: {p}")
            return 2
        config_dir = p.parent
    elif args.config_dir is not None:
        config_dir = (
            args.config_dir
            if args.config_dir.is_absolute()
            else (BACKEND_ROOT / args.config_dir).resolve()
        )
    else:
        config_dir = (BACKEND_ROOT / "config").resolve()

    if not config_dir.is_dir():
        print(f"error: config directory not found: {config_dir}")
        return 2
    if not (config_dir / "settings.yaml").is_file():
        print(f"error: base settings missing: {config_dir / 'settings.yaml'}")
        return 2

    env_name = (args.env if args.env is not None else os.getenv("ENVIRONMENT", "development")).strip()
    if not env_name:
        print("error: empty --env / ENVIRONMENT")
        return 2

    _try_load_dotenv()

    try:
        merged = _load_merged_settings(config_dir=config_dir, env=env_name)
        svc = _get_llm_service_config(merged, args.service_id)
    except Exception as e:
        print(f"error: {e}")
        return 2

    _silence_noisy_loggers()

    print(f"config_dir: {config_dir}")
    print(f"ENVIRONMENT (merge): {env_name!r}")
    print(f"service_id: {args.service_id}")
    print(f"api_key_env: {svc.get('api_key_env', '')}")

    return run_probe(
        cfg=svc,
        user_prompt=args.prompt,
        timeout_sec=args.timeout,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    raise SystemExit(main())
