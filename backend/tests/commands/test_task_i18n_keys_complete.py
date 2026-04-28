"""Phase B PR5: enforce both locale files cover all task error / success keys.

Plan §3 risk C — i18n keys MUST exist in both ``zh-CN`` and ``en-US``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


_LOCALES_DIR = (
    Path(__file__).resolve().parents[2] / "app" / "commands" / "i18n" / "locales"
)


_REQUIRED_ERROR_KEYS = [
    "generic",
    "forbidden",
    "not_found",
    "invalid_event",
    "version_stale",
    "already_claimed",
    "role_required",
    "precondition_failed",
    "workflow_not_found",
    "workflow_inactive",
    "pool_not_found",
    "pool_inactive",
    "publish_denied",
    "consume_denied",
    "children_not_terminal",
    "cycle_detected",
    "selector_bounds_exceeded",
    "empty_selector",
    "unknown_trait_class",
    "unknown_trait_mask",
    "expansion_backpressure",
    "unauthenticated",
    "visibility_unsupported",
]

_REQUIRED_SUCCESS_KEYS = [
    "create",
    "publish",
    "claim",
    "assign",
    "complete",
]

_REQUIRED_USAGE_KEYS = [
    "root",
    "create",
    "claim",
    "assign",
    "publish",
    "complete",
    "list",
    "show",
    "pool",
    "pool_list",
    "pool_show",
    "pool_create",
    "pool_update",
    "pool_disable",
    "pool_enable",
]


def _load(locale: str) -> Dict[str, Any]:
    raw = (_LOCALES_DIR / f"{locale}.yaml").read_text(encoding="utf-8")
    bundle = yaml.safe_load(raw) or {}
    return bundle.get("commands", {}).get("task", {})


@pytest.mark.unit
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_task_command_has_description(locale: str):
    task = _load(locale)
    assert task.get("description"), f"{locale}: commands.task.description missing"


@pytest.mark.unit
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_task_error_keys_complete(locale: str):
    task = _load(locale)
    errors = task.get("error", {})
    missing = [k for k in _REQUIRED_ERROR_KEYS if not errors.get(k)]
    assert not missing, f"{locale}: missing error keys: {missing}"


@pytest.mark.unit
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_task_success_keys_complete(locale: str):
    task = _load(locale)
    missing = []
    for evt in _REQUIRED_SUCCESS_KEYS:
        if not (task.get(evt, {}).get("success")):
            missing.append(evt)
    assert not missing, f"{locale}: missing success keys: {missing}"


@pytest.mark.unit
@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_task_usage_keys_complete(locale: str):
    task = _load(locale)
    usage = task.get("usage", {})
    missing = [k for k in _REQUIRED_USAGE_KEYS if not usage.get(k)]
    assert not missing, f"{locale}: missing usage keys: {missing}"


@pytest.mark.unit
def test_locale_files_share_same_error_key_set():
    zh = _load("zh-CN").get("error", {})
    en = _load("en-US").get("error", {})
    assert set(zh.keys()) == set(en.keys()), (
        f"locale drift in commands.task.error: zh-only={set(zh)-set(en)}, "
        f"en-only={set(en)-set(zh)}"
    )
