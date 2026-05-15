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
