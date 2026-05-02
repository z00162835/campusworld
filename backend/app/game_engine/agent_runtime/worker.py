from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.commands.agent_command_context import command_context_for_npc_agent
from app.commands.base import CommandContext
from app.core.config_manager import get_config
from app.core.log import LoggerNames, get_logger
from app.core.log.aico_observability import (
    get_aico_max_phase_output_chars,
    is_aico_observability_enabled,
)
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext, ThinkingFramework
from app.game_engine.agent_runtime.memory_port import MemoryPort, SqlAlchemyMemoryPort
from app.models.graph import Node

if TYPE_CHECKING:
    from app.core.settings import AgentLlmServiceConfig
    from app.game_engine.agent_runtime.agent_tick_context import NpcAgentTickInputs
    from app.game_engine.agent_runtime.llm_client import LlmClient
    from app.game_engine.agent_runtime.tool_calling import ToolSchema
    from app.game_engine.agent_runtime.tooling import ToolExecutor
else:
    ToolExecutor = Any
    ToolSchema = Any


class AgentWorker:
    """Binds a ThinkingFramework with ports (memory + optional tools)."""

    def __init__(
        self,
        *,
        memory: MemoryPort,
        framework: ThinkingFramework,
        tools: Optional[ToolExecutor] = None,
        tool_command_context: Optional[CommandContext] = None,
        tool_manifest_text: str = "",
        tool_schemas: Optional[List[ToolSchema]] = None,
    ):
        self.memory = memory
        self.framework = framework
        self.tools = tools
        self.tool_command_context = tool_command_context
        self.tool_manifest_text = tool_manifest_text or ""
        self.tool_schemas = list(tool_schemas or [])

    def tick(
        self,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        *,
        system_prompt: Optional[str] = None,
        phase_prompts: Optional[Dict[str, str]] = None,
        memory_context: Optional[str] = None,
        recent_conversation: Optional[str] = None,
        retrieved_memory: Optional[str] = None,
        memory_context_do: Optional[str] = None,
        phase_llm_overrides: Optional[Dict[str, Any]] = None,
    ):
        # Tier-ed context: enrich payload with the precomputed tool manifest
        # so the framework's Plan phase can surface "Tools available" without
        # the caller having to repeat it on every tick.
        enriched = dict(payload or {})
        if self.tool_manifest_text and not enriched.get("tool_manifest_text"):
            enriched["tool_manifest_text"] = self.tool_manifest_text
        ctx = FrameworkRunContext(
            agent_node_id=getattr(self.memory, "_agent_node_id", 0),
            correlation_id=correlation_id,
            payload=enriched,
            system_prompt=system_prompt,
            phase_prompts=dict(phase_prompts or {}),
            memory_context=memory_context,
            recent_conversation=recent_conversation,
            retrieved_memory=retrieved_memory,
            memory_context_do=memory_context_do,
            phase_llm_overrides=dict(phase_llm_overrides or {}),
        )
        return self.framework.run(ctx)


class SysSampleWorker(AgentWorker):
    """Default sys_worker-style worker using PDCA + DB memory."""

    @classmethod
    def create(
        cls,
        session,
        agent_node_id: int,
        invoker_context: Optional[CommandContext] = None,
    ) -> "SysSampleWorker":
        from app.game_engine.agent_runtime.frameworks.pdca import PDCAFramework
        from app.game_engine.agent_runtime.tooling import RegistryToolExecutor

        agent = session.query(Node).filter(Node.id == agent_node_id).first()
        if agent is None:
            raise ValueError(f"agent node {agent_node_id} not found")
        attrs = agent.attributes or {}
        fb = invoker_context or CommandContext(
            user_id=str(agent_node_id),
            username="agent_worker",
            session_id=f"agent_worker_{agent_node_id}",
            permissions=[],
            roles=[],
            db_session=session,
        )
        fb_meta = dict(fb.metadata or {})
        fb_meta["agent_interaction_profile"] = str(attrs.get("interaction_profile") or "mutate")
        if isinstance(attrs.get("invocation_policy"), dict):
            fb_meta["agent_invocation_policy"] = dict(attrs.get("invocation_policy") or {})
        fb = CommandContext(
            user_id=fb.user_id,
            username=fb.username,
            session_id=fb.session_id,
            permissions=list(fb.permissions or []),
            roles=list(fb.roles or []),
            db_session=fb.db_session,
            caller=fb.caller,
            game_state=fb.game_state,
            metadata=fb_meta,
        )
        tool_ctx = command_context_for_npc_agent(session, agent, fb)
        mem = SqlAlchemyMemoryPort(session, agent_node_id)
        tools = RegistryToolExecutor()
        fw = PDCAFramework(memory=mem, tools=tools)
        return cls(
            memory=mem,
            framework=fw,
            tools=tools,
            tool_command_context=tool_ctx,
        )


