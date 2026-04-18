from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from app.commands.agent_command_context import command_context_for_npc_agent
from app.commands.base import CommandContext
from app.game_engine.agent_runtime.frameworks.base import FrameworkRunContext, ThinkingFramework
from app.game_engine.agent_runtime.memory_port import MemoryPort, SqlAlchemyMemoryPort
from app.models.graph import Node

if TYPE_CHECKING:
    from app.core.settings import AgentLlmServiceConfig
    from app.game_engine.agent_runtime.llm_client import LlmClient
    from app.game_engine.agent_runtime.tooling import ToolExecutor
else:
    ToolExecutor = Any


class AgentWorker:
    """Binds a ThinkingFramework with ports (memory + optional tools)."""

    def __init__(
        self,
        *,
        memory: MemoryPort,
        framework: ThinkingFramework,
        tools: Optional[ToolExecutor] = None,
        tool_command_context: Optional[CommandContext] = None,
    ):
        self.memory = memory
        self.framework = framework
        self.tools = tools
        self.tool_command_context = tool_command_context

    def tick(
        self,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        *,
        system_prompt: Optional[str] = None,
        phase_prompts: Optional[Dict[str, str]] = None,
        memory_context: Optional[str] = None,
        phase_llm_overrides: Optional[Dict[str, Any]] = None,
    ):
        ctx = FrameworkRunContext(
            agent_node_id=getattr(self.memory, "_agent_node_id", 0),
            correlation_id=correlation_id,
            payload=payload,
            system_prompt=system_prompt,
            phase_prompts=dict(phase_prompts or {}),
            memory_context=memory_context,
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
        fb = invoker_context or CommandContext(
            user_id=str(agent_node_id),
            username="agent_worker",
            session_id=f"agent_worker_{agent_node_id}",
            permissions=[],
            roles=[],
            db_session=session,
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
    ) -> "LlmPdcaAssistantWorker":
        from app.game_engine.agent_runtime.agent_llm_config import resolve_agent_llm_config_for_npc_tick
        from app.game_engine.agent_runtime.agent_node_phase_llm import parse_phase_llm_from_attributes
        from app.game_engine.agent_runtime.frameworks.llm_pdca import LlmPDCAFramework
        from app.game_engine.agent_runtime.llm_client import build_llm_client_from_service_config
        from app.game_engine.agent_runtime.resolved_tool_surface import (
            PreauthorizedToolExecutor,
            build_resolved_tool_surface,
        )
        from app.game_engine.agent_runtime.tool_gather import tool_gather_budgets_from_agent_extra

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
        llm_impl = llm_client or build_llm_client_from_service_config(cfg)
        fb = invoker_context or CommandContext(
            user_id=str(agent_node_id),
            username="agent_worker",
            session_id=f"agent_worker_{agent_node_id}",
            permissions=[],
            roles=[],
            db_session=session,
        )
        tool_ctx = command_context_for_npc_agent(session, agent, fb)
        mem = SqlAlchemyMemoryPort(session, agent_node_id)
        raw_allow = attrs.get("tool_allowlist") or []
        allowlist = [str(x) for x in raw_allow] if isinstance(raw_allow, list) else []
        surface = build_resolved_tool_surface(node_tool_allowlist=allowlist, tool_command_context=tool_ctx)
        pre_ex = PreauthorizedToolExecutor(surface)
        budgets = tool_gather_budgets_from_agent_extra(cfg.extra)
        instance_phase_llm, instance_mode_models = parse_phase_llm_from_attributes(attrs)
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
        )
        return cls(
            memory=mem,
            framework=fw,
            tools=pre_ex,
            tool_command_context=tool_ctx,
        )
