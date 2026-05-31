import pytest

from app.commands.base import CommandResult, SystemCommand
from app.commands.registry import CommandRegistry


class _DummySystemCommand(SystemCommand):
    def __init__(self, name: str, aliases=None):
        super().__init__(name=name, description="dummy", aliases=aliases or [])

    def execute(self, context, args):
        return CommandResult.success_result("ok")


def test_registry_rejects_alias_shadowing_registered_command_name():
    registry = CommandRegistry()

    assert registry.register_command(_DummySystemCommand("help")) is True
    assert registry.register_command(_DummySystemCommand("custom", aliases=["help"])) is False

    assert registry.get_command("help").name == "help"
    assert registry.get_command("custom") is None


def test_registry_rejects_name_shadowing_registered_alias():
    registry = CommandRegistry()

    assert registry.register_command(_DummySystemCommand("help", aliases=["h"])) is True
    assert registry.register_command(_DummySystemCommand("h")) is False

    assert registry.get_command("h").name == "help"


def test_registry_rejects_alias_equal_to_command_name():
    registry = CommandRegistry()

    assert registry.register_command(_DummySystemCommand("custom", aliases=["custom"])) is False
    assert registry.get_command("custom") is None


def test_registry_replaces_same_command_name_without_leaking_old_aliases():
    registry = CommandRegistry()

    assert registry.register_command(_DummySystemCommand("custom", aliases=["old"])) is True
    assert registry.register_command(_DummySystemCommand("custom", aliases=["new"])) is True

    assert registry.get_command("custom").name == "custom"
    assert registry.get_command("old") is None
    assert registry.get_command("new").name == "custom"


@pytest.mark.unit
def test_initialize_commands_alias_namespace_unique():
    from app.commands.init_commands import initialize_commands
    from app.commands.registry import command_registry

    assert initialize_commands(force_reinit=True) is True
    owner_by_token: dict[str, str] = {}
    for cmd in command_registry.get_all_commands():
        for token in [cmd.name, *list(cmd.aliases or [])]:
            prev = owner_by_token.get(token)
            assert prev in (None, cmd.name), f"token {token!r} owned by both {prev!r} and {cmd.name!r}"
            owner_by_token[token] = cmd.name


@pytest.mark.unit
def test_canonical_alias_resolution():
    from app.commands.init_commands import initialize_commands
    from app.commands.registry import command_registry

    assert initialize_commands(force_reinit=True) is True
    cases = {
        "l": "look",
        "examine": "describe",
        "ex": "describe",
        "h": "help",
        "exit": "quit",
        "walk": "go",
        "@find": "find",
    }
    for alias, primary in cases.items():
        cmd = command_registry.get_command(alias)
        assert cmd is not None, f"alias {alias!r} did not resolve"
        assert cmd.name == primary, f"alias {alias!r} -> {cmd.name!r}, expected {primary!r}"
