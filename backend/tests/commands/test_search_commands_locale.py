"""D5-C: search_commands matches only the current-context display language."""

from __future__ import annotations

from types import MethodType

import pytest

from app.commands.base import CommandContext
from app.commands.init_commands import initialize_commands
from app.commands.policy import AuthzDecision
from app.commands.registry import command_registry


@pytest.fixture(scope="module", autouse=True)
def _load():
    initialize_commands()
    yield


@pytest.fixture(autouse=True)
def _allow_all_for_policy(monkeypatch):
    """``get_available_commands`` requires authz; stub allow for locale search tests."""

    def _allow(self, command, context):
        return AuthzDecision(allowed=True)

    monkeypatch.setattr(
        command_registry.policy_evaluator,
        "evaluate",
        MethodType(_allow, command_registry.policy_evaluator),
    )


def _ctx(locale: str) -> CommandContext:
    return CommandContext(
        user_id="1",
        username="u",
        session_id="s",
        permissions=[],
        metadata={"locale": locale},
    )


@pytest.mark.unit
def test_search_help_by_zh_phrase_only_when_locale_zh() -> None:
    r = command_registry.search_commands("列出", context=_ctx("zh-CN"))
    names = {c.name for c in r}
    assert "help" in names


@pytest.mark.unit
def test_search_help_zh_phrase_misses_when_locale_en() -> None:
    r = command_registry.search_commands("列出", context=_ctx("en-US"))
    names = {c.name for c in r}
    assert "help" not in names


@pytest.mark.unit
def test_search_help_by_english_when_locale_en() -> None:
    r = command_registry.search_commands("List available", context=_ctx("en-US"))
    names = {c.name for c in r}
    assert "help" in names