class LlmPdcaAssistantWorker(AgentWorker):
    """NLP + LLM + PDCA for assistants with ``decision_mode: llm``."""

    @classmethod
    def create(
        cls,
        session,
        agent_node_id: int,
        invoker_context: Optional[CommandContext] = None,
        *,
        llm_client: Optional[LlmClient] = None,
        agent_llm_config: Optional["AgentLlmServiceConfig"] = None,
        tick_inputs: Optional["NpcAgentTickInputs"] = None,
    ) -> "LlmPdcaAssistantWorker":
        from app.commands.registry import command_registry as _command_registry
        from app.game_engine.agent_runtime.agent_llm_config import resolve_agent_llm_config_for_npc_tick
        from app.game_engine.agent_runtime.agent_node_phase_llm import parse_phase_llm_from_attributes
        from app.game_engine.agent_runtime.aico_world_context import build_llm_tool_manifest
        from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
        from app.game_engine.agent_runtime.llm_client import build_llm_client_from_service_config
        from app.game_engine.agent_runtime.resolved_tool_surface import (
            PreauthorizedToolExecutor,
            build_resolved_tool_surface,
        )
        from app.game_engine.agent_runtime.tool_gather import tool_gather_budgets_from_agent_extra

        if tick_inputs is not None:
            agent = tick_inputs.agent
            if int(agent.id) != int(agent_node_id):
                raise ValueError(
                    f"tick_inputs.agent.id {agent.id} does not match agent_node_id {agent_node_id}"
                )
            attrs = dict(tick_inputs.attrs)
            service_id = tick_inputs.service_id
            model_ref_s = tick_inputs.model_ref_s
            if agent_llm_config is not None:
                cfg = agent_llm_config
            else:
                cfg = tick_inputs.cfg
        else:
            agent = session.query(Node).filter(Node.id == agent_node_id).first()
            if agent is None:
                raise ValueError(f"agent node {agent_node_id} not found")
            attrs = agent.attributes or {}
            service_id = str(attrs.get("service_id") or "aico")
            model_ref = attrs.get("model_config_ref")
            model_ref_s = str(model_ref) if model_ref else None
            if agent_llm_config is not None:
                cfg = agent_llm_config
            else:
                cfg = resolve_agent_llm_config_for_npc_tick(
                    service_id,
                    model_config_ref=model_ref_s,
                    node_attributes=attrs,
                )
        fb = invoker_context or CommandContext(
            user_id=str(agent_node_id),
            username="agent_worker",
            session_id=f"agent_worker_{agent_node_id}",
            permissions=[],
            roles=[],
            db_session=session,
        )
        from app.game_engine.agent_runtime.agent_llm_extra import parse_bool_extra

        extra = dict(cfg.extra or {})
        tier1_on = parse_bool_extra(extra, "prepend_primer_tier1", default=True)
        caller_location_name: Optional[str] = None
        if tier1_on:
            if tick_inputs is not None:
                caller_location_name = tick_inputs.caller.caller_location_display_name
            else:
                try:
                    from app.game_engine.agent_runtime.command_caller_graph import (
                        resolve_caller_location_id,
                        resolve_caller_node_id,
                        resolve_room_display_name,
                    )

                    cid = resolve_caller_node_id(session, fb)
                    lid = resolve_caller_location_id(session, cid)
                    caller_location_name = resolve_room_display_name(session, lid)
                except Exception:
                    caller_location_name = None
            from app.game_engine.agent_runtime.system_primer_context import (
                merge_system_prompt_with_primer_tier1,
            )

            cfg = cfg.model_copy(
                update={
                    "system_prompt": merge_system_prompt_with_primer_tier1(
                        cfg.system_prompt or "",
                        for_agent=service_id,
                        caller_location_name=caller_location_name,
                        enabled=True,
                    )
                }
            )
        llm_impl = llm_client or build_llm_client_from_service_config(cfg)
        tool_ctx = command_context_for_npc_agent(session, agent, fb)
        mem = SqlAlchemyMemoryPort(session, agent_node_id)
        raw_allow = attrs.get("tool_allowlist") or []
        allowlist = [str(x) for x in raw_allow] if isinstance(raw_allow, list) else []
        surface = build_resolved_tool_surface(node_tool_allowlist=allowlist, tool_command_context=tool_ctx)
        pre_ex = PreauthorizedToolExecutor(surface)
        budgets = tool_gather_budgets_from_agent_extra(cfg.extra)
        instance_phase_llm, instance_mode_models = parse_phase_llm_from_attributes(attrs)
        # Build tool manifest once at worker-create time. The allowed surface
        # is stable across ticks for a given agent node; rebuild happens when
        # the worker is recreated (e.g. after ``tool_allowlist`` changes).
        manifest_locale = None
        if invoker_context is not None and isinstance(getattr(invoker_context, "metadata", None), dict):
            v = invoker_context.metadata.get("locale")
            if isinstance(v, str) and v.strip():
                manifest_locale = v.strip()
        try:
            manifest_text, tool_schemas = build_llm_tool_manifest(
                surface, _command_registry, session=session, locale=manifest_locale
            )
        except Exception:
            # Defensive: never fail worker creation because of manifest issues.
            manifest_text, tool_schemas = "", []
        tick_hooks = None
        cm = get_config()
        if service_id.strip().lower() == "aico" and is_aico_observability_enabled(cm):
            from app.game_engine.agent_runtime.aico_observability_hooks import AicoObservabilityTickHooks

            tick_hooks = AicoObservabilityTickHooks(
                get_logger(LoggerNames.AICO_AGENT),
                max_phase_output_chars=get_aico_max_phase_output_chars(cm),
            )
        from app.game_engine.agent_runtime.intent_classifier_runtime import (
            build_intent_classifier_for_tick,
            resolve_intent_classifier_runtime,
        )

        ic_runtime = resolve_intent_classifier_runtime(dict(cfg.extra or {}), attrs)
        intent_classifier = build_intent_classifier_for_tick(ic_runtime)
        fw = LlmPDCAFramework(
            memory=mem,
            llm_config=cfg,
            instance_phase_llm=instance_phase_llm,
            instance_mode_models=instance_mode_models,
            llm=llm_impl,
            tools=pre_ex,
            tool_command_context=tool_ctx,
            preauthorized_tool_executor=pre_ex,
            tool_gather_budgets=budgets,
            tick_hooks=tick_hooks,
            tool_schemas=tool_schemas,
            intent_classifier=intent_classifier,
        )
        return cls(
            memory=mem,
            framework=fw,
            tools=pre_ex,
            tool_command_context=tool_ctx,
            tool_manifest_text=manifest_text,
            tool_schemas=tool_schemas,
        )
