"""Observation / Situation / Goal / Quest semantic commands."""
from __future__ import annotations

from typing import Dict, List, Optional

from app.commands.base import CommandContext, CommandResult, GameCommand
from app.commands.command_tool_semantics import CommandToolSemantics, MUTATE_SUBCOMMAND, READ_SUBCOMMAND, build_error_schema
from app.services.task.errors import TaskSystemError
from app.services.task.permissions import TASK_CREATE, TASK_READ, TASK_UPDATE
from app.services.task.quest_interaction_service import (
    focus_objective,
    new_correlation_id,
    set_clue_pin,
    set_collaborator,
    track_quest,
    untrack_quest,
)
from app.services.task.quest_semantic_service import (
    create_goal,
    create_observation,
    create_quest,
    create_situation,
    list_nodes,
    show_node,
    show_quest,
)

from ._helpers import i18n, parse_argv, require_permission, resolve_principal_or_error, task_error_to_result, usage_result


def _csv_flag(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split(',') if part.strip()]


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_refs(values: List[str]) -> str:
    return ', '.join(values) if values else '-'


_SEMANTIC_COMMAND_PROFILES = (
    MUTATE_SUBCOMMAND('create'),
    MUTATE_SUBCOMMAND('record'),
    READ_SUBCOMMAND('list'),
    READ_SUBCOMMAND('show'),
)

_QUEST_COMMAND_PROFILES = _SEMANTIC_COMMAND_PROFILES + (
    MUTATE_SUBCOMMAND('track'),
    MUTATE_SUBCOMMAND('untrack'),
    MUTATE_SUBCOMMAND('focus-objective'),
    MUTATE_SUBCOMMAND('pin-clue'),
    MUTATE_SUBCOMMAND('unpin-clue'),
    MUTATE_SUBCOMMAND('set-collaborator'),
    MUTATE_SUBCOMMAND('remove-collaborator'),
)

_SEMANTIC_ERROR_SCHEMA = build_error_schema(('INVALID_PARAM', 'NOT_FOUND', 'PERMISSION_DENIED', 'POLICY_DENIED', 'CONFLICT'))


