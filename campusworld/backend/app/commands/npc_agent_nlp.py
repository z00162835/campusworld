"""Shared NLP tick for npc_agent: used by `aico` and line-prefix `@<handle>` dispatch."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from app.commands.base import CommandContext, CommandResult
from app.core.log import get_logger
from app.models.graph import Node

_NPC_AGENT_NLP_LOG = get_logger("app.commands.npc_agent_nlp")

# User-facing text only; do not name commands or point users to help/CLI recovery.
NPC_AGENT_LLM_FAILURE_USER_MSG = "我这边暂时无法处理，请再描述一下你的目标。"


def maybe_ltm_memory_context(session, agent_node_id: int, user_message: str, cfg_extra: Dict[str, Any]) -> Optional[str]:
    """
    Optional LTM injection. Disabled unless extra.enable_ltm is true in agents.llm YAML extra.
    """
    if not cfg_extra.get("enable_ltm"):
        return None
    if not user_message.strip():
        return None
    if os.environ.get("AICO_SKIP_LTM_PLACEHOLDER"):
        return None
    from app.services.ltm_semantic_retrieval import build_ltm_memory_context_for_tick

    return build_ltm_memory_context_for_tick(
        session,
        agent_node_id,
        user_message=user_message,
    )


def run_npc_agent_nlp_tick(
    session,
    node: Node,
    context: CommandContext,
    message: str,
    *,
    memory_context: Optional[str] = None,
    phase_llm_overrides: Optional[Dict[str, Any]] = None,
):
    """Run one LlmPdcaAssistantWorker tick; caller commits session."""
    from app.game_engine.agent_runtime.agent_llm_config import resolve_agent_llm_config_for_npc_tick
    from app.game_engine.agent_runtime.agent_tick_context import (
        NpcAgentTickInputs,
        build_caller_graph_snapshot,
    )
    from app.game_engine.agent_runtime.aico_world_context import build_world_snapshot_from_session
    from app.game_engine.agent_runtime.frameworks.base import FrameworkRunResult
    from app.game_engine.agent_runtime.llm_client import build_llm_client_from_service_config, http_llm_available
    from app.game_engine.agent_runtime.worker import LlmPdcaAssistantWorker

    attrs = node.attributes or {}
    service_id = str(attrs.get("service_id") or "aico")
    model_ref = attrs.get("model_config_ref")
    model_ref_s = str(model_ref) if model_ref else None
    cfg = resolve_agent_llm_config_for_npc_tick(
        service_id,
        model_config_ref=model_ref_s,
        node_attributes=attrs,
    )
    if not http_llm_available(cfg):
        return FrameworkRunResult(
            ok=True,
            message=str(message).strip(),
            final_phase="passthrough",
        )

    mem_ctx = memory_context
    if mem_ctx is None:
        mem_ctx = maybe_ltm_memory_context(session, node.id, message, dict(cfg.extra or {}))

    llm = build_llm_client_from_service_config(cfg)
    caller_snap = build_caller_graph_snapshot(session, context)
    tick_inputs = NpcAgentTickInputs(
        agent=node,
        attrs=dict(attrs),
        service_id=service_id,
        model_ref_s=model_ref_s,
        cfg=cfg,
        caller=caller_snap,
    )
    w = LlmPdcaAssistantWorker.create(
        session,
        node.id,
        invoker_context=context,
        llm_client=llm,
        agent_llm_config=cfg,
        tick_inputs=tick_inputs,
    )

    # Build a per-tick world snapshot. Kept best-effort — any failure here
    # must not abort the tick; the Plan phase simply sees no snapshot.
    world_snapshot_text = ""
    try:
        caller_username = getattr(context, "username", None)
        caller_roles = getattr(context, "roles", ()) or ()
        caller_location_node_id = caller_snap.caller_location_node_id
        world_snapshot_text = build_world_snapshot_from_session(
            session,
            caller_username=caller_username,
            caller_roles=list(caller_roles),
            caller_location_node_id=caller_location_node_id,
            agent_node_attrs=attrs,
            tool_surface_count=len(getattr(w, "tool_schemas", []) or []),
            recent_commands=(),
        )
    except Exception:
        world_snapshot_text = ""

    from app.core.config_manager import get_config
    from app.core.log.aico_observability import (
        clear_aico_full_chain_tick,
        is_aico_dev_chain_verbose,
        set_aico_full_chain_tick,
    )

    cm = get_config()
    allow_full = service_id.strip().lower() == "aico" and is_aico_dev_chain_verbose(cm)
    set_aico_full_chain_tick(allow_full)
    try:
        payload: Dict[str, Any] = {"message": message}
        if world_snapshot_text:
            payload["world_snapshot"] = world_snapshot_text
        try:
            return w.tick(
                payload,
                correlation_id=context.session_id,
                memory_context=mem_ctx,
                phase_llm_overrides=phase_llm_overrides,
            )
        except Exception:
            _NPC_AGENT_NLP_LOG.exception(
                "npc_agent_nlp tick failed: service_id=%s session=%s",
                service_id,
                context.session_id,
            )
            return FrameworkRunResult(
                ok=False,
                message=NPC_AGENT_LLM_FAILURE_USER_MSG,
                final_phase="error",
            )
    finally:
        clear_aico_full_chain_tick()


def assistant_nlp_command_result(
    handle: str,
    res,
    *,
    service_id: Optional[str] = None,
) -> CommandResult:
    """Assistant NLP tick → CommandResult: human text in message; machine fields in data."""
    msg = str(res.message or "").strip()
    data: Dict[str, Any] = {
        "ok": res.ok,
        "phase": res.final_phase,
        "handle": handle,
    }
    if service_id:
        data["service_id"] = service_id
    return CommandResult.success_result(msg, data=data)


