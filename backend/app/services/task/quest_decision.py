"""Pure Quest/Agent decision composition; never grants command authorization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
from string import Formatter

from app.game_engine.agent_runtime.policy.decisions import PolicyDecision
from app.services.task.permissions import Principal
from app.services.task.quest_semantic_service import split_semantic_ref


@dataclass(frozen=True)
class QuestDecisionContext:
    quest_id: int
    objective_id: int
    actor: Principal
    agent_node_id: Optional[int]
    command_line: str
    projection_revision: str
    pinned_rule_refs: tuple[str, ...]
    correlation_id: str
    quest_state_version: Optional[int] = None
    objective_state_version: Optional[int] = None


def render_quest_template(template: str, context: QuestDecisionContext) -> str:
    """Only interpolate the two approved integer scope identifiers."""
    fields = {'quest_id': context.quest_id, 'objective_id': context.objective_id}
    for _literal, name, specification, conversion in Formatter().parse(template):
        if name is not None and (name not in fields or specification or conversion):
            raise ValueError('Unsupported Quest capability template field')
    return template.format_map(fields)


@dataclass(frozen=True)
class QuestGovernanceDecision:
    """Result supplied by the owning versioned Quest governance evaluator."""

    decision: Literal['allow', 'deny', 'require_approval']
    reason_code: str
    projection_revision: str
    rule_refs: tuple[str, ...]
    context: QuestDecisionContext
    capability_ref: Optional[str] = None


@dataclass(frozen=True)
class QuestDecisionComposition:
    status: Literal['blocked', 'approval_required', 'ready_for_command_authorization']
    reason_code: str
    context: QuestDecisionContext
    governance: QuestGovernanceDecision
    behavior: Optional[PolicyDecision]

    @property
    def may_request_command_authorization(self) -> bool:
        return self.status == 'ready_for_command_authorization'

    def audit_payload(self) -> dict:
        return {
            'status': self.status,
            'reason_code': self.reason_code,
            'correlation_id': self.context.correlation_id,
            'quest_id': self.context.quest_id,
            'objective_id': self.context.objective_id,
            'actor': {'id': self.context.actor.id, 'kind': self.context.actor.kind},
            'agent_node_id': self.context.agent_node_id,
            'command_line': self.context.command_line,
            'quest_state_version': self.context.quest_state_version,
            'objective_state_version': self.context.objective_state_version,
            'governance': {
                'decision': self.governance.decision,
                'reason_code': self.governance.reason_code,
                'projection_revision': self.governance.projection_revision,
                'rule_refs': list(self.governance.rule_refs),
                'capability_ref': self.governance.capability_ref,
            },
            'behavior': ({
                'decision': self.behavior.decision,
                'runtime_action': self.behavior.runtime_action,
                'check_point': self.behavior.check_point,
                'reason_code': self.behavior.reason_code,
                'evidence': self.behavior.evidence,
            } if self.behavior is not None else None),
            'command_authorization': 'required_at_execution',
        }


def compose_quest_decisions(*, context: QuestDecisionContext, governance: QuestGovernanceDecision,
                            behavior: Optional[PolicyDecision] = None) -> QuestDecisionComposition:
    """Compose independent results without evaluating or copying their rules.

    No command runs here. A runtime consumer must persist this result with its
    object references and re-enter command authorization at the execution point.
    """
    if not context.correlation_id.strip() or not context.command_line.strip():
        raise ValueError('Decision composition requires a correlation id and command')
    if context.quest_id <= 0 or context.objective_id <= 0:
        raise ValueError('Decision composition requires Quest and Objective references')
    pinned_rule_refs = context.pinned_rule_refs
    status: Literal['blocked', 'approval_required', 'ready_for_command_authorization'] = 'blocked'
    if governance.context != context:
        reason = 'governance_context_mismatch'
    elif not context.projection_revision or governance.projection_revision != context.projection_revision:
        reason = 'stale_governance'
    elif (not pinned_rule_refs or any(
            not namespace or not key or not version or version.lower() in {'latest', 'head', 'current'} or '*' in version
            for namespace, key, version in map(split_semantic_ref, pinned_rule_refs))
          or set(governance.rule_refs) != set(pinned_rule_refs)):
        reason = 'unresolved_governance_versions'
    elif governance.decision not in {'allow', 'deny', 'require_approval'} or not governance.reason_code:
        reason = 'invalid_governance_decision'
    elif governance.decision == 'deny':
        reason = governance.reason_code
    elif context.agent_node_id is not None and behavior is None:
        reason = 'missing_agent_behavior_decision'
    elif behavior is not None and (behavior.check_point != 'before_tool_call'
                                  or behavior.decision not in {'allow', 'deny', 'require_approval', 'allow_with_transform'}):
        reason = 'invalid_agent_behavior_decision'
    elif behavior is not None and behavior.decision == 'deny':
        reason = behavior.reason_code
    elif governance.decision == 'require_approval' or (behavior is not None and behavior.decision == 'require_approval'):
        status, reason = 'approval_required', 'approval_required'
    elif behavior is not None and (not behavior.is_allow or behavior.transform_applied is not None
                                  or behavior.decision == 'allow_with_transform'):
        reason = 'unsupported_agent_behavior_action'
    else:
        status, reason = 'ready_for_command_authorization', 'governance_and_behavior_pass'
    return QuestDecisionComposition(status, reason, context, governance, behavior)
