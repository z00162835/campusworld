"""SkillInjection per-phase manifest/body render tests + activation golden set."""
from __future__ import annotations

from pathlib import Path

from app.game_engine.agent_runtime.skills.skill_injection import SkillInjection
from app.game_engine.agent_runtime.skills.skill_registry import SkillRegistry


def _write_skill(dir_path: Path, fm: str, body: str = "body") -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "SKILL.md").write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


def _build_registry(tmp_path: Path) -> SkillRegistry:
    _write_skill(tmp_path / "problem_framing",
                 "name: problem_framing\ndescription: Frame the problem.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
                 body="# framing guidance")
    _write_skill(tmp_path / "retrieval_reasoning",
                 "name: retrieval_reasoning\ndescription: Retrieve then reason.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan, do]\nimplementation:\n  mode: prompt\n",
                 body="# retrieval guidance")
    _write_skill(tmp_path / "final_synthesis",
                 "name: final_synthesis\ndescription: Synthesize the answer.\nactivation_mode: phase_mapped\nallowed_in_react_states: [check, act]\nimplementation:\n  mode: prompt\n",
                 body="# synthesis guidance")
    return SkillRegistry(skills_dir=tmp_path)


class TestPerPhaseEligibleAndManifest:
    def test_l1_manifest_eligible_only(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "retrieval_reasoning", "final_synthesis"]
        block = inj.render_manifest(refs, phase="plan")
        assert "problem_framing" in block
        assert "retrieval_reasoning" in block
        assert "final_synthesis" not in block

    def test_manifest_splits_active_and_inactive(self, tmp_path):
        _write_skill(tmp_path / "problem_framing",
                     "name: problem_framing\ndescription: Frame the problem.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
                     body="# framing guidance")
        _write_skill(tmp_path / "model_pick",
                     "name: model_pick\ndescription: model picks.\nactivation_mode: model_selected\nimplementation:\n  mode: prompt\n",
                     body="should not inject in v1")
        reg = SkillRegistry(skills_dir=tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "model_pick"]
        block = inj.render_manifest(refs, phase="plan")
        assert "### Active skills" in block
        assert "### Available but inactive skills" in block
        assert "problem_framing" in block.split("### Active skills")[1].split("### Available but inactive skills")[0]
        assert "model_pick" in block.split("### Available but inactive skills")[1]

    def test_empty_section_omitted(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing"]
        block = inj.render_manifest(refs, phase="plan")
        assert "### Available but inactive skills" not in block

    def test_no_eligible_returns_empty(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        assert inj.render_manifest(["final_synthesis"], phase="plan") == ""

    def test_manifest_in_skill_refs_order(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["retrieval_reasoning", "problem_framing"]
        block = inj.render_manifest(refs, phase="plan")
        assert block.index("retrieval_reasoning") < block.index("problem_framing")


class TestL2BodyInjection:
    def test_phase_mapped_body_injected_when_matching(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        text = inj.inject_bodies(["problem_framing", "retrieval_reasoning", "final_synthesis"], phase="plan")
        assert "# framing guidance" in text
        assert "# retrieval guidance" in text
        assert "# synthesis guidance" not in text

    def test_model_selected_body_not_injected(self, tmp_path):
        _write_skill(tmp_path / "model_pick",
                     "name: model_pick\ndescription: model picks.\nactivation_mode: model_selected\nimplementation:\n  mode: prompt\n",
                     body="SECRET BODY")
        reg = SkillRegistry(skills_dir=tmp_path)
        inj = SkillInjection(registry=reg)
        text = inj.inject_bodies(["model_pick"], phase="plan")
        assert "SECRET BODY" not in text

    def test_no_matching_body_returns_empty(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        assert inj.inject_bodies(["final_synthesis"], phase="plan") == ""


class TestInjectSkillContext:
    def test_full_skill_context_manifest_then_bodies(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "retrieval_reasoning", "final_synthesis"]
        result = inj.inject(refs, phase="plan")
        assert result.text.startswith("## Available Agent Skills")
        assert "# framing guidance" in result.text
        assert "# retrieval guidance" in result.text
        assert "# synthesis guidance" not in result.text
        # only phase-mapped+matching skills produce activations (L2 injected)
        assert {a.skill_id for a in result.activations} == {"problem_framing", "retrieval_reasoning"}
        for a in result.activations:
            assert a.definition_hash

    def test_empty_refs_produces_empty_context(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        result = inj.inject([], phase="plan")
        assert result.text == ""
        assert result.activations == ()
        assert result.blocked == ()


class TestActivationGoldenSet:
    def test_phase_to_active_skill_ids(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "retrieval_reasoning", "final_synthesis"]
        golden = {
            "plan": ["problem_framing", "retrieval_reasoning"],
            "do": ["retrieval_reasoning"],
            "check": ["final_synthesis"],
            "act": ["final_synthesis"],
        }
        for phase, expected in golden.items():
            result = inj.inject(refs, phase=phase)
            assert [a.skill_id for a in result.activations] == expected, f"phase={phase}"

    def test_non_mapped_phase_not_active(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "retrieval_reasoning", "final_synthesis"]
        # problem_framing only in plan; should not activate in do
        result = inj.inject(refs, phase="do")
        ids = {a.skill_id for a in result.activations}
        assert "problem_framing" not in ids


class TestBlockedSection:
    def test_before_activate_hook_can_block_skill(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "retrieval_reasoning", "final_synthesis"]

        def _deny_problem_framing(defn, phase):
            if defn.name == "problem_framing":
                return "policy_denied_problem_framing"
            return None

        result = inj.inject(refs, phase="plan", before_activate=_deny_problem_framing)
        assert {a.skill_id for a in result.activations} == {"retrieval_reasoning"}
        assert {b.name for b in result.blocked} == {"problem_framing"}
        assert result.blocked_reasons == ("policy_denied_problem_framing",)
        assert "### Blocked by policy" in result.text
        assert "problem_framing" in result.text.split("### Blocked by policy")[1]
        assert "policy_denied_problem_framing" in result.text

    def test_blocked_skill_not_in_active_or_inactive(self, tmp_path):
        reg = _build_registry(tmp_path)
        inj = SkillInjection(registry=reg)
        refs = ["problem_framing", "retrieval_reasoning"]

        result = inj.inject(
            refs,
            phase="plan",
            before_activate=lambda defn, phase: "denied" if defn.name == "problem_framing" else None,
        )
        active_part = result.text.split("### Active skills")[1].split("### Blocked by policy")[0]
        assert "problem_framing" not in active_part
        assert "retrieval_reasoning" in active_part
        assert "problem_framing" in result.text.split("### Blocked by policy")[1]
