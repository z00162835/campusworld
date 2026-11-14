"""Deterministic governance over readable, exact, published graph knowledge versions.

World packages own their policy/process nodes and publication. This evaluator
does not create rules, infer permissions or publish model-generated content.
"""
from __future__ import annotations

import math

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.commands.shell_words import split_command_line
from app.services.task.errors import ReferenceNotFound
from app.services.task.quest_decision import QuestDecisionContext, QuestGovernanceDecision, render_quest_template
from app.services.task.quest_semantic_service import can_read_semantic_node, split_semantic_ref
from app.services.task.task_state_machine import load_node_ref
from app.services.task.task_visibility_sql import visible_task_ids


class _Rejected(Exception):
    pass


class GraphQuestGovernance:
    """Fail closed when source versions or hard-control inputs are incomplete."""
    _risk = {'low': 0, 'normal': 1, 'high': 2, 'critical': 3}
    _policy_fields = frozenset({'schema_version', 'allowed_process_refs', 'risk_ceiling',
        'min_confidence', 'requires_approval', 'allow_automatic', 'required_evidence_refs'})

    def __init__(self, *, lock_inputs=True):
        self._lock_inputs = lock_inputs

    @property
    def _read_lock(self):
        return ' FOR SHARE' if self._lock_inputs else ''

    def _node(self, session, node_id, type_code, actor):
        visible = (node_id in visible_task_ids(session, actor, [node_id]) if type_code == 'task'
                   else can_read_semantic_node(session, node_id=node_id, actor=actor))
        if not visible:
            raise _Rejected('governance_source_unavailable')
        if self._lock_inputs:
            session.execute(text('SELECT id FROM nodes WHERE id = :id FOR SHARE'), {'id': node_id}).first()
        return load_node_ref(session, node_id=node_id, expected_type_code=type_code)

    def _definition(self, session, ref, types, actor):
        namespace, key, version = split_semantic_ref(ref)
        if (not namespace or not key or not version or version.lower() in {'latest', 'head', 'current'}
                or '*' in version):
            raise _Rejected('governance_version_unpinned')
        rows = session.execute(text("""
            SELECT id, type_code, attributes FROM nodes
            WHERE is_active = TRUE AND type_code = ANY(:types)
              AND attributes->>'semantic_ref' = :ref
            LIMIT 2
        """ + self._read_lock), {'types': list(types), 'ref': ref}).all()
        if len(rows) != 1:
            raise _Rejected('governance_source_unavailable')
        row = rows[0]
        if not can_read_semantic_node(session, node_id=int(row.id), actor=actor):
            raise _Rejected('governance_source_unavailable')
        attrs = row.attributes
        if (not isinstance(attrs, dict) or str(attrs.get('version')) != version
                or attrs.get('publication_state') != 'published'):
            raise _Rejected('governance_version_unpublished')
        definition = attrs.get('definition')
        if not isinstance(definition, dict) or type(definition.get('schema_version')) is not int or definition['schema_version'] != 1:
            raise _Rejected('governance_schema_unsupported')
        return definition

    def _evidence(self, session, ref, context, situation_id):
        if isinstance(ref, str) and ref.isdigit():
            if self._lock_inputs:
                session.execute(text('SELECT id FROM nodes WHERE id = :id FOR SHARE'), {'id': int(ref)}).first()
            row = load_node_ref(session, node_id=int(ref))
        else:
            rows = session.execute(text("""
                SELECT id, type_code, attributes FROM nodes
                WHERE is_active = TRUE AND type_code = ANY(:types)
                  AND attributes->>'semantic_ref' = :ref LIMIT 2
            """ + self._read_lock), {'types': ['observation', 'fact', 'evidence'], 'ref': ref}).all()
            if len(rows) != 1:
                raise _Rejected('missing_evidence')
            row = {'id': rows[0].id, 'type_code': rows[0].type_code, 'attributes': rows[0].attributes}
        if (row.get('type_code') not in {'observation', 'fact', 'evidence'}
                or not can_read_semantic_node(session, node_id=int(row['id']), actor=context.actor)
                or row['attributes'].get('verification_status') not in {'verified', 'supported'}):
            raise _Rejected('missing_evidence')
        linked = session.execute(text("""
            SELECT 1 FROM relationships WHERE is_active = TRUE
              AND type_code = ANY(:types) AND source_id = ANY(:roots) AND target_id = :evidence_id
            LIMIT 1
        """ + self._read_lock), {'types': ['SUPPORTED_BY', 'BASED_ON_FACT'],
               'roots': [context.quest_id, context.objective_id, situation_id],
               'evidence_id': int(row['id'])}).first()
        if linked is None:
            raise _Rejected('missing_evidence')

    def compile_capabilities(self, session, context, commands):
        """Compile published finite templates, never free-form model commands."""
        from app.services.task.quest_execution import RegisteredQuestCapability
        from app.commands.command_tool_semantics import resolve_command_tool_semantics

        result = {}
        try:
            quest = self._node(session, context.quest_id, 'quest', context.actor)['attributes']
            process_refs = quest.get('process_refs')
            if not isinstance(process_refs, list) or len(process_refs) > 16:
                return {}
            for ref in process_refs:
                process = self._definition(session, ref, ('process_pattern',), context.actor)
                if set(process) != {'schema_version', 'command_templates'}:
                    return {}
                templates = process['command_templates']
                if not isinstance(templates, list) or len(templates) > 32 or any(not isinstance(item, str) for item in templates):
                    return {}
                for template in templates:
                    parts = split_command_line(template)
                    if not parts or parts[0].startswith('@'):
                        continue
                    command = commands.get_command(parts[0])
                    if command is None or command.name != parts[0]:
                        continue
                    capability = RegisteredQuestCapability(ref=ref, command_name=parts[0],
                        args=tuple(parts[1:]), database_transactional=True)
                    tokens = capability.tokens(context)
                    if list(tokens) != split_command_line(context.command_line):
                        continue
                    sem = resolve_command_tool_semantics(tokens[0], args=tokens[1:], registry=commands)
                    if sem.semantic_pending or not command.supports_managed_transaction(list(tokens[1:])):
                        continue
                    result[ref] = capability
        except (_Rejected, KeyError, TypeError, ValueError, ReferenceNotFound):
            return {}
        return result

    def required_evidence_refs(self, session, context):
        """Describe rule requirements for a preview, without granting execution."""
        result = set()
        try:
            quest = self._node(session, context.quest_id, 'quest', context.actor)['attributes']
            refs = quest.get('policy_refs')
            if not isinstance(refs, list) or len(refs) > 32:
                return []
            for ref in refs:
                policy = self._definition(session, ref, ('policy', 'control'), context.actor)
                evidence = policy.get('required_evidence_refs')
                if not isinstance(evidence, list) or len(evidence) > 64 or any(not isinstance(item, str) for item in evidence):
                    return []
                result.update(evidence)
        except (_Rejected, KeyError, TypeError, ValueError, ReferenceNotFound):
            return []
        return sorted(result)

    def __call__(self, session: Session, context: QuestDecisionContext) -> QuestGovernanceDecision:
        decision, reason = 'deny', 'governance_input_invalid'
        refs = ()
        selected_capability = None
        try:
            quest = self._node(session, context.quest_id, 'quest', context.actor)['attributes']
            if quest.get('governance_mode') != 'enforced':
                raise _Rejected('quest_governance_not_enforced')
            objective = self._node(session, context.objective_id, 'task', context.actor)['attributes']
            if int(objective.get('quest_id') or 0) != context.quest_id:
                raise _Rejected('objective_scope_mismatch')
            if (context.quest_state_version is None or context.objective_state_version is None
                    or quest.get('state_version') != context.quest_state_version
                    or objective.get('state_version') != context.objective_state_version):
                raise _Rejected('domain_state_changed')
            if quest.get('current_state') != 'executing':
                raise _Rejected('quest_not_executable')
            if quest.get('execution_hold') is not False:
                raise _Rejected('quest_execution_hold')
            goal = self._node(session, int(quest['goal_id']), 'goal', context.actor)['attributes']
            if goal.get('constraints') or quest.get('quality_refs'):
                raise _Rejected('governance_schema_unsupported')
            policy_refs, process_refs = quest.get('policy_refs'), quest.get('process_refs')
            if (not isinstance(policy_refs, list) or not policy_refs or not isinstance(process_refs, list)
                    or not process_refs or len(policy_refs) > 32 or len(process_refs) > 16
                    or any(not isinstance(ref, str) for ref in policy_refs + process_refs)):
                raise _Rejected('governance_versions_missing')
            refs = tuple(policy_refs + process_refs)
            if set(refs) != set(context.pinned_rule_refs):
                raise _Rejected('governance_versions_changed')
            # Process knowledge declares capabilities; it never overrides hard controls.
            matching_processes = []
            for ref in process_refs:
                process = self._definition(session, ref, ('process_pattern',), context.actor)
                if set(process) != {'schema_version', 'command_templates'}:
                    raise _Rejected('governance_schema_unsupported')
                templates = process.get('command_templates')
                if not isinstance(templates, list) or len(templates) > 32 or any(not isinstance(item, str) for item in templates):
                    raise _Rejected('governance_input_invalid')
                for template in templates:
                    rendered = render_quest_template(template, context)
                    if split_command_line(rendered) == split_command_line(context.command_line):
                        matching_processes.append(ref)
            if not matching_processes:
                raise _Rejected('process_capability_not_allowed')
            if len(set(matching_processes)) != 1:
                raise _Rejected('process_capability_ambiguous')
            selected_capability = matching_processes[0]
            situation_id = int(quest['situation_id'])
            situation = self._node(session, situation_id, 'situation', context.actor)['attributes']
            approval = False
            for ref in policy_refs:
                policy = self._definition(session, ref, ('policy', 'control'), context.actor)
                if set(policy) != self._policy_fields:
                    raise _Rejected('governance_schema_unsupported')
                if any(type(policy[field]) is not bool for field in ('requires_approval', 'allow_automatic')):
                    raise _Rejected('governance_input_invalid')
                allowed = policy['allowed_process_refs']
                if not isinstance(allowed, list) or not any(item in allowed for item in matching_processes):
                    raise _Rejected('process_capability_not_allowed')
                ceiling, risk = policy['risk_ceiling'], quest.get('risk_level')
                if ceiling not in self._risk or risk not in self._risk or self._risk[risk] > self._risk[ceiling]:
                    raise _Rejected('risk_budget_exceeded')
                threshold, confidence = policy['min_confidence'], situation.get('confidence')
                if (type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1):
                    raise _Rejected('governance_input_invalid')
                if threshold > 0 and (type(confidence) not in (int, float) or not math.isfinite(confidence)
                                     or not 0 <= confidence <= 1 or confidence < threshold):
                    raise _Rejected('low_confidence')
                if context.agent_node_id is not None and not policy['allow_automatic']:
                    raise _Rejected('automatic_execution_not_allowed')
                evidence = policy['required_evidence_refs']
                if not isinstance(evidence, list) or len(evidence) > 64 or any(not isinstance(item, str) for item in evidence):
                    raise _Rejected('governance_input_invalid')
                for evidence_ref in evidence:
                    self._evidence(session, evidence_ref, context, situation_id)
                approval = approval or policy['requires_approval']
            decision, reason = ('require_approval', 'approval_required') if approval else ('allow', 'governance_pass')
        except _Rejected as exc:
            reason = str(exc)
        except (KeyError, TypeError, ValueError, ReferenceNotFound):
            reason = 'governance_input_invalid'
        return QuestGovernanceDecision(decision, reason, context.projection_revision, refs, context,
                                       capability_ref=selected_capability)
