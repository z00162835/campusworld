"""Framework integration: per-phase skill-context injection, trace, fingerprint."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from app.core.settings import AgentLlmServiceConfig
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext
from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
from app.game_engine.agent_runtime.skills import SkillInjection, SkillRegistry


def _write_skill(dir_path: Path, fm: str, body: str = "body") -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "SKILL.md").write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


def _seed_registry(tmp_path: Path) -> SkillRegistry:
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


class _FakeMem:
    def __init__(self) -> None:
        self.runs: List[Dict[str, Any]] = []
        self.raw: List[Dict[str, Any]] = []

    def start_run(self, run_id, correlation_id, phase, command_trace, status) -> None:
        self.runs.append({"op": "start", "phase": phase})

    def update_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append({"op": "update", "phase": phase})

    def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
        self.runs.append({"op": "finish", "phase": phase})

    def append_raw(self, kind, payload, session_id=None) -> None:
        self.raw.append({"kind": kind, "payload": payload})


class _RecordingLlm:
    """Records (system, user, skill_context_text, fingerprint) per LLM call."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def complete(self, *, system: str, user: str, call_spec=None, cancel_check=None) -> str:
        self.calls.append({
            "system": system,
            "user": user,
            "skill_context_text": getattr(call_spec, "skill_context_text", None) if call_spec else None,
            "fingerprint": (call_spec.extra or {}).get("prompt_fingerprint") if call_spec else None,
        })
        return "ok"

    def supports_tools(self) -> bool:
        return False


def _basic_cfg() -> AgentLlmServiceConfig:
    return AgentLlmServiceConfig(
        system_prompt="You are AICO.",
        phase_prompts={"plan": "Plan step.", "do": "Answer step.", "check": "Check step.", "act": "Act step."},
    )


def _build_fw(tmp_path, rec) -> LlmPDCAFramework:
    reg = _seed_registry(tmp_path)
    return LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
        skill_refs=["problem_framing", "retrieval_reasoning", "final_synthesis"],
        skill_injection=SkillInjection(registry=reg),
    )


@pytest.mark.unit
def test_skill_context_injected_per_phase(tmp_path):
    rec = _RecordingLlm()
    fw = _build_fw(tmp_path, rec)
    fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # Group calls by the skill_context present; plan should carry framing+retrieval,
    # do should carry retrieval, check/act should carry synthesis.
    plan_ctx = next((c for c in rec.calls if "framing guidance" in (c["skill_context_text"] or "")), None)
    do_ctx = next((c for c in rec.calls if "retrieval guidance" in (c["skill_context_text"] or "") and "framing" not in (c["skill_context_text"] or "")), None)
    check_ctx = next((c for c in rec.calls if "synthesis guidance" in (c["skill_context_text"] or "")), None)
    assert plan_ctx is not None, "plan phase must inject problem_framing + retrieval_reasoning"
    assert "## Available Agent Skills" in plan_ctx["skill_context_text"]
    assert do_ctx is not None, "do phase must inject retrieval_reasoning only"
    assert "framing guidance" not in (do_ctx["skill_context_text"] or "")
    assert check_ctx is not None, "check/act must inject final_synthesis"


@pytest.mark.unit
def test_platform_system_message_has_no_skill_text(tmp_path):
    rec = _RecordingLlm()
    fw = _build_fw(tmp_path, rec)
    fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    assert rec.calls, "expected LLM calls"
    for c in rec.calls:
        assert "## Available Agent Skills" not in (c["system"] or "")
        assert "guidance" not in (c["system"] or "")


@pytest.mark.unit
def test_skill_context_not_in_user_string(tmp_path):
    """skill-context rides on call_spec, not the plain user string (providers place it)."""
    rec = _RecordingLlm()
    fw = _build_fw(tmp_path, rec)
    fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    # The framework passes skill_context_text via spec, not by prepending to user.
    for c in rec.calls:
        assert "## Available Agent Skills" not in (c["user"] or "")


@pytest.mark.unit
def test_trace_records_skill_activated_with_definition_hash(tmp_path):
    rec = _RecordingLlm()
    reg = _seed_registry(tmp_path)

    class _TraceMem(_FakeMem):
        def __init__(self) -> None:
            super().__init__()
            self.last_trace: List[Dict[str, Any]] = []

        def finish_run(self, run_id, phase, command_trace, status, graph_ops_summary=None) -> None:
            self.last_trace = list(command_trace)
            super().finish_run(run_id, phase, command_trace, status, graph_ops_summary)

    mem = _TraceMem()
    fw = LlmPDCAFramework(
        memory=mem,
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
        skill_refs=["problem_framing", "retrieval_reasoning", "final_synthesis"],
        skill_injection=SkillInjection(registry=reg),
    )
    fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    activations = [e for e in mem.last_trace if e.get("step") == "skill_activated"]
    assert activations, "trace must record skill_activated entries"
    expected_hashes = {sid: reg.load_body(sid).definition_hash for sid in
                       ("problem_framing", "retrieval_reasoning", "final_synthesis")}
    seen = {(a["skill_id"], a["definition_hash"]) for a in activations}
    for sid, h in expected_hashes.items():
        assert (sid, h) in seen, f"missing skill_activated trace for {sid} with matching definition_hash"
    # every activation entry carries a phase + definition_hash
    for a in activations:
        assert a["phase"] in {"plan", "do", "check", "act"}
        assert a["definition_hash"]


