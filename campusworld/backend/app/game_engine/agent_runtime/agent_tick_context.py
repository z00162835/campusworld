"""Per-tick snapshots for npc_agent NLP to avoid duplicate graph reads (F10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.commands.base import CommandContext
from app.core.settings import AgentLlmServiceConfig
from app.models.graph import Node


@dataclass(frozen=True)
class CallerGraphSnapshot:
    """Caller location facts resolved once per tick at the NLP entry."""

    caller_node_id: Optional[int]
    caller_location_node_id: Optional[int]
    caller_location_display_name: Optional[str]


@dataclass(frozen=True)
class NpcAgentTickInputs:
    """Agent row + LLM config + caller snapshot for one ``run_npc_agent_nlp_tick``."""

    agent: Node
    attrs: Dict[str, Any]
    service_id: str
    model_ref_s: Optional[str]
    cfg: AgentLlmServiceConfig
    caller: CallerGraphSnapshot


def build_caller_graph_snapshot(session: Any, invoker: CommandContext) -> CallerGraphSnapshot:
    """Resolve caller room once; swallow errors into empty snapshot."""
    try:
        from app.game_engine.agent_runtime.command_caller_graph import (
            resolve_caller_location_id,
            resolve_caller_node_id,
            resolve_room_display_name,
        )

        cid = resolve_caller_node_id(session, invoker)
        lid = resolve_caller_location_id(session, cid)
        name = resolve_room_display_name(session, lid)
        return CallerGraphSnapshot(
            caller_node_id=cid,
            caller_location_node_id=lid,
            caller_location_display_name=name,
        )
    except Exception:
        return CallerGraphSnapshot(None, None, None)
