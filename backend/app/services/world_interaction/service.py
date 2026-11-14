"""World interaction aggregation for HTTP/UI adapters.

The service derives UI state from the graph and command layer. It does not own
world position state; account ``location_id`` remains the authoritative current
place.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import String, cast, or_, text
from sqlalchemy.orm import Session

from app.commands.base import CommandContext, CommandResult
from app.commands.command_tool_semantics import resolve_command_tool_semantics
from app.commands.room_connects_to_query import connects_to_exits_from_room
from app.commands.init_commands import ensure_commands_initialized
from app.commands.registry import command_registry
from app.commands.shell_words import split_command_line
from app.core.log import get_logger, LoggerNames
from app.game_engine.manager import game_engine_manager
from app.models.graph import Node, Relationship
from app.models.root_manager import root_manager
from app.services.task.permissions import Principal
from app.services.task.task_visibility_sql import visible_task_ids
from app.services.task.quest_interaction_projection import build_quest_interaction_projection
from app.services.task.quest_semantic_service import show_quest
from app.services.task.errors import OptimisticLockError, PermissionDenied, PreconditionFailed, ReferenceNotFound
from app.services.task.quest_semantic_service import can_read_semantic_node
from app.services.task.quest_interaction_service import (
    focus_objective,
    new_correlation_id,
    record_projection_change,
    read_projection_cursor,
    set_clue_pin,
    set_collaborator,
    set_situation_attention,
    track_quest,
    untrack_quest,
)
from app.services.task.user_task_queue import (
    QueueTaskRow,
    last_handled_task,
    list_for_principal,
    principal_from_actor,
)

from app.core.config_manager import get_setting
from app.repositories.world_conversation_archive import WorldConversationArchiveRepository
from app.schemas.world_history import ConversationArchiveRequest
from app.services.space_summary_service import build_space_summary_data

from .aico_stream_query import AicoStreamQueryService
from .command_query import CommandQueryService
from .command_runner import CommandRunner
from .semantic_map_service import (
    apply_highlight_ids_to_focus_map,
    build_focus_map,
    build_map_query_patch,
)
from .types import CAMPUS_HUB_WORLD_ID, DISPLAY_POLICY, WorldActor


class WorldInteractionService:
    """Build CampusWorld interaction state and dispatch generated actions."""

    def __init__(self) -> None:
        self.logger = get_logger(LoggerNames.GAME)
        max_archives = int(get_setting("world_interaction.max_archives_per_user", 100) or 100)
        self._archive_repo = WorldConversationArchiveRepository(max_archives_per_user=max_archives)
        self._command_runner = CommandRunner()
        self._command_query = CommandQueryService(
            run_command=self.execute_command,
            search=self.search,
            build_patch=self._state_patch_after_result,
        )
        self._aico_stream_query = AicoStreamQueryService(
            command_runner=self._command_runner,
            build_patch=self._state_patch_after_result,
            logger=self.logger,
        )

    def get_current_state(self, session: Session, actor: WorldActor) -> Dict[str, Any]:
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        location = self._resolve_current_location(session, user)
        current_world_id = self._world_id_for_node(location)
        available_worlds = self.list_available_worlds(session, current_world_id=current_world_id)
        state = self._build_interaction_state(session, actor, user, location, current_world_id, available_worlds)
        return {
            "session": state["session"],
            "interaction_state": state,
            "display_policy": DISPLAY_POLICY,
            "available_worlds": available_worlds,
        }

    def refresh_interaction_state(self, session: Session, actor: WorldActor) -> Dict[str, Any]:
        return self.get_current_state(session, actor)["interaction_state"]

    def list_available_worlds(self, session: Session, *, current_world_id: Optional[str] = None) -> List[Dict[str, Any]]:
        world_ids: List[str] = []
        try:
            for world_id in game_engine_manager.list_games():
                self._append_unique(world_ids, world_id)
        except Exception as exc:
            self.logger.warning("Failed to list discovered worlds: %s", exc)

        world_nodes = session.query(Node).filter(Node.type_code == "world", Node.is_active == True).limit(200).all()
        for node in world_nodes:
            self._append_unique(world_ids, str((node.attributes or {}).get("world_id") or node.name).lower())

        entrances = session.query(Node).filter(Node.type_code == "world_entrance", Node.is_active == True).limit(200).all()
        entrance_by_world: Dict[str, Node] = {}
        for node in entrances:
            attrs = dict(node.attributes or {})
            wid = str(attrs.get("portal_world_id") or attrs.get("world_id") or node.name or "").strip().lower()
            if not wid:
                continue
            self._append_unique(world_ids, wid)
            entrance_by_world[wid] = node

        world_labels = self._world_display_names(session)

        worlds: List[Dict[str, Any]] = []
        engine = game_engine_manager.get_engine()
        for wid in world_ids:
            status = "available"
            if engine and engine.loader:
                runtime = engine.loader.get_runtime_state(wid)
                status = str(runtime.get("status") or status)
            entrance = entrance_by_world.get(wid)
            worlds.append(
                {
                    "world_id": wid,
                    "name": self._world_label(wid, entrance, world_labels),
                    "status": status,
                    "is_current": wid == current_world_id,
                    "is_recommended": wid == "hicampus",
                    "entry_hint": f"enter {wid}",
                }
            )
        root = root_manager.get_root_node(session)
        hub_name = self._display_name(root) if root else "Singularity Room"
        worlds.append(
            {
                "world_id": CAMPUS_HUB_WORLD_ID,
                "name": hub_name,
                "status": "available",
                "is_current": current_world_id is None,
                "is_recommended": False,
                "entry_hint": "leave" if current_world_id else "look",
            }
        )
        return sorted(worlds, key=lambda item: (not item["is_current"], not item["is_recommended"], item["world_id"]))

    def enter_world(self, session: Session, actor: WorldActor, world_id: str) -> Dict[str, Any]:
        if str(world_id).strip().lower() == CAMPUS_HUB_WORLD_ID:
            return self.leave_world(session, actor)
        result = self.execute_command(session, actor, f"enter {world_id}")
        return self._state_patch_after_result(session, actor, result)

    def leave_world(self, session: Session, actor: WorldActor) -> Dict[str, Any]:
        result = self.execute_command(session, actor, "leave")
        return self._state_patch_after_result(session, actor, result)

    def execute_decision_action(self, session: Session, actor: WorldActor, decision_event_id: str, option_id: str) -> Dict[str, Any]:
        state = self.refresh_interaction_state(session, actor)
        events = list(state.get("decision_center", {}).get("decisionEvents") or [])
        active_task = state.get("decision_center", {}).get("activeTask")
        if active_task:
            task_action = active_task.get("nextBestAction")
            if task_action:
                events.append({"id": active_task.get("id"), "options": [task_action] + list(active_task.get("alternativeActions") or [])})
        for event in events:
            if event.get("id") != decision_event_id:
                continue
            for option in event.get("options") or []:
                if option.get("id") == option_id:
                    command = option.get("command")
                    if not command:
                        return self._state_patch_after_result(session, actor, CommandResult.success_result(option.get("label") or "Action completed"))
                    governed = self._execute_governed_task_choice(session, actor, option)
                    if governed is not None:
                        return governed
                    result = self.execute_command(session, actor, command)
                    return self._state_patch_after_result(session, actor, result, resolved_event_id=decision_event_id)
        return {"success": False, "result": {"summary": "Action is no longer available.", "status": "failed"}, "state_patch": {}}

    def _prepare_governed_task_choice(self, session, principal, option):
        from app.services.task.task_state_machine import load_node_ref
        from app.services.task.quest_decision import QuestDecisionContext
        from app.services.task.quest_governance import GraphQuestGovernance

        tokens = split_command_line(str(option.get('command') or ''))
        if len(tokens) < 3 or tokens[0] != 'task' or tokens[1] not in {'claim', 'start', 'complete'} or not tokens[2].isdigit():
            return None
        task = load_node_ref(session, node_id=int(tokens[2]), expected_type_code='task')
        quest_id = task['attributes'].get('quest_id')
        if quest_id is None or not can_read_semantic_node(session, node_id=int(quest_id), actor=principal):
            return None
        attrs = load_node_ref(session, node_id=int(quest_id), expected_type_code='quest')['attributes']
        if attrs.get('governance_mode') != 'enforced':
            return None
        refs = tuple(attrs.get('policy_refs') or []) + tuple(attrs.get('process_refs') or [])
        context = QuestDecisionContext(quest_id=int(quest_id), objective_id=int(task['id']), actor=principal,
            agent_node_id=None, command_line=option['command'],
            projection_revision=read_projection_cursor(session, account_node_id=principal.id)[0],
            pinned_rule_refs=refs, correlation_id=new_correlation_id(),
            quest_state_version=int(attrs.get('state_version') or 0),
            objective_state_version=int(task['attributes'].get('state_version') or 0))
        source = GraphQuestGovernance(lock_inputs=False)
        return context, source, source.compile_capabilities(session, context, command_registry), attrs

    def _execute_governed_task_choice(self, session, actor, option):
        from app.services.task.errors import TaskSystemError
        from app.services.task.quest_execution import QuestActionExecutor

        principal = principal_from_actor(user_id=actor.user_id, roles=actor.roles, permissions=actor.permissions)
        try:
            prepared = self._prepare_governed_task_choice(session, principal, option)
            if prepared is None:
                return None
            context, source, capabilities, attrs = prepared
            ensure_commands_initialized()
            capabilities = source.compile_capabilities(session, context, command_registry)
            capability_ref = next(iter(sorted(capabilities)), next(iter(attrs.get('process_refs') or []), 'unavailable'))
            outcome = QuestActionExecutor(capabilities=capabilities, commands=command_registry).execute(
                session, context=context, capability_ref=capability_ref, idempotency_key=str(uuid.uuid4()))
            session.commit()
            result = CommandResult(success=outcome['success'],
                message='Command completed; Quest verification is still required.' if outcome['success']
                    else 'Quest action requires attention. Review the execution record.',
                data={'quest_execution': outcome}, error=None if outcome['success'] else 'quest.execution_escalated')
            reason = outcome['reasonCode']
        except (TaskSystemError, ValueError):
            reason = 'domain_state_changed'
            result = CommandResult.error_result('Quest state changed or is no longer available', error='quest.action_unavailable')
        response = self._state_patch_after_result(session, actor, result)
        response['result']['summaryKey'] = f'worldInteraction.quest.executionReason.{reason}'
        response['result']['reasonCode'] = reason
        return response

    def _decorate_governed_task_choices(self, session, principal, options):
        from app.services.task.quest_decision import compose_quest_decisions
        from app.services.task.errors import TaskSystemError

        seen = set()
        for option in options:
            if id(option) in seen:
                continue
            seen.add(id(option))
            try:
                prepared = self._prepare_governed_task_choice(session, principal, option)
                if prepared is None:
                    continue
                context, source, capabilities, attrs = prepared
                decision = compose_quest_decisions(context=context, governance=source(session, context))
                option['consequenceProvenanceRefs'] = list(context.pinned_rule_refs)
                option['requiredEvidenceRefs'] = source.required_evidence_refs(session, context)
                if attrs.get('risk_level') in {'low', 'normal', 'high', 'critical'}:
                    option['riskLevel'] = attrs['risk_level']
                reason = decision.reason_code
                gate = 'approval_required' if decision.status == 'approval_required' else 'blocked'
                if reason == 'missing_evidence':
                    gate = 'evidence_required'
                if decision.may_request_command_authorization and capabilities:
                    tokens = split_command_line(context.command_line)
                    command = command_registry.get_command(tokens[0])
                    cmd_context = CommandContext(user_id=str(principal.id), username=f'user:{principal.id}',
                        session_id=f'quest-preview:{context.quest_id}', permissions=list(principal.permissions),
                        roles=list(principal.roles), db_session=session)
                    authorized = command is not None and command_registry.authorize_command(command, cmd_context).allowed
                    gate, reason = ('clear', '') if authorized else ('blocked', 'command_authorization_denied')
                elif decision.may_request_command_authorization:
                    reason = 'unregistered_or_unsupported_capability'
                option['gateStatus'], option['gateReasonCode'] = gate, reason
                option['requiresConfirmation'] = bool(option.get('requiresConfirmation')
                    or option.get('riskLevel') in {'high', 'critical'} or option.get('reversible') is False)
            except (TaskSystemError, ValueError):
                option['gateStatus'], option['gateReasonCode'] = 'blocked', 'governance_source_unavailable'

    def execute_quest_interaction_action(
        self,
        session: Session,
        actor: WorldActor,
        *,
        expected_projection_revision: str,
        idempotency_key: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute an optimistic, idempotent Quest interaction mutation."""
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        principal = principal_from_actor(
            user_id=actor.user_id,
            roles=actor.roles,
            permissions=actor.permissions,
        )
        action = str(payload.get("action") or "").strip().lower()
        correlation_id = str(payload.get("correlationId") or "").strip() or new_correlation_id()

        def required_int(name: str) -> int:
            value = payload.get(name)
            if value is None or not str(value).isdigit():
                raise ValueError(f"payload.{name} must be a numeric node id")
            return int(value)

        common = {
            "account_node_id": int(user.id),
            "actor": principal,
            "expected_revision": expected_projection_revision,
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_id,
            "db_session": session,
        }
        if action == "track":
            mutation = track_quest(quest_id=required_int("questId"), **common)
        elif action == "untrack":
            mutation = untrack_quest(quest_id=required_int("questId"), **common)
        elif action == "focus_objective":
            mutation = focus_objective(
                quest_id=required_int("questId"),
                objective_id=required_int("objectiveId"),
                **common,
            )
        elif action in {"pin_clue", "unpin_clue"}:
            mutation = set_clue_pin(
                quest_id=required_int("questId"),
                clue_node_id=required_int("clueNodeId"),
                pinned=action == "pin_clue",
                **common,
            )
        elif action in {"set_collaborator", "remove_collaborator"}:
            mutation = set_collaborator(
                quest_id=required_int("questId"),
                agent_node_id=required_int("agentNodeId"),
                active=action == "set_collaborator",
                role=str(payload.get("role") or "advisor"),
                status=str(payload.get("status") or "active"),
                is_primary_companion=bool(payload.get("isPrimaryCompanion", False)),
                capability_scope=[str(item) for item in payload.get("capabilityScope") or []],
                **common,
            )
        elif action == "situation_attention":
            mutation = set_situation_attention(
                situation_id=required_int("situationId"),
                attention=str(payload.get("attention") or ""),
                snoozed_until=str(payload.get("snoozedUntil") or "") or None,
                **common,
            )
        else:
            raise ValueError(f"unsupported Quest interaction action: {action}")
        session.commit()
        interaction = self.refresh_interaction_state(session, actor)
        return {
            "success": True,
            "result": {
                "summary": "Quest interaction updated.",
                "status": "completed",
                "projectionRevision": mutation.projection_revision,
                "lastEventId": mutation.last_event_id,
                "idempotentReplay": mutation.idempotent_replay,
                "changed": mutation.changed,
            },
            "state_patch": {
                "questInteraction": interaction.get("quest_interaction"),
                "focusSummary": interaction["decision_center"]["focus"],
                "activeTask": interaction["decision_center"].get("activeTask"),
                "newDecisionEvents": interaction["decision_center"].get("decisionEvents", []),
                "contextSummary": interaction.get("context_summary"),
            },
        }

    def run_command_query(self, session: Session, actor: WorldActor, query: str) -> Dict[str, Any]:
        return self._command_query.run(session, actor, query)

    def query_decision_center(self, session: Session, actor: WorldActor, query: str, mode: str) -> Dict[str, Any]:
        if mode == "aico":
            raise ValueError("AICO queries must use POST /decision-center/query/stream")
        return self.run_command_query(session, actor, query)

    def cancel_stream(self, stream_id: str) -> Dict[str, Any]:
        return self._aico_stream_query.cancel(stream_id)

    def archive_conversations(
        self,
        session: Session,
        actor: WorldActor,
        payload: ConversationArchiveRequest,
    ) -> Dict[str, Any]:
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        entry = {
            "id": f"archive_{uuid.uuid4().hex[:12]}",
            "archivedAt": self._now(),
            "aico_threads": [thread.model_dump() for thread in payload.aico_threads],
            "command_conversation": [message.model_dump() for message in payload.command_conversation],
        }
        has_content = bool(entry["aico_threads"]) or bool(entry["command_conversation"])
        if has_content:
            entry["history_summary"] = self._build_archive_history_summary(entry)
            self._archive_repo.append_for_account(session, user, entry)
            session.commit()
        return {"ok": True, "archived": has_content, "archive_id": entry["id"] if has_content else None}

    def validate_quest_conversation_context(
        self,
        session: Session,
        actor: WorldActor,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        principal = principal_from_actor(user_id=actor.user_id, roles=actor.roles, permissions=actor.permissions)
        try:
            quest_id = int(context.get("quest_id"))
            expected_revision = str(context.get("projection_revision") or "")
            objective_id = int(context["objective_id"]) if context.get("objective_id") is not None else None
            agent_id = int(context["agent_node_id"]) if context.get("agent_node_id") is not None else None
        except (TypeError, ValueError) as exc:
            raise PreconditionFailed("Quest conversation context contains an invalid node id") from exc
        revision, _ = read_projection_cursor(session, account_node_id=int(user.id))
        if not expected_revision:
            raise PreconditionFailed("Quest conversation context requires projection_revision")
        if expected_revision != revision:
            raise OptimisticLockError("stale_projection: Quest conversation context is out of date")
        if not can_read_semantic_node(session, node_id=quest_id, actor=principal):
            raise ReferenceNotFound(f"Quest {quest_id} not found")
        tracked = session.execute(
            text("""
                SELECT 1 FROM relationships
                 WHERE source_id = :account_id AND target_id = :quest_id
                   AND type_code = 'TRACKS_QUEST' AND is_active = TRUE
                 LIMIT 1
            """),
            {"account_id": int(user.id), "quest_id": quest_id},
        ).first()
        if tracked is None:
            raise PermissionDenied("Quest conversation requires an explicitly tracked Quest")
        if objective_id is not None:
            if objective_id not in visible_task_ids(session, principal, [objective_id]):
                raise ReferenceNotFound(f"Objective {objective_id} not found")
            objective = session.execute(
                text("""
                    SELECT 1 FROM relationships
                     WHERE source_id = :quest_id AND target_id = :objective_id
                       AND type_code = 'HAS_OBJECTIVE' AND is_active = TRUE
                     LIMIT 1
                """),
                {"quest_id": quest_id, "objective_id": objective_id},
            ).first()
            if objective is None:
                raise PreconditionFailed("Objective does not belong to the Quest")
        collaborator_id = None
        agent_handle = None
        if agent_id is not None:
            if not can_read_semantic_node(session, node_id=agent_id, actor=principal):
                raise ReferenceNotFound(f"Companion Agent {agent_id} not found")
            collaborator = session.execute(
                text("""
                    SELECT id FROM relationships
                     WHERE source_id = :quest_id AND target_id = :agent_id
                       AND type_code = 'ASSISTED_BY' AND is_active = TRUE
                     ORDER BY id DESC LIMIT 1
                """),
                {"quest_id": quest_id, "agent_id": agent_id},
            ).first()
            if collaborator is None:
                raise PermissionDenied("Conversation Agent is not an active Quest collaborator")
            collaborator_id = int(collaborator.id)
            agent_row = session.execute(
                text("SELECT attributes FROM nodes WHERE id = :agent_id AND type_code = 'npc_agent'"),
                {"agent_id": agent_id},
            ).first()
            agent_attributes = dict((agent_row.attributes or {}) if agent_row is not None else {})
            agent_handle = str(agent_attributes.get("handle") or agent_attributes.get("name") or "").strip()
            if not agent_handle or not all(character.isalnum() or character in "_-" for character in agent_handle):
                raise PreconditionFailed("Companion Agent does not have a routable command handle")
        quest_data = show_quest(quest_id=quest_id, actor=principal, db_session=session)
        quest_node = quest_data.get("quest") or {}
        situation = quest_data.get("situation") or {}
        goal = quest_data.get("goal") or {}
        objective = next(
            (item for item in quest_data.get("objectives") or [] if objective_id is not None and int(item.get("task_id") or 0) == objective_id),
            None,
        )
        return {
            "quest_node_id": quest_id,
            "objective_node_id": objective_id,
            "agent_node_id": agent_id,
            "collaboration_relationship_id": collaborator_id,
            "agent_handle": agent_handle,
            "projection_revision": revision,
            "quest_title": str(quest_node.get("title") or ""),
            "situation_assertion": str((situation.get("attributes") or {}).get("assertion") or ""),
            "goal_desired_state": str((goal.get("attributes") or {}).get("desired_state") or ""),
            "objective_title": str((objective or {}).get("title") or ""),
        }

    def stream_aico_query(
        self,
        actor: WorldActor,
        query: str,
        *,
        thread_id: Optional[str] = None,
        quest_context: Optional[Dict[str, Any]] = None,
    ):
        return self._aico_stream_query.stream(actor, query, thread_id=thread_id, quest_context=quest_context)

    def query_semantic_map(self, session: Session, actor: WorldActor, query: str, mode: str = "auto") -> Dict[str, Any]:
        search = self.search(session, actor, query)
        map_patch = build_map_query_patch(session, search["results"], query, mode=mode)
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        location = self._resolve_current_location(session, user)
        if map_patch.get("viewLayer"):
            focus_map = build_focus_map(
                session,
                location,
                view_layer=str(map_patch.get("viewLayer") or "room"),
                anchor_id=map_patch.get("anchorId"),
                mode=str(map_patch.get("mode") or "focus"),
            )
            focus_map = apply_highlight_ids_to_focus_map(
                focus_map,
                list(map_patch.get("highlightedNodeIds") or []),
                mode=str(map_patch.get("mode") or "focus"),
            )
            map_patch["focus_map"] = focus_map
        return {"mode": map_patch["mode"], "answer": search["summary"], "map_patch": map_patch}

    def get_semantic_map_focus(
        self,
        session: Session,
        actor: WorldActor,
        *,
        view_layer: str = "room",
        anchor_id: Optional[str] = None,
        mode: str = "focus",
        selected_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        location = self._resolve_current_location(session, user)
        event_space_ids: Optional[List[str]] = None
        if str(mode or "").strip().lower() == "event":
            event_space_ids = self._decision_event_space_ids(session, actor, location)
        focus_map = build_focus_map(
            session,
            location,
            view_layer=view_layer,
            anchor_id=anchor_id,
            mode=mode,
            selected_entity_id=selected_entity_id,
            event_space_ids=event_space_ids,
        )
        return {"focus_map": focus_map}

    def get_space_summary(self, session: Session, actor: WorldActor, node_id: int) -> Dict[str, Any]:
        data = build_space_summary_data(session, int(node_id))
        if not data:
            return {"ok": False, "error": "Space node not found"}
        return {"ok": True, "summary": data}

    def get_entity_inspect(
        self,
        session: Session,
        actor: WorldActor,
        *,
        node_id: Optional[int] = None,
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from app.services.entity_inspect_service import build_entity_inspect_data, visible_node_ids_from_focus_map

        user = self._get_user_node(session, actor.user_id, username=actor.username)
        location = self._resolve_current_location(session, user)
        focus_map = build_focus_map(session, location, view_layer="room", mode="focus")
        visible_ids = visible_node_ids_from_focus_map(focus_map)
        data = build_entity_inspect_data(
            session,
            actor,
            node_id=node_id,
            agent_id=agent_id,
            visible_node_ids=visible_ids,
        )
        if not data:
            return {"ok": False, "error": "Entity not found or not inspectable"}
        return {"ok": True, "inspect": data}

    def execute_semantic_map_action(
        self,
        session: Session,
        actor: WorldActor,
        *,
        action_type: str,
        view_layer: Optional[str] = None,
        anchor_id: Optional[str] = None,
        mode: str = "focus",
        selected_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        clean = str(action_type or "").strip().lower()
        if clean == "drill":
            return self.get_semantic_map_focus(
                session,
                actor,
                view_layer=view_layer or "room",
                anchor_id=anchor_id,
                mode=mode,
                selected_entity_id=selected_entity_id,
            )
        if clean == "select":
            user = self._get_user_node(session, actor.user_id, username=actor.username)
            location = self._resolve_current_location(session, user)
            layer = str(view_layer or "room").strip().lower()
            resolved_anchor = anchor_id
            if layer == "room" and selected_entity_id and str(selected_entity_id).isdigit():
                resolved_anchor = selected_entity_id
            focus_map = build_focus_map(
                session,
                location,
                view_layer=layer,
                anchor_id=resolved_anchor,
                mode=mode,
                selected_entity_id=selected_entity_id,
            )
            summary = None
            entity_inspect = None
            if selected_entity_id and str(selected_entity_id).isdigit():
                nid = int(selected_entity_id)
                summary = build_space_summary_data(session, nid)
                if summary is None:
                    from app.services.entity_inspect_service import build_entity_inspect_data, visible_node_ids_from_focus_map

                    visible_ids = visible_node_ids_from_focus_map(focus_map)
                    entity_inspect = build_entity_inspect_data(
                        session,
                        actor,
                        node_id=nid,
                        visible_node_ids=visible_ids,
                    )
            return {
                "focus_map": focus_map,
                "space_summary": summary,
                "entity_inspect": entity_inspect,
            }
        return {"ok": False, "error": f"Unsupported map action: {action_type}"}

    def search(self, session: Session, actor: WorldActor, query: str) -> Dict[str, Any]:
        clean = str(query or "").strip()
        if not clean:
            return {"summary": "No query provided.", "results": [], "suggested_actions": []}
        like = f"%{clean}%"
        nodes = (
            session.query(Node)
            .filter(Node.is_active == True)
            .filter(
                or_(
                    Node.name.ilike(like),
                    Node.description.ilike(like),
                    Node.type_code.ilike(like),
                    cast(Node.attributes["display_name"], String).ilike(like),
                    cast(Node.attributes["building_code"], String).ilike(like),
                    cast(Node.attributes["building_name"], String).ilike(like),
                    cast(Node.attributes["package_node_id"], String).ilike(like),
                )
            )
            .limit(20)
            .all()
        )
        results = [self._search_result_for_node(node) for node in nodes]
        ensure_commands_initialized()
        for name, cmd in command_registry.commands.items():
            haystack = f"{name} {cmd.description or ''} {' '.join(cmd.aliases or [])}".lower()
            if clean.lower() in haystack:
                results.append({"entity_id": name, "entity_type": "command", "title": name, "summary": cmd.description or "", "actions": [{"id": f"run_{name}", "label": "Use command", "actionType": "search", "requiresConfirmation": False}]})
        summary = f"Found {len(results)} result(s) for {clean}."
        suggested_actions = []
        if results:
            first = results[0]
            suggested_actions.append({"id": "show_first_result", "label": "Show on map", "actionType": "open_map", "targetEntityId": first["entity_id"], "requiresConfirmation": False})
        return {"summary": summary, "results": results[:20], "suggested_actions": suggested_actions}

    def history_summary(
        self,
        session: Session,
        actor: WorldActor,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        user = self._get_user_node(session, actor.user_id, username=actor.username)
        location = self._resolve_current_location(session, user)
        groups: List[Dict[str, Any]] = [
            {
                "id": "location",
                "title": "Location changes",
                "items": [
                    {
                        "id": f"loc_{location.id}",
                        "title": self._display_name(location),
                        "summary": f"Current location: {self._display_name(location)}",
                        "messageCount": 1,
                        "createdAt": self._now(),
                    }
                ],
            }
        ]
        archives, total = self._archive_repo.list_summaries_for_account(
            session,
            user.id,
            limit=limit,
            offset=offset,
        )
        aico_items: List[Dict[str, Any]] = []
        command_items: List[Dict[str, Any]] = []
        for archive in archives:
            archived_at = archive.get("archivedAt") or self._now()
            summary = dict(archive.get("history_summary") or {})
            if not summary:
                # Pre-summary-format archives are not re-expanded here; the
                # listing intentionally only reads the summary JSON path so the
                # endpoint does not hydrate full message JSONB per batch.
                continue
            aico_items.extend(list(summary.get("aico_items") or []))
            command_items.extend(list(summary.get("command_items") or []))
        if aico_items:
            groups.append({"id": "aico_conversations", "title": "AICO conversations", "items": aico_items})
        if command_items:
            groups.append(
                {
                    "id": "command_conversations",
                    "title": "Command sessions",
                    "items": command_items,
                }
            )
        return {
            "groups": groups,
            "collapsed": True,
            "pagination": {"limit": limit, "offset": offset, "total": total},
        }

    @staticmethod
    def _build_archive_history_summary(entry: Dict[str, Any]) -> Dict[str, Any]:
        archived_at = entry.get("archivedAt") or WorldInteractionService._now()
        archive_id = str(entry.get("id") or "archive")
        aico_items = [
            {
                "id": f"{archive_id}_{thread.get('id', 'thread')}",
                "title": thread.get("title") or "Conversation",
                "messageCount": len(thread.get("messages") or []),
                "preview": WorldInteractionService._history_preview_from_messages(thread.get("messages") or []),
                "createdAt": thread.get("updatedAt") or archived_at,
            }
            for thread in entry.get("aico_threads") or []
            if thread.get("messages")
        ]
        command_items = WorldInteractionService._archived_command_items(
            archive_id,
            entry.get("command_conversation") or [],
            archived_at,
        )
        return {"aico_items": aico_items, "command_items": command_items}

    @staticmethod
    def _history_preview_from_messages(messages: List[Dict[str, Any]]) -> str:
        for message in reversed(messages or []):
            role = message.get("role")
            if role == "assistant":
                text = str(message.get("answer") or message.get("query") or "").strip()
            else:
                text = str(message.get("query") or message.get("answer") or "").strip()
            if text:
                return text[:56]
        return ""

    @staticmethod
    def _archived_command_items(archive_id: str, messages: List[Dict[str, Any]], archived_at: str) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        index = 0
        while index < len(messages):
            message = messages[index]
            if message.get("role") != "user":
                index += 1
                continue
            assistant = messages[index + 1] if index + 1 < len(messages) and messages[index + 1].get("role") == "assistant" else None
            label = str(message.get("query") or message.get("answer") or "").strip()
            detail = str((assistant or {}).get("answer") or label).strip()
            if not label and not detail:
                index += 1
                continue
            items.append(
                {
                    "id": f"{archive_id}_cmd_{message.get('id', index)}",
                    "title": label[:48] if label else "Command",
                    "detail": detail[:120] if detail else label,
                    "messageCount": 2 if assistant else 1,
                    "sequence": len(items),
                    "createdAt": archived_at,
                }
            )
            index += 2 if assistant else 1
        return list(reversed(items))

    def execute_command(self, session: Session, actor: WorldActor, command_line: str) -> CommandResult:
        result = self._command_runner.run(session, actor, command_line)
        parts = split_command_line(str(command_line or '').strip())
        if not result.success or not parts:
            return result
        semantics = resolve_command_tool_semantics(parts[0].lower(), args=parts[1:])
        data = result.data if isinstance(result.data, dict) else {}
        if semantics.interaction_profile != 'mutate':
            return result
        if data.get('projection_revision') is None:
            user = self._get_user_node(session, actor.user_id, username=actor.username)
            principal = principal_from_actor(
                user_id=actor.user_id,
                roles=actor.roles,
                permissions=actor.permissions,
            )
            record_projection_change(
                db_session=session,
                account_node_id=int(user.id),
                actor=principal,
                kind=f'command.{parts[0].lower()}',
            )
        session.commit()
        return result

    def _build_interaction_state(self, session: Session, actor: WorldActor, user: Node, location: Node, current_world_id: Optional[str], available_worlds: List[Dict[str, Any]]) -> Dict[str, Any]:
        principal = principal_from_actor(user_id=actor.user_id, roles=actor.roles, permissions=actor.permissions)
        focus_map = self._focus_map(session, location)
        quest_interaction = build_quest_interaction_projection(
            session,
            account_node_id=int(user.id),
            current_location_id=int(location.id),
            actor=principal,
        )
        decision_center = self._decision_center(
            session,
            principal,
            location,
            current_world_id,
            available_worlds,
            focus_map,
            quest_interaction,
        )
        context_summary = self._context_summary(
            session,
            principal,
            location,
            focus_map,
            current_world_id,
            active_task=decision_center.get("activeTask"),
        )
        return {
            "session": {
                "id": f"world_{actor.user_id}",
                "currentWorldId": current_world_id,
                "currentSpaceId": str(location.id),
                "currentSpaceKey": self._stable_node_key(location),
                "updatedAt": self._now(),
            },
            "decision_center": decision_center,
            "focus_map": focus_map,
            "context_summary": context_summary,
            "quest_interaction": quest_interaction,
            "quick_queries": decision_center["quickQueries"],
        }

    def _decision_center(
        self,
        session: Session,
        principal: Principal,
        location: Node,
        current_world_id: Optional[str],
        available_worlds: List[Dict[str, Any]],
        focus_map: Dict[str, Any],
        quest_interaction: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        queue = list_for_principal(session, principal, limit=DISPLAY_POLICY["maxDecisionEventsVisible"] + 3)
        foreground_quest_id = str((quest_interaction or {}).get("foregroundQuestId") or "")
        foreground = next(
            (
                item
                for item in (quest_interaction or {}).get("trackedQuests") or []
                if str(item.get("id")) == foreground_quest_id
            ),
            None,
        )
        foreground_objective_id = None
        if foreground:
            foreground_objective_id = foreground.get("focusedObjectiveId") or foreground.get("recommendedObjectiveId")
        if foreground_objective_id is not None:
            queue = sorted(queue, key=lambda row: 0 if str(row.id) == str(foreground_objective_id) else 1)
        events: List[Dict[str, Any]] = [self._task_queue_event(row) for row in queue]
        primary_action = events[0]["options"][0] if events and events[0].get("options") else None

        if not events:
            if not current_world_id:
                target = next((item for item in available_worlds if item.get("is_recommended")), available_worlds[0] if available_worlds else None)
                if target:
                    primary_action = self._option(
                        "enter_world",
                        f"Enter {target['name']}",
                        "primary",
                        "execute_command",
                        command=f"enter {target['world_id']}",
                        target=str(target["world_id"]),
                        label_key="worldInteraction.decision.action.enterWorld",
                        label_params={"name": target['name']},
                    )
                    events.append(
                        self._event(
                            "enter_world",
                            "Enter a world",
                            "Choose a CampusWorld world to start interacting with spaces, agents, and tasks.",
                            "navigation",
                            "The current system room is the hub for world entry.",
                            "Enter a recommended world or choose another from the world switcher.",
                            [primary_action],
                            [{"id": str(target["world_id"]), "type": "space", "label": target["name"]}],
                        )
                    )
            else:
                next_edge = next((edge for edge in focus_map["edges"] if edge.get("status") == "recommended"), None)
                if next_edge:
                    command = f"go {next_edge.get('direction') or next_edge.get('label')}"
                    primary_action = self._option("go_next", f"Go to {next_edge['targetLabel']}", "primary", "execute_command", command=command, target=str(next_edge["to"]), label_key="worldInteraction.decision.action.goTo", label_params={"name": next_edge['targetLabel']})
                    events.append(
                        self._event(
                            "next_navigation",
                            f"Next: {next_edge['targetLabel']}",
                            "This reachable space is the clearest next move from your current location.",
                            "navigation",
                            "Moving updates your authoritative account location.",
                            "Continue through the highlighted route.",
                            [primary_action, self._option("show_route", "Show route", "secondary", "open_map", target=str(next_edge["to"]), label_key="worldInteraction.decision.action.showRoute")],
                            [{"id": str(next_edge["to"]), "type": "space", "label": next_edge["targetLabel"]}],
                        )
                    )

        active_queue = queue
        if foreground is not None:
            # The HUD is the foreground Quest projection, not an alias for the
            # first visible queue item. If its Objective is not actionable in
            # this principal's queue, do not silently show an unrelated task.
            active_queue = [
                row for row in queue
                if foreground_objective_id is not None and str(row.id) == str(foreground_objective_id)
            ]
        active_task = self._active_task_from_queue(
            active_queue,
            primary_action if active_queue and str(active_queue[0].id) == str(queue[0].id) else None,
            session=session,
            principal=principal,
            quest_projection=foreground,
        )
        quest_objectives = {str(row.id) for row in queue if row.quest_id is not None}
        preview_options = [option for event in events[: DISPLAY_POLICY['maxDecisionEventsVisible']]
                           for option in event.get('options') or []]
        if active_task:
            preview_options += [active_task['nextBestAction']] + list(active_task.get('alternativeActions') or [])
        self._decorate_governed_task_choices(session, principal,
            [option for option in preview_options if str(option.get('targetEntityId')) in quest_objectives])
        focus = {
            "title": self._display_name(location),
            "summary": self._focus_summary_text(location, current_world_id, events, queue),
            "currentSpaceId": str(location.id),
            "currentTaskId": active_task["id"] if active_task else None,
            "severity": "warning" if queue else ("info" if events else "normal"),
            "primaryAction": primary_action,
        }
        return {
            "focus": focus,
            "decisionEvents": events[: DISPLAY_POLICY["maxDecisionEventsVisible"]],
            "activeTask": active_task,
            "nextBestAction": primary_action,
            "quickQueries": self._quick_queries(current_world_id),
            "loading": False,
            "error": None,
        }

    def _task_queue_event(self, row: QueueTaskRow) -> Dict[str, Any]:
        options = self._options_for_queue_task(row)
        priority = "urgent" if row.priority == "urgent" else "important" if row.priority == "high" else "normal"
        return self._event(
            f"task_{row.id}",
            row.title,
            f"Task #{row.id} is {row.state}. Handle it from your queue.",
            "task",
            "Completing or advancing this task updates your work queue.",
            "Use the primary action to advance the task state.",
            options,
            [{"id": str(row.id), "type": "task", "label": row.title}],
            priority=priority,
        )

    def _options_for_queue_task(self, row: QueueTaskRow) -> List[Dict[str, Any]]:
        state = row.state
        task_id = row.id
        if state in {"open", "rejected"} and row.visibility == "pool_open" and row.assignee_kind == "pool":
            return [self._option(f"task_claim_{task_id}", "Claim task", "primary", "execute_command", command=f"task claim {task_id}", target=str(task_id), label_key="worldInteraction.decision.action.claim", consequence_kind="proposed", consequence_summary="If accepted, you become responsible for this Objective.", consequence_summary_key="worldInteraction.decision.actionConsequence.claim", gate_status="clear", reversible=True, affected_entity_refs=[str(task_id)])]
        if state == "claimed":
            return [self._option(f"task_start_{task_id}", "Start task", "primary", "execute_command", command=f"task start {task_id}", target=str(task_id), label_key="worldInteraction.decision.action.start", consequence_kind="proposed", consequence_summary="If accepted, this Objective enters active work.", consequence_summary_key="worldInteraction.decision.actionConsequence.start", gate_status="clear", reversible=True, affected_entity_refs=[str(task_id)])]
        if state in {"in_progress", "approved"}:
            return [self._option(f"task_complete_{task_id}", "Complete task", "primary", "execute_command", command=f"task complete {task_id}", target=str(task_id), requires_confirmation=True, label_key="worldInteraction.decision.action.complete", consequence_kind="proposed", consequence_summary="If accepted, only this Objective is recorded complete; Quest acceptance still requires verification.", consequence_summary_key="worldInteraction.decision.actionConsequence.complete", gate_status="clear", reversible=False, affected_entity_refs=[str(task_id)])]
        return [self._option(f"task_show_{task_id}", "View task", "secondary", "execute_command", command=f"task show {task_id}", target=str(task_id), label_key="worldInteraction.decision.action.view")]

    def _active_task_from_queue(
        self,
        queue: Sequence[QueueTaskRow],
        primary_action: Optional[Dict[str, Any]],
        *,
        session: Optional[Session] = None,
        principal: Optional[Principal] = None,
        quest_projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not queue:
            return None
        row = queue[0]
        primary = primary_action or (self._options_for_queue_task(row)[0] if self._options_for_queue_task(row) else None)
        if not primary:
            return None
        quest_context = self._quest_context(
            session,
            row,
            principal,
            quest_projection=quest_projection,
        ) if session is not None and principal is not None else None
        aggregate_progress = (quest_projection or {}).get("progress") or {}
        progress = aggregate_progress.get("percent") if quest_projection is not None else None
        if progress is None and quest_context is not None:
            progress = quest_context.get("progress")
        return {
            "id": f"task_{row.id}",
            "title": row.title,
            "summary": f"State: {row.state}",
            "status": "active",
            "questId": str(row.quest_id) if row.quest_id is not None else None,
            "questTitle": row.quest_title,
            "questContext": quest_context,
            "progress": int(progress) if progress is not None else None,
            "currentStep": {
                "id": f"task_step_{row.id}",
                "title": primary["label"],
                "shortInstruction": f"Task is {row.state}.",
                "status": "active",
                "expectedAction": primary.get("command"),
            },
            "nextBestAction": primary,
            "alternativeActions": self._options_for_queue_task(row)[1:],
            "blockers": [],
        }

    def _quest_context(
        self,
        session: Session,
        row: QueueTaskRow,
        principal: Principal,
        *,
        quest_projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Build a compact Mission Card projection from semantic-world nodes."""
        if row.quest_id is None:
            return None
        try:
            data = show_quest(quest_id=int(row.quest_id), actor=principal, db_session=session)
        except ReferenceNotFound:
            return None
        quest = data["quest"]
        attrs = dict(quest.get("attributes") or {})
        situation = data.get("situation")
        goal = data.get("goal")
        situation_attrs = dict((situation or {}).get("attributes") or {})
        goal_attrs = dict((goal or {}).get("attributes") or {})
        situation_projection = (quest_projection or {}).get("situation") or {}
        return {
            "state": str(attrs.get("current_state") or "draft"),
            "riskLevel": str(attrs.get("risk_level") or "normal"),
            "situation": {
                "id": str(situation["id"]),
                "title": str(situation.get("title") or ""),
                "assertion": str(situation_attrs.get("assertion") or ""),
                "subjectRef": situation_projection.get("primarySubjectRef") or (
                    str(situation_attrs.get("subject_ref")) if situation_attrs.get("subject_ref") is not None else None
                ),
                "relatedEntityRefs": list(situation_projection.get("relatedEntityRefs") or []),
                "scopedAtRef": situation_projection.get("scopedAtRef"),
                "triggerKind": str(situation_attrs.get("trigger_kind") or "manual"),
                "confidence": situation_attrs.get("confidence"),
                "severity": str(situation_attrs.get("severity") or "medium"),
            } if situation else None,
            "goal": {
                "id": str(goal["id"]),
                "title": str(goal.get("title") or ""),
                "desiredState": str(goal_attrs.get("desired_state") or ""),
            } if goal else None,
            "governanceRefs": list(attrs.get("policy_refs") or []),
            "processRefs": list(attrs.get("process_refs") or []),
            "qualityRefs": list(attrs.get("quality_refs") or []),
            "caseRefs": list(attrs.get("case_refs") or []),
            "progress": int((data.get("progress") or {}).get("percent", 0)),
            "companion": (quest_projection or {}).get("companion"),
            "companionFallback": (quest_projection or {}).get("companionFallback") or "aico",
        }

    def _decision_event_space_ids(self, session: Session, actor: WorldActor, location: Node) -> List[str]:
        principal = principal_from_actor(user_id=actor.user_id, roles=actor.roles, permissions=actor.permissions)
        queue = list_for_principal(session, principal, limit=DISPLAY_POLICY["maxDecisionEventsVisible"] + 3)
        ids: List[str] = []
        for row in queue:
            task_node = (
                session.query(Node)
                .filter(Node.id == int(row.id), Node.type_code == "task", Node.is_active == True)
                .first()
            )
            if task_node and task_node.location_id:
                ids.append(str(task_node.location_id))
            events = [self._task_queue_event(row)]
            for event in events:
                for ent in event.get("relatedEntities") or []:
                    if str(ent.get("type")) == "space":
                        eid = str(ent.get("id") or "")
                        if eid.isdigit():
                            ids.append(eid)
        if not queue:
            for exit_row in connects_to_exits_from_room(session, int(location.id)):
                target_id = str(exit_row.get("target_id") or "")
                if target_id.isdigit():
                    ids.append(target_id)
                    break
        deduped: List[str] = []
        seen: set[str] = set()
        for item in ids:
            if item not in seen:
                seen.add(item)
                deduped.append(item)
        return deduped

    def _focus_map(self, session: Session, location: Node) -> Dict[str, Any]:
        return build_focus_map(session, location, view_layer="room", mode="focus")

    def _context_summary(
        self,
        session: Session,
        principal: Principal,
        location: Node,
        focus_map: Dict[str, Any],
        current_world_id: Optional[str],
        *,
        active_task: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        agents = focus_map.get("agentPresences") or []
        queue = list_for_principal(session, principal, limit=20)
        handled = last_handled_task(session, principal)
        summary_task = None
        if active_task:
            summary_task = {
                "id": active_task.get("id"),
                "title": active_task.get("questTitle") or active_task.get("title"),
                "currentStep": (active_task.get("currentStep") or {}).get("title") or active_task.get("summary"),
                "progress": active_task.get("progress"),
            }
        payload: Dict[str, Any] = {
            "currentSpace": {"id": str(location.id), "name": self._display_name(location), "oneLineSummary": self._one_line(location)},
            "nearbyAgents": {"total": len(agents), "highlighted": [{"id": a["agentId"], "name": a["name"], "role": a["role"], "status": a["status"], "locationName": self._display_name(location)} for a in agents]},
            "pendingDecisionCount": len(queue),
            "suggestedQueries": self._quick_queries(current_world_id),
        }
        if summary_task:
            payload["activeTask"] = summary_task
        if handled:
            payload["lastHandledTask"] = handled
        return payload

    def _state_patch_after_result(self, session: Session, actor: WorldActor, result: CommandResult, resolved_event_id: Optional[str] = None) -> Dict[str, Any]:
        interaction = self.refresh_interaction_state(session, actor)
        state_patch = {
            "currentSpaceId": interaction["session"]["currentSpaceId"],
            "focusSummary": interaction["decision_center"]["focus"],
            "activeTask": interaction["decision_center"].get("activeTask"),
            "newDecisionEvents": interaction["decision_center"].get("decisionEvents", []),
            "mapPatch": {
                "mode": interaction["focus_map"].get("mode"),
                "viewLayer": interaction["focus_map"].get("viewLayer"),
                "visibleNodeIds": [node["id"] for node in interaction["focus_map"].get("nodes", [])],
                "highlightedNodeIds": [
                    node["id"]
                    for node in interaction["focus_map"].get("nodes", [])
                    if node.get("status") in {"active", "current"}
                ],
                "highlightedPath": interaction["focus_map"].get("highlightedPath", []),
                "agentPresences": list(interaction["focus_map"].get("agentPresences") or []),
            },
            "contextSummary": interaction.get("context_summary"),
            "questInteraction": interaction.get("quest_interaction"),
            "historyAppend": [{"id": f"cmd_{datetime.utcnow().timestamp()}", "summary": result.message, "createdAt": self._now()}],
        }
        if resolved_event_id:
            state_patch["resolvedDecisionEventIds"] = [resolved_event_id]
        return {"success": result.success, "result": {"summary": result.message, "status": "completed" if result.success else "failed", "error": result.error}, "state_patch": state_patch, "command_result": self._command_result_payload(result)}

    def _get_user_node(self, session: Session, user_id: str, *, username: str = "") -> Node:
        clean_id = str(user_id or "").strip()
        node: Optional[Node] = None
        if clean_id.isdigit():
            node = session.query(Node).filter(Node.id == int(clean_id), Node.type_code == "account").first()
        if not node and username:
            node = session.query(Node).filter(Node.type_code == "account", Node.name == username).first()
        if not node and clean_id and "@" in clean_id:
            node = (
                session.query(Node)
                .filter(Node.type_code == "account", Node.attributes["email"].astext == clean_id)
                .first()
            )
        if not node:
            raise ValueError("Authenticated account node not found")
        return node

    def _resolve_current_location(self, session: Session, user: Node) -> Node:
        location = session.query(Node).filter(Node.id == user.location_id, Node.is_active == True).first() if user.location_id else None
        if location:
            return location
        if not root_manager.ensure_root_node_exists():
            raise ValueError("Singularity room is unavailable")
        session.expire_all()
        root = root_manager.get_root_node(session)
        if not root:
            raise ValueError("Singularity room is unavailable")
        user.location_id = root.id
        user.home_id = root.id
        session.add(user)
        session.commit()
        return root

    @staticmethod
    def _append_unique(items: List[str], item: str) -> None:
        clean = str(item or "").strip().lower()
        if clean and clean not in items:
            items.append(clean)

    @staticmethod
    def _world_id_for_node(node: Optional[Node]) -> Optional[str]:
        if not node:
            return None
        attrs = dict(node.attributes or {})
        if attrs.get("is_root") is True or str(attrs.get("is_root")).lower() == "true":
            return None
        wid = attrs.get("world_id")
        return str(wid).lower() if wid else None

    @staticmethod
    def _display_name(node: Optional[Node]) -> str:
        if not node:
            return "Unknown"
        attrs = dict(node.attributes or {})
        return str(attrs.get("display_name") or attrs.get("room_name") or attrs.get("name") or node.name)

    def _world_display_names(self, session: Session) -> Dict[str, str]:
        labels: Dict[str, str] = {}
        world_nodes = session.query(Node).filter(Node.type_code == "world", Node.is_active == True).limit(200).all()
        for node in world_nodes:
            attrs = dict(node.attributes or {})
            wid = str(attrs.get("world_id") or node.name or "").strip().lower()
            if wid:
                labels[wid] = self._display_name(node)
        return labels

    def _world_label(self, world_id: str, entrance: Optional[Node], labels: Dict[str, str]) -> str:
        if entrance:
            return self._display_name(entrance)
        if world_id in labels:
            return labels[world_id]
        if world_id == "hicampus":
            return "HiCampus"
        return world_id.replace("_", " ").title()

    def _one_line(self, node: Node) -> str:
        attrs = dict(node.attributes or {})
        return str(attrs.get("short_desc") or attrs.get("room_short_description") or node.description or self._display_name(node))

    def _stable_node_key(self, node: Node) -> str:
        attrs = dict(node.attributes or {})
        return str(attrs.get("id") or attrs.get("node_id") or attrs.get("room_code") or node.id)

    def _map_node(self, node: Node, status: str, x: int, y: int) -> Dict[str, Any]:
        return {
            "id": str(node.id),
            "name": self._display_name(node),
            "type": self._map_node_type(node),
            "x": x,
            "y": y,
            "status": status,
            "semanticTags": list(node.tags or [])[:4],
            "activeAgentIds": [],
            "activeEventIds": [],
            "objectIds": [],
        }

    @staticmethod
    def _map_node_type(node: Node) -> str:
        type_code = str(node.type_code or "")
        if "building" in type_code:
            return "building"
        if "room" in type_code or "floor" in type_code:
            return "room"
        return "service" if type_code not in {"room", "building"} else type_code

    def _agents_near(self, session: Session, location_ids: List[int]) -> List[Dict[str, Any]]:
        if not location_ids:
            return []
        agents = session.query(Node).filter(Node.location_id.in_(location_ids), Node.type_code == "npc_agent", Node.is_active == True).limit(DISPLAY_POLICY["maxAgentsHighlighted"]).all()
        out = []
        for agent in agents:
            attrs = dict(agent.attributes or {})
            out.append(
                {
                    "agentId": str(agent.id),
                    "name": self._display_name(agent),
                    "role": str(attrs.get("role") or "guide"),
                    "currentSpaceId": str(agent.location_id),
                    "status": str(attrs.get("status") or "waiting"),
                    "currentIntent": attrs.get("current_intent"),
                    "currentTask": attrs.get("current_task"),
                    "lastSeenAt": self._now(),
                    "visibility": "visible",
                }
            )
        return out

    def _event(
        self,
        event_id: str,
        title: str,
        summary: str,
        event_type: str,
        impact: str,
        recommendation: str,
        options: List[Dict[str, Any]],
        related: List[Dict[str, Any]],
        *,
        priority: str = "important",
    ) -> Dict[str, Any]:
        return {
            "id": event_id,
            "title": title,
            "summary": summary,
            "type": event_type,
            "priority": priority,
            "status": "new",
            "source": "system",
            "impact": impact,
            "recommendation": recommendation,
            "options": options[: DISPLAY_POLICY["maxActionsPerCard"]],
            "relatedEntities": related,
            "createdAt": self._now(),
        }

    @staticmethod
    def _option(
        option_id: str,
        label: str,
        style: str,
        action_type: str,
        *,
        command: Optional[str] = None,
        target: Optional[str] = None,
        requires_confirmation: bool = False,
        label_key: Optional[str] = None,
        label_params: Optional[Dict[str, Any]] = None,
        consequence_kind: Optional[str] = None,
        consequence_summary: Optional[str] = None,
        consequence_summary_key: Optional[str] = None,
        consequence_provenance_refs: Optional[List[str]] = None,
        consequence_confidence: Optional[float] = None,
        risk_level: Optional[str] = None,
        required_evidence_refs: Optional[List[str]] = None,
        gate_status: Optional[str] = None,
        reversible: Optional[bool] = None,
        affected_entity_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "id": option_id,
            "label": label,
            "labelKey": label_key,
            "labelParams": label_params or {},
            "style": style,
            "actionType": action_type,
            "command": command,
            "targetEntityId": target,
            "requiresConfirmation": bool(
                requires_confirmation or risk_level in {'high', 'critical'} or reversible is False
            ),
            "consequenceKind": consequence_kind,
            "consequenceSummary": consequence_summary,
            "consequenceSummaryKey": consequence_summary_key,
            "consequenceProvenanceRefs": consequence_provenance_refs or [],
            "consequenceConfidence": consequence_confidence,
            "riskLevel": risk_level,
            "requiredEvidenceRefs": required_evidence_refs or [],
            "gateStatus": gate_status,
            "reversible": reversible,
            "affectedEntityRefs": affected_entity_refs or ([target] if target else []),
        }

    def _focus_summary_text(
        self,
        location: Node,
        current_world_id: Optional[str],
        events: Sequence[Dict[str, Any]],
        queue: Sequence[QueueTaskRow],
    ) -> str:
        if queue:
            return f"{len(queue)} task(s) need your attention."
        if not current_world_id:
            return "You are in the CampusWorld system hub. Choose a world to enter."
        if events:
            return events[0]["summary"]
        return f"You are in {self._display_name(location)}."

    @staticmethod
    def _quick_queries(current_world_id: Optional[str]) -> List[Dict[str, str]]:
        return []

    def _search_result_for_node(self, node: Node) -> Dict[str, Any]:
        entity_type = "agent" if node.type_code == "npc_agent" else "space" if self._world_id_for_node(node) or node.type_code in {"room", "building", "building_floor"} else "object"
        return {
            "entity_id": str(node.id),
            "entity_type": entity_type,
            "title": self._display_name(node),
            "summary": self._one_line(node),
            "actions": [{"id": f"show_{node.id}", "label": "Show on map", "actionType": "open_map", "targetEntityId": str(node.id), "requiresConfirmation": False}],
        }

    @staticmethod
    def _command_result_payload(result: CommandResult) -> Dict[str, Any]:
        return {"success": result.success, "message": result.message, "data": result.data, "error": result.error, "should_exit": result.should_exit}

    @staticmethod
    def _now() -> str:
        return datetime.utcnow().isoformat() + "Z"


world_interaction_service = WorldInteractionService()