@pytest.mark.unit
def test_real_seed_registry_loads_three_skills():
    """End-to-end seed asset validation: config/skills has the 3 AICO seed skills."""
    from app.game_engine.agent_runtime.skills.skill_registry import DEFAULT_SKILLS_DIR, SkillRegistry

    reg = SkillRegistry(skills_dir=DEFAULT_SKILLS_DIR)
    ids = set(reg.skill_ids)
    assert {"problem_framing", "retrieval_reasoning", "final_synthesis"} <= ids
    for sid in ("problem_framing", "retrieval_reasoning", "final_synthesis"):
        d = reg.get(sid)
        assert d.implementation.mode == "prompt"
        assert d.activation_mode == "phase_mapped"
        assert d.side_effect_level == "none"
        assert d.allowed_tool_groups == ("read",)
        assert reg.load_body(sid).definition_hash


@pytest.mark.unit
def test_fingerprint_per_phase_differs_with_skill_context(tmp_path):
    from app.game_engine.agent_runtime.prompt_fingerprint import compute_npc_prompt_fingerprint

    fp_plan = compute_npc_prompt_fingerprint(
        world_snapshot="", tool_manifest_text="", user_message="hi",
        skill_context_text="plan ctx", phase="plan")
    fp_do = compute_npc_prompt_fingerprint(
        world_snapshot="", tool_manifest_text="", user_message="hi",
        skill_context_text="do ctx", phase="do")
    fp_plan_b = compute_npc_prompt_fingerprint(
        world_snapshot="", tool_manifest_text="", user_message="hi",
        skill_context_text="plan ctx", phase="plan")
    assert fp_plan != fp_do
    assert fp_plan == fp_plan_b  # deterministic


@pytest.mark.unit
def test_no_skill_refs_means_no_skill_context(tmp_path):
    rec = _RecordingLlm()
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
        skill_refs=[],
    )
    fw.run(FrameworkRunContext(agent_node_id=1, payload={"message": "hi"}))
    for c in rec.calls:
        assert not (c["skill_context_text"] or "").strip()


class TestSkillModificationRegression:
    def test_rebuild_registry_changes_hash_and_fingerprint_input(self, tmp_path):
        skill_dir = tmp_path / "problem_framing"
        _write_skill(skill_dir,
                     "name: problem_framing\ndescription: Frame the problem.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
                     body="original guidance")
        reg1 = SkillRegistry(skills_dir=tmp_path)
        hash1 = reg1.load_body("problem_framing").definition_hash
        from app.game_engine.agent_runtime.prompt_fingerprint import compute_npc_prompt_fingerprint
        fp1 = compute_npc_prompt_fingerprint(world_snapshot="", tool_manifest_text="", user_message="hi",
                                             skill_context_text=reg1.load_body("problem_framing").text, phase="plan")
        # Edit the SKILL.md body; v1 has no hot reload so the OLD registry is unchanged.
        _write_skill(skill_dir,
                     "name: problem_framing\ndescription: Frame the problem.\nactivation_mode: phase_mapped\nallowed_in_react_states: [plan]\nimplementation:\n  mode: prompt\n",
                     body="MUTATED guidance")
        # Old registry snapshot unaffected (no hot reload):
        assert reg1.load_body("problem_framing").definition_hash == hash1
        # Rebuild registry -> new snapshot picks up the edit.
        reg2 = SkillRegistry(skills_dir=tmp_path)
        hash2 = reg2.load_body("problem_framing").definition_hash
        fp2 = compute_npc_prompt_fingerprint(world_snapshot="", tool_manifest_text="", user_message="hi",
                                             skill_context_text=reg2.load_body("problem_framing").text, phase="plan")
        assert hash2 != hash1
        assert fp2 != fp1


@pytest.mark.unit
def test_active_skill_context_dto_built_in_payload(tmp_path):
    """SPEC §4.3 step 1-2: _prepare_skill_context must store active_skill_context DTO.

    The DTO is later copied by _phase_react_loop into runtime_tool_ctx.metadata
    so execution_gate can read it. This test verifies the DTO construction side.
    """
    rec = _RecordingLlm()
    reg = _seed_registry(tmp_path)
    fw = LlmPDCAFramework(
        memory=_FakeMem(),
        llm_config=_basic_cfg(),
        instance_phase_llm={},
        instance_mode_models={},
        llm=rec,
        skill_refs=["problem_framing", "retrieval_reasoning"],
        skill_injection=SkillInjection(registry=reg),
    )
    ctx = FrameworkRunContext(agent_node_id=1, payload={"message": "hi"})
    fw._prepare_skill_context(ctx, "plan", [])
    asc = ctx.payload.get('active_skill_context')
    assert asc is not None
    assert 'active_skill_ids' in asc
    assert 'active_skill_allowed_tool_groups' in asc
    assert 'problem_framing' in asc['active_skill_ids']
    assert 'retrieval_reasoning' in asc['active_skill_ids']

    # When skill_refs is empty, the DTO should be None
    ctx2 = FrameworkRunContext(agent_node_id=1, payload={"message": "hi"})
    fw._skill_refs = ()
    fw._prepare_skill_context(ctx2, "plan", [])
    assert ctx2.payload.get('active_skill_context') is None
