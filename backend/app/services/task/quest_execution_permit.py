"""One-shot in-process proof of a freshly governed command invocation."""
from dataclasses import dataclass, field

from app.services.task.errors import PreconditionFailed
from app.services.task.quest_decision import QuestDecisionComposition

_ISSUER = object()


@dataclass
class QuestMutationPermit:
    decision: QuestDecisionComposition
    session: object = field(repr=False)
    event: str
    _issuer: object = field(default=None, repr=False)
    _used: bool = False

    def consume(self, *, session, quest_id, task_id, event, actor, state_version):
        context = self.decision.context
        if (self._issuer is not _ISSUER or self._used or self.session is not session
                or not self.decision.may_request_command_authorization
                or self.event != event or context.quest_id != quest_id
                or context.objective_id != task_id or context.actor != actor
                or context.objective_state_version != state_version):
            raise PreconditionFailed('Governed Quest mutation requires a fresh scoped execution permit')
        self._used = True


def _issue_mutation_permit(decision, session, event):
    if not decision.may_request_command_authorization or event not in {'claim', 'start', 'complete'}:
        raise PreconditionFailed('Quest execution is not permitted')
    return QuestMutationPermit(decision=decision, session=session, event=event, _issuer=_ISSUER)


def enforce_quest_mutation(session, *, attrs, task_id, event, actor, state_version, permit):
    quest_id = attrs.get('quest_id')
    if quest_id is None:
        return
    from app.services.task.task_state_machine import load_node_ref

    quest = load_node_ref(session, node_id=int(quest_id), expected_type_code='quest')
    if quest['attributes'].get('governance_mode') != 'enforced':
        if actor.kind == 'agent':
            raise PreconditionFailed('Agent Quest execution requires enforced governance')
        return
    if not isinstance(permit, QuestMutationPermit):
        raise PreconditionFailed('Use governed Quest execution for this Objective')
    if quest['attributes'].get('state_version') != permit.decision.context.quest_state_version:
        raise PreconditionFailed('Governed Quest state changed before the Objective mutation')
    permit.consume(session=session, quest_id=int(quest_id), task_id=task_id, event=event,
                   actor=actor, state_version=state_version)