class ObservationCommand(GameCommand):
    """Command facade for immutable, source-bearing observations."""

    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        subcommand_profiles=_SEMANTIC_COMMAND_PROFILES,
        default_profile_when_no_subcommand='read',
        data_classification='internal',
        data_scope=('observation',),
        error_schema=_SEMANTIC_ERROR_SCHEMA,
    )

    def __init__(self) -> None:
        super().__init__(name='observation', description='Observation semantic nodes', aliases=['observations'], game_name='campusworld')

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(context, 'observation.usage.root', 'observation <record|list|show> [...]')
        sub = str(args[0]).lower()
        rest = args[1:]
        if sub in {'record', 'create'}:
            gate = require_permission(context, TASK_CREATE)
            return gate if gate is not None else self._do_create(context, rest)
        if sub == 'list':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_list(context, rest)
        if sub == 'show':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_show(context, rest)
        return CommandResult.error_result(i18n(context, 'error.invalid_event', default=f'unknown subcommand: {sub}', detail=sub), error='commands.task.error.invalid_event')

    def _do_create(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        assertion = parsed.flags.get('assertion')
        source_ref = parsed.flags.get('source-ref')
        observed_at = parsed.flags.get('observed-at')
        if not assertion or not source_ref or not observed_at:
            return usage_result(ctx, 'observation.usage.create', 'observation record --assertion <A> --source-ref <R> --observed-at <T> [--title <T>] [...]')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        subject_id = _parse_int(parsed.flags.get('subject'))
        if parsed.flags.get('subject') is not None and subject_id is None:
            return usage_result(ctx, 'observation.usage.create', 'observation record --assertion <A> --source-ref <R> --observed-at <T> [--title <T>] [...]')
        try:
            result = create_observation(
                title=parsed.flags.get('title') or assertion[:120],
                assertion=assertion,
                actor=actor,
                source_ref=source_ref,
                provenance={
                    'source_kind': str(parsed.flags.get('source-kind') or 'human'),
                    'capture_method': str(parsed.flags.get('capture-method') or 'command'),
                    **({'correlation_id': parsed.flags['correlation-id']} if parsed.flags.get('correlation-id') else {}),
                },
                observed_at=observed_at,
                subject_id=subject_id,
                db_session=ctx.db_session,
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'observation.create.success', default='Observation created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            items = list_nodes(type_code='observation', actor=actor, limit=int(parsed.flags.get('limit', '20')), db_session=ctx.db_session)
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'observation.usage.list', 'observation list [--limit N]')
        return _list_result(ctx, 'observation', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'observation.usage.show', 'observation show <id>')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            data = show_node(node_id=int(args[0]), type_code='observation', actor=actor, db_session=ctx.db_session)
        except ValueError:
            return usage_result(ctx, 'observation.usage.show', 'observation show <id>')
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        attrs = data['attributes']
        message = i18n(
            ctx,
            'observation.show.detail',
            default='Observation #{id}\n  assertion: {assertion}\n  verification_status: {verification_status}',
            id=data['id'],
            assertion=attrs.get('assertion'),
            verification_status=attrs.get('verification_status'),
        )
        return CommandResult.success_result(message, data=data)


class SituationCommand(GameCommand):
    """Command facade for declarative Situation assertions."""

    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        subcommand_profiles=_SEMANTIC_COMMAND_PROFILES,
        default_profile_when_no_subcommand='read',
        data_classification='internal',
        data_scope=('situation',),
        error_schema=_SEMANTIC_ERROR_SCHEMA,
    )

    def __init__(self) -> None:
        super().__init__(name='situation', description='Situation semantic assertions', aliases=['situations'], game_name='campusworld')

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(context, 'situation.usage.root', 'situation <create|list|show> [...]')
        sub = str(args[0]).lower()
        rest = args[1:]
        if sub == 'create':
            gate = require_permission(context, TASK_CREATE)
            return gate if gate is not None else self._do_create(context, rest)
        if sub == 'list':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_list(context, rest)
        if sub == 'show':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_show(context, rest)
        return CommandResult.error_result(i18n(context, 'error.invalid_event', default=f'unknown subcommand: {sub}', detail=sub), error='commands.task.error.invalid_event')

    def _do_create(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        title = parsed.flags.get('title')
        assertion = parsed.flags.get('assertion')
        if not title or not assertion:
            return usage_result(ctx, 'situation.usage.create', 'situation create --title <T> --assertion <A> [...]')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        subject_id = _parse_int(parsed.flags.get('subject'))
        if parsed.flags.get('subject') is not None and subject_id is None:
            return usage_result(ctx, 'situation.usage.create', 'situation create --title <T> --assertion <A> [...]')
        confidence = _parse_float(parsed.flags.get('confidence'))
        if parsed.flags.get('confidence') is not None and confidence is None:
            return usage_result(ctx, 'situation.usage.create', 'situation create --title <T> --assertion <A> [...]')
        try:
            result = create_situation(
                title=title,
                assertion=assertion,
                actor=actor,
                subject_id=subject_id,
                trigger_kind=parsed.flags.get('trigger-kind', 'manual'),
                trigger_summary=parsed.flags.get('trigger-summary'),
                fact_refs=_csv_flag(parsed.flags.get('fact-ref')),
                evidence_refs=_csv_flag(parsed.flags.get('evidence-ref')),
                rule_refs=_csv_flag(parsed.flags.get('rule-ref')),
                experience_refs=_csv_flag(parsed.flags.get('experience-ref')),
                inference_trace_summary=parsed.flags.get('inference-summary') or parsed.flags.get('inference-trace-summary'),
                confidence=confidence,
                severity=parsed.flags.get('severity', 'medium'),
                business_impact=parsed.flags.get('business-impact'),
                db_session=ctx.db_session,
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'situation.create.success', default='Situation created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            limit = int(parsed.flags.get('limit', '20'))
            items = list_nodes(type_code='situation', actor=actor, limit=limit, db_session=ctx.db_session)
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'situation.usage.list', 'situation list [--limit N]')
        return _list_result(ctx, 'situation', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'situation.usage.show', 'situation show <id>')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            data = show_node(node_id=int(args[0]), type_code='situation', actor=actor, db_session=ctx.db_session)
        except ValueError:
            return usage_result(ctx, 'situation.usage.show', 'situation show <id>')
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        attrs = data['attributes']
        lines = [
            i18n(ctx, 'situation.show.title', default='Situation #{id}', id=data['id']),
            f"  assertion      : {attrs.get('assertion')}",
            f"  trigger_kind   : {attrs.get('trigger_kind')}",
            f"  severity       : {attrs.get('severity')}",
        ]
        return CommandResult.success_result('\n'.join(lines), data=data)


class GoalCommand(GameCommand):
    """Command facade for business goals raised by Situations."""

    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        subcommand_profiles=_SEMANTIC_COMMAND_PROFILES,
        default_profile_when_no_subcommand='read',
        data_classification='internal',
        data_scope=('goal', 'situation'),
        error_schema=_SEMANTIC_ERROR_SCHEMA,
    )

    def __init__(self) -> None:
        super().__init__(name='goal', description='Goal semantic nodes', aliases=['goals'], game_name='campusworld')

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(context, 'goal.usage.root', 'goal <create|list|show> [...]')
        sub = str(args[0]).lower()
        rest = args[1:]
        if sub == 'create':
            gate = require_permission(context, TASK_CREATE)
            return gate if gate is not None else self._do_create(context, rest)
        if sub == 'list':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_list(context, rest)
        if sub == 'show':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_show(context, rest)
        return CommandResult.error_result(i18n(context, 'error.invalid_event', default=f'unknown subcommand: {sub}', detail=sub), error='commands.task.error.invalid_event')

    def _do_create(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        title = parsed.flags.get('title')
        situation_id = _parse_int(parsed.flags.get('situation'))
        desired_state = parsed.flags.get('desired-state')
        if not title or situation_id is None or not desired_state:
            return usage_result(ctx, 'goal.usage.create', 'goal create --title <T> --situation <id> --desired-state <state> [...]')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            result = create_goal(
                title=title,
                situation_id=situation_id,
                actor=actor,
                desired_state=desired_state,
                priority=parsed.flags.get('priority', 'normal'),
                deadline_at=parsed.flags.get('deadline-at'),
                acceptance_summary=parsed.flags.get('acceptance-summary'),
                db_session=ctx.db_session,
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'goal.create.success', default='Goal created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            items = list_nodes(type_code='goal', actor=actor, limit=int(parsed.flags.get('limit', '20')), db_session=ctx.db_session)
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'goal.usage.list', 'goal list [--limit N]')
        return _list_result(ctx, 'goal', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'goal.usage.show', 'goal show <id>')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            data = show_node(node_id=int(args[0]), type_code='goal', actor=actor, db_session=ctx.db_session)
        except ValueError:
            return usage_result(ctx, 'goal.usage.show', 'goal show <id>')
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        attrs = data['attributes']
        lines = [
            i18n(ctx, 'goal.show.title', default='Goal #{id}', id=data['id']),
            f"  desired_state  : {attrs.get('desired_state')}",
            f"  priority       : {attrs.get('priority')}",
            f"  situation_id   : {attrs.get('situation_id')}",
        ]
        return CommandResult.success_result('\n'.join(lines), data=data)


class QuestCommand(GameCommand):
    """Command facade for Quest containers and task objectives."""

    tool_semantics = CommandToolSemantics(
        interaction_profile='mutate',
        subcommand_profiles=_QUEST_COMMAND_PROFILES,
        default_profile_when_no_subcommand='read',
        data_classification='internal',
        data_scope=('quest', 'goal', 'situation', 'task'),
        error_schema=_SEMANTIC_ERROR_SCHEMA,
    )

    def __init__(self) -> None:
        super().__init__(name='quest', description='Quest semantic containers', aliases=['quests'], game_name='campusworld')

    def execute(self, context: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(context, 'quest.usage.root', 'quest <create|list|show> [...]')
        sub = str(args[0]).lower()
        rest = args[1:]
        if sub == 'create':
            gate = require_permission(context, TASK_CREATE)
            return gate if gate is not None else self._do_create(context, rest)
        if sub == 'list':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_list(context, rest)
        if sub == 'show':
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_show(context, rest)
        if sub in {'track', 'untrack', 'focus-objective', 'pin-clue', 'unpin-clue'}:
            gate = require_permission(context, TASK_READ)
            return gate if gate is not None else self._do_interaction(context, sub, rest)
        if sub in {'set-collaborator', 'remove-collaborator'}:
            gate = require_permission(context, TASK_UPDATE)
            return gate if gate is not None else self._do_interaction(context, sub, rest)
        return CommandResult.error_result(i18n(context, 'error.invalid_event', default=f'unknown subcommand: {sub}', detail=sub), error='commands.task.error.invalid_event')

    def _do_create(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        title = parsed.flags.get('title')
        situation_id = _parse_int(parsed.flags.get('situation'))
        goal_id = _parse_int(parsed.flags.get('goal'))
        if not title or situation_id is None or goal_id is None:
            return usage_result(ctx, 'quest.usage.create', 'quest create --situation <id> --goal <id> --title <T>')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            result = create_quest(
                title=title,
                situation_id=situation_id,
                goal_id=goal_id,
                actor=actor,
                risk_level=parsed.flags.get('risk-level', 'normal'),
                plan_graph_summary=parsed.flags.get('plan-graph-summary'),
                policy_refs=_csv_flag(parsed.flags.get('policy-ref')),
                process_refs=_csv_flag(parsed.flags.get('process-ref')),
                quality_refs=_csv_flag(parsed.flags.get('quality-ref')),
                case_refs=_csv_flag(parsed.flags.get('case-ref')),
                db_session=ctx.db_session,
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'quest.create.success', default='Quest created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            items = list_nodes(type_code='quest', actor=actor, limit=int(parsed.flags.get('limit', '20')), db_session=ctx.db_session)
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'quest.usage.list', 'quest list [--limit N]')
        return _list_result(ctx, 'quest', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'quest.usage.show', 'quest show <id>')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            data = show_quest(quest_id=int(args[0]), actor=actor, db_session=ctx.db_session)
        except ValueError:
            return usage_result(ctx, 'quest.usage.show', 'quest show <id>')
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        quest = data['quest']
        progress = data['progress']
        situation = data['situation']
        quest_attrs = quest.get('attributes') or {}
        lines = [
            i18n(ctx, 'quest.show.title', default='Quest #{id}', id=quest['id']),
            f"  situation      : #{situation['id']} {situation['assertion']}",
            f"  trigger_kind   : {situation.get('trigger_kind')}",
            f"  fact_refs      : {_format_refs(situation.get('fact_refs') or [])}",
            f"  evidence_refs  : {_format_refs(situation.get('evidence_refs') or [])}",
            f"  rule_refs      : {_format_refs(situation.get('rule_refs') or [])}",
            f"  experience_refs: {_format_refs(situation.get('experience_refs') or [])}",
            f"  goal           : #{data['goal']['id']} {data['goal']['title']}",
            f"  progress       : terminal={progress['terminal_objectives']}/{progress['total_objectives']} ({progress['percent']}%) succeeded={progress['completed_objectives']} ({progress['success_percent']}%)",
            f"  policy_refs    : {_format_refs(quest_attrs.get('policy_refs') or [])}",
            f"  process_refs   : {_format_refs(quest_attrs.get('process_refs') or [])}",
            f"  quality_refs   : {_format_refs(quest_attrs.get('quality_refs') or [])}",
            f"  case_refs      : {_format_refs(quest_attrs.get('case_refs') or [])}",
            "  objectives     :",
        ]
        objectives = data.get('objectives') or []
        if not objectives:
            lines.append('    -')
        for obj in objectives:
            caps = _format_refs(obj.get('required_capabilities') or [])
            kind = obj.get('objective_kind') or '-'
            lines.append(f"    #{obj['task_id']} state={obj.get('current_state') or '-'} kind={kind} caps={caps} title={obj.get('title') or '-'}")
        return CommandResult.success_result('\n'.join(lines), data=data)

    def _do_interaction(self, ctx: CommandContext, sub: str, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        expected_revision = parsed.flags.get('if-revision')
        idempotency_key = parsed.flags.get('idempotency-key')
        if not expected_revision or not idempotency_key:
            return usage_result(ctx, 'quest.usage.interaction', f'quest {sub} <ids...> --if-revision <R> --idempotency-key <K>')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        positionals = parsed.positional
        common = {
            'account_node_id': int(actor.id),
            'actor': actor,
            'expected_revision': expected_revision,
            'idempotency_key': idempotency_key,
            'correlation_id': parsed.flags.get('correlation-id') or new_correlation_id(),
            'db_session': ctx.db_session,
        }
        try:
            if sub in {'track', 'untrack'} and len(positionals) == 1:
                quest_id = int(positionals[0])
                result = track_quest(quest_id=quest_id, **common) if sub == 'track' else untrack_quest(quest_id=quest_id, **common)
            elif sub == 'focus-objective' and len(positionals) == 2:
                result = focus_objective(quest_id=int(positionals[0]), objective_id=int(positionals[1]), **common)
            elif sub in {'pin-clue', 'unpin-clue'} and len(positionals) == 2:
                result = set_clue_pin(
                    quest_id=int(positionals[0]),
                    clue_node_id=int(positionals[1]),
                    pinned=sub == 'pin-clue',
                    **common,
                )
            elif sub in {'set-collaborator', 'remove-collaborator'} and len(positionals) == 2:
                result = set_collaborator(
                    quest_id=int(positionals[0]),
                    agent_node_id=int(positionals[1]),
                    active=sub == 'set-collaborator',
                    role=parsed.flags.get('role', 'advisor'),
                    status=parsed.flags.get('status', 'active'),
                    is_primary_companion=parsed.flags.get('primary', 'false').lower() in {'1', 'true', 'yes'},
                    capability_scope=_csv_flag(parsed.flags.get('capability-scope')),
                    **common,
                )
            else:
                raise ValueError('invalid interaction arguments')
        except ValueError:
            return usage_result(ctx, 'quest.usage.interaction', f'quest {sub} <ids...> --if-revision <R> --idempotency-key <K>')
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        return CommandResult.success_result(
            i18n(ctx, 'quest.interaction.success', default='Quest interaction updated.'),
            data={
                'projection_revision': result.projection_revision,
                'last_event_id': result.last_event_id,
                'idempotent_replay': result.idempotent_replay,
                'changed': result.changed,
            },
        )


def _list_result(ctx: CommandContext, kind: str, items: List[Dict[str, Any]]) -> CommandResult:
    if not items:
        msg = i18n(ctx, f'{kind}.list.empty', default=f'No {kind}s match.')
    else:
        lines = [i18n(ctx, f'{kind}.list.header', default=f'{kind.title()} list (total={{total}})', total=len(items))]
        row_tmpl = i18n(ctx, f'{kind}.list.row', default='#{id}  title={title}')
        for item in items:
            lines.append(row_tmpl.format(id=item['id'], title=item['title']))
        msg = '\n'.join(lines)
    return CommandResult.success_result(msg, data={'items': items, 'total': len(items)})


__all__ = ['ObservationCommand', 'SituationCommand', 'GoalCommand', 'QuestCommand']
