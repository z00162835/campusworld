"""Agent Skill registry / definition / runner unit tests."""
from __future__ import annotations
import os
from pathlib import Path

import pytest

from app.game_engine.agent_runtime.skills.skill_definition import (
    SkillActivation,
    SkillBodyLoad,
    SkillDefinition,
    SkillImplementation,
    parse_skill_md,
)
from app.game_engine.agent_runtime.skills.skill_registry import SkillRegistry
from app.game_engine.agent_runtime.skills.skill_runner import SkillRunner


def _write_skill(dir_path: Path, frontmatter: str, body: str = "guidance body") -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n\n{body}", encoding="utf-8")


def _make_def(**overrides) -> SkillDefinition:
    base = dict(
        name="problem_framing",
        description="Frame the user problem before acting. Use when the user asks an open question.",
        activation_mode="phase_mapped",
        allowed_in_react_states=("plan",),
        implementation=SkillImplementation(mode="prompt"),
    )
    base.update(overrides)
    return SkillDefinition(**base)


class TestSkillDefinition:
    def test_phase_mapped_requires_states(self):
        with pytest.raises(ValueError):
            _make_def(allowed_in_react_states=())

    def test_model_selected_forbids_states(self):
        with pytest.raises(ValueError):
            _make_def(activation_mode="model_selected", allowed_in_react_states=("plan",))

    def test_model_selected_no_states_ok(self):
        d = _make_def(activation_mode="model_selected", allowed_in_react_states=())
        assert d.activation_mode == "model_selected"

    def test_description_required_nonempty(self):
        with pytest.raises(ValueError):
            _make_def(description="")

    def test_description_max_length(self):
        with pytest.raises(ValueError):
            _make_def(description="x" * 1025)

    def test_name_regex_rejects_uppercase(self):
        with pytest.raises(ValueError):
            _make_def(name="BadName")

    def test_display_name_defaults_to_name(self):
        d = _make_def()
        assert d.display_name is None
        assert d.effective_display_name == "problem_framing"

    def test_invalid_activation_mode_rejected(self):
        with pytest.raises(ValueError, match="invalid activation_mode"):
            _make_def(activation_mode="phase_maped")

    def test_invalid_category_rejected(self):
        with pytest.raises(ValueError, match="invalid category"):
            _make_def(category="foo")

    def test_invalid_side_effect_level_rejected(self):
        with pytest.raises(ValueError, match="invalid side_effect_level"):
            _make_def(side_effect_level="write_medium")


class TestParseSkillMd:
    def test_parse_frontmatter_and_body(self, tmp_path):
        src = (
            "---\n"
            "name: retrieval_reasoning\n"
            "description: >-\n  retrieve then reason.\n"
            "activation_mode: phase_mapped\n"
            "allowed_in_react_states: [plan, do]\n"
            "implementation:\n  mode: prompt\n"
            "---\n\n# Body\n\nDo the thing.\n"
        )
        (defn, body) = parse_skill_md(src, dir_name="retrieval_reasoning")
        assert defn.name == "retrieval_reasoning"
        assert "retrieve then reason" in defn.description
        assert defn.allowed_in_react_states == ("plan", "do")
        assert defn.implementation.mode == "prompt"
        assert body.startswith("# Body")
        assert "Do the thing." in body

    def test_parse_name_must_match_dir(self):
        src = "---\nname: other\n.description: x\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n---\n\nbody\n"
        # malformed-ish but name mismatch should raise
        src = (
            "---\nname: other_skill\n"
            "description: x\n"
            "activation_mode: phase_mapped\n"
            "allowed_in_react_states: [plan]\n"
            "implementation:\n  mode: prompt\n"
            "---\n\nbody\n"
        )
        with pytest.raises(ValueError):
            parse_skill_md(src, dir_name="retrieval_reasoning")


class TestSkillRegistry:
    def test_load_caches_full_source_snapshot(self, tmp_path):
        _write_skill(
            tmp_path / "problem_framing",
            "name: problem_framing\ndescription: frame it.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
            body="# framing\nguidance",
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        assert reg.contains("problem_framing")
        d = reg.get("problem_framing")
        assert d.name == "problem_framing"
        load = reg.load_body("problem_framing")
        assert isinstance(load, SkillBodyLoad)
        assert load.text.startswith("# framing")
        assert load.definition_hash and len(load.definition_hash) <= 64

    def test_load_body_does_not_reread_disk(self, tmp_path):
        skill_dir = tmp_path / "problem_framing"
        _write_skill(
            skill_dir,
            "name: problem_framing\ndescription: frame it.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
            body="original",
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        first = reg.load_body("problem_framing")
        # Mutate the file on disk after load; v1 has no hot reload.
        (skill_dir / "SKILL.md").write_text("---\nname: problem_framing\ndescription: frame it.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n---\n\nMUTATED\n", encoding="utf-8")
        second = reg.load_body("problem_framing")
        assert second.text == first.text
        assert second.definition_hash == first.definition_hash

    def test_manifest_for_preserves_skill_refs_order(self, tmp_path):
        _write_skill(tmp_path / "a", "name: a\ndescription: A.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n")
        _write_skill(tmp_path / "b", "name: b\ndescription: B.\nactivation_mode: phase_mapped\nallowed_in_react_states: [do]\nimplementation:\n  mode: prompt\n")
        reg = SkillRegistry(skills_dir=tmp_path)
        defs = reg.manifest_for(["b", "a", "b"])
        assert [d.name for d in defs] == ["b", "a"]

    def test_load_rejects_invalid_activation_mode(self, tmp_path):
        _write_skill(
            tmp_path / "bad_mode",
            "name: bad_mode\ndescription: x.\nactivation_mode: phase_maped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
        )
        with pytest.raises(ValueError, match="invalid activation_mode"):
            SkillRegistry(skills_dir=tmp_path)

    def test_load_rejects_tool_mode_v1(self, tmp_path):
        _write_skill(tmp_path / "tool_skill", "name: tool_skill\ndescription: x.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: tool\n")
        with pytest.raises(ValueError):
            SkillRegistry(skills_dir=tmp_path)

    def test_l3_bundled_warning(self, tmp_path, caplog):
        skill_dir = tmp_path / "problem_framing"
        _write_skill(
            skill_dir,
            "name: problem_framing\ndescription: frame it.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
        )
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "extra.md").write_text("ref", encoding="utf-8")
        with caplog.at_level("WARNING"):
            SkillRegistry(skills_dir=tmp_path)
        assert any("references" in r.getMessage() or "assets" in r.getMessage() for r in caplog.records)

    def test_unknown_skill_id_returns_false(self, tmp_path):
        reg = SkillRegistry(skills_dir=tmp_path)
        assert not reg.contains("nope")
        with pytest.raises(KeyError):
            reg.get("nope")


class TestSkillRunner:
    def test_prompt_mode_returns_activation(self, tmp_path):
        _write_skill(
            tmp_path / "problem_framing",
            "name: problem_framing\ndescription: frame it.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
            body="guidance",
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        runner = SkillRunner(registry=reg)
        act = runner.activate("problem_framing")
        assert isinstance(act, SkillActivation)
        assert act.skill_id == "problem_framing"
        assert act.text == "guidance"
        assert act.definition_hash

    def test_load_body_hash_matches_activation_hash(self, tmp_path):
        _write_skill(
            tmp_path / "problem_framing",
            "name: problem_framing\ndescription: frame it.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
            body="guidance",
        )
        reg = SkillRegistry(skills_dir=tmp_path)
        runner = SkillRunner(registry=reg)
        assert runner.activate("problem_framing").definition_hash == reg.load_body("problem_framing").definition_hash
