import pytest

from app.commands.base import CommandContext
from app.commands.i18n.locale_text import (
    DEFAULT_LOCALE,
    normalize_locale,
    pick_i18n,
    resolve_locale,
    tool_manifest_locale,
)


@pytest.mark.unit
def test_normalize_locale_aliases() -> None:
    assert normalize_locale("zh") == "zh-CN"
    assert normalize_locale("en") == "en-US"
    assert normalize_locale("  en-US  ") == "en-US"
    assert normalize_locale(None) == DEFAULT_LOCALE


@pytest.mark.unit
def test_pick_i18n_fallback() -> None:
    m = {"zh-CN": "一", "en-US": "two"}
    p = pick_i18n(m, "en-GB", legacy_default="legacy")
    assert p.value == "two"
    p2 = pick_i18n(m, "zh-CN", legacy_default="x")
    assert p2.value == "一"


@pytest.mark.unit
def test_tool_manifest_locale_explicit() -> None:
    assert tool_manifest_locale("en") == "en-US"
    assert tool_manifest_locale("  ") == DEFAULT_LOCALE


@pytest.mark.unit
def test_resolve_locale_uses_metadata() -> None:
    ctx = CommandContext(
        user_id="1",
        username="t",
        session_id="s",
        permissions=[],
        metadata={"locale": "en"},
    )
    assert resolve_locale(ctx) == "en-US"
