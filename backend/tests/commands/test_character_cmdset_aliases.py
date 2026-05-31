import pytest

from app.commands.init_commands import initialize_commands
from app.commands.registry import collect_all_command_tokens, command_registry
from app.commands.cmdset import CharacterCmdSet


@pytest.mark.unit
def test_character_cmdset_has_no_registry_token_overlap():
    assert initialize_commands(force_reinit=True) is True
    reg_tokens = collect_all_command_tokens(command_registry.commands, command_registry.aliases)
    cs = CharacterCmdSet()
    cs_tokens = set(cs.commands.keys()) | set(cs.aliases.keys())
    overlap = cs_tokens & reg_tokens
    assert not overlap, f"CharacterCmdSet overlaps registry: {sorted(overlap)}"


@pytest.mark.unit
def test_character_cmdset_does_not_resolve_global_look_alias():
    assert initialize_commands(force_reinit=True) is True
    cs = CharacterCmdSet()
    assert cs.get_command("l") is None
    assert cs.get_command("look") is None
    assert cs.get_command("walk") is None


@pytest.mark.unit
def test_character_cmdset_keeps_non_conflicting_commands():
    assert initialize_commands(force_reinit=True) is True
    cs = CharacterCmdSet()
    for name in ("run", "jump", "rest", "talk", "charstats"):
        assert cs.get_command(name) is not None, f"missing CharacterCmdSet command {name!r}"
