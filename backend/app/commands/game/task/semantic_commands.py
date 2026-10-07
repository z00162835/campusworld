"""Situation / Goal / Quest commands for the R1 semantic shell."""
from __future__ import annotations

from typing import Dict, List, Optional

from app.commands.base import CommandContext, CommandResult, GameCommand
from app.services.task.errors import TaskSystemError
from app.services.task.permissions import TASK_CREATE, TASK_READ
from app.services.task.quest_semantic_service import (
    create_goal,
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


class SituationCommand(GameCommand):
    """Command facade for declarative Situation assertions."""

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
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'situation.create.success', default='Situation created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        try:
            limit = int(parsed.flags.get('limit', '20'))
            items = list_nodes(type_code='situation', limit=limit)
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'situation.usage.list', 'situation list [--limit N]')
        return _list_result(ctx, 'situation', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'situation.usage.show', 'situation show <id>')
        try:
            data = show_node(node_id=int(args[0]), type_code='situation')
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
        if not title or situation_id is None:
            return usage_result(ctx, 'goal.usage.create', 'goal create --title <T> --situation <id> [...]')
        actor, err = resolve_principal_or_error(ctx)
        if err is not None:
            return err
        try:
            result = create_goal(
                title=title,
                situation_id=situation_id,
                actor=actor,
                desired_state=parsed.flags.get('desired-state'),
                priority=parsed.flags.get('priority', 'normal'),
                deadline_at=parsed.flags.get('deadline-at'),
                acceptance_summary=parsed.flags.get('acceptance-summary'),
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'goal.create.success', default='Goal created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        try:
            items = list_nodes(type_code='goal', limit=int(parsed.flags.get('limit', '20')))
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'goal.usage.list', 'goal list [--limit N]')
        return _list_result(ctx, 'goal', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'goal.usage.show', 'goal show <id>')
        try:
            data = show_node(node_id=int(args[0]), type_code='goal')
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
            )
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        msg = i18n(ctx, 'quest.create.success', default='Quest created: #{id}', id=result.node_id)
        return CommandResult.success_result(msg, data={'id': result.node_id, 'type_code': result.type_code, 'attributes': result.attributes})

    def _do_list(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        parsed = parse_argv(args)
        try:
            items = list_nodes(type_code='quest', limit=int(parsed.flags.get('limit', '20')))
        except (ValueError, TaskSystemError) as exc:
            if isinstance(exc, TaskSystemError):
                return task_error_to_result(ctx, exc)
            return usage_result(ctx, 'quest.usage.list', 'quest list [--limit N]')
        return _list_result(ctx, 'quest', items)

    def _do_show(self, ctx: CommandContext, args: List[str]) -> CommandResult:
        if not args:
            return usage_result(ctx, 'quest.usage.show', 'quest show <id>')
        try:
            data = show_quest(quest_id=int(args[0]))
        except ValueError:
            return usage_result(ctx, 'quest.usage.show', 'quest show <id>')
        except TaskSystemError as exc:
            return task_error_to_result(ctx, exc)
        quest = data['quest']
        progress = data['progress']
        lines = [
            i18n(ctx, 'quest.show.title', default='Quest #{id}', id=quest['id']),
            f"  situation      : #{data['situation']['id']} {data['situation']['assertion']}",
            f"  goal           : #{data['goal']['id']} {data['goal']['title']}",
            f"  progress       : {progress['completed_objectives']}/{progress['total_objectives']} ({progress['percent']}%)",
        ]
        return CommandResult.success_result('\n'.join(lines), data=data)


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


__all__ = ['SituationCommand', 'GoalCommand', 'QuestCommand']
