import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.commands.base import GameCommand
from app.commands.init_commands import register_game_commands, unregister_game_commands
from app.commands.registry import command_registry
import app.commands.init_commands as init_mod


class _DummyWorldCommand(GameCommand):
    def __init__(self, name: str, aliases=None):
        super().__init__(name=name, description="dummy", aliases=aliases or [], game_name="")

    def execute(self, context, args):
        raise NotImplementedError()


@pytest.fixture(autouse=True)
def _reset_registry_and_world_state():
    orig_commands = dict(command_registry.commands)
    orig_aliases = dict(command_registry.aliases)
    orig_by_type = {k: list(v) for (k, v) in command_registry.commands_by_type.items()}
    orig_groups = {k: list(v) for (k, v) in command_registry.command_groups.items()}
    orig_world_map = dict(init_mod._world_registered_command_names)
    yield
    command_registry.commands = orig_commands
    command_registry.aliases = orig_aliases
    command_registry.commands_by_type = orig_by_type
    command_registry.command_groups = orig_groups
    init_mod._world_registered_command_names = orig_world_map


def test_register_game_commands_rejects_name_collision():
    from app.commands.system_commands import HelpCommand

    assert command_registry.register_command(HelpCommand()) is True
    ok = register_game_commands("hicampus", [_DummyWorldCommand("help")])
    assert ok is False


def test_register_game_commands_rejects_alias_collision():
    from app.commands.system_commands import HelpCommand

    assert command_registry.register_command(HelpCommand()) is True
    ok = register_game_commands("hicampus", [_DummyWorldCommand("hicampus_echo", aliases=["h"])])
    assert ok is False


def test_register_game_commands_rejects_alias_shadowing_existing_command_name():
    from app.commands.system_commands import HelpCommand

    assert command_registry.register_command(HelpCommand()) is True
    ok = register_game_commands("hicampus", [_DummyWorldCommand("hicampus_echo", aliases=["help"])])

    assert ok is False
    assert command_registry.get_command("help").name == "help"


def test_register_game_commands_rejects_name_shadowing_existing_alias():
    from app.commands.system_commands import HelpCommand

    assert command_registry.register_command(HelpCommand()) is True
    ok = register_game_commands("hicampus", [_DummyWorldCommand("h")])

    assert ok is False
    assert command_registry.get_command("h").name == "help"


def test_register_game_commands_rejects_batch_name_alias_collision():
    ok = register_game_commands(
        "hicampus",
        [
            _DummyWorldCommand("hicampus_alpha", aliases=["hicampus_beta"]),
            _DummyWorldCommand("hicampus_beta"),
        ],
    )

    assert ok is False
    assert command_registry.get_command("hicampus_alpha") is None
    assert command_registry.get_command("hicampus_beta") is None


def test_register_game_commands_rejects_alias_equal_to_command_name():
    ok = register_game_commands("hicampus", [_DummyWorldCommand("hicampus_echo", aliases=["hicampus_echo"])])

    assert ok is False
    assert command_registry.get_command("hicampus_echo") is None


def test_register_then_unregister_game_commands_success():
    cmd = _DummyWorldCommand("hicampus_echo", aliases=["he"])
    ok = register_game_commands("hicampus", [cmd])
    assert ok is True
    assert command_registry.get_command("hicampus_echo") is not None
    assert command_registry.get_command("he") is not None

    out = unregister_game_commands("hicampus")
    assert out is True
    assert command_registry.get_command("hicampus_echo") is None
    assert command_registry.get_command("he") is None
