"""Task system exception hierarchy.

SSOT: ``docs/command/SPEC/features/CMD_task.md §C`` (i18n key catalog).

These exceptions are raised by the state machine, ACL evaluator, selector
validator and BLOCKED_BY cycle detector. The command layer translates each
class to a stable i18n key so that wire-protocol responses remain consistent
across SSH and ``POST /api/v1/command/execute``.
"""

from __future__ import annotations


class TaskSystemError(Exception):
    """Base class for all task-system domain errors."""

    i18n_key: str = "commands.task.error.generic"


# --- Workflow / state machine -------------------------------------------------


class WorkflowEventNotAllowed(TaskSystemError):
    i18n_key = "commands.task.error.invalid_event"


class WorkflowDefinitionNotFound(TaskSystemError):
    i18n_key = "commands.task.error.workflow_not_found"


class WorkflowDefinitionInactive(TaskSystemError):
    i18n_key = "commands.task.error.workflow_inactive"


class OptimisticLockError(TaskSystemError):
    i18n_key = "commands.task.error.version_stale"


class RoleRequiredError(TaskSystemError):
    i18n_key = "commands.task.error.role_required"


class PreconditionFailed(TaskSystemError):
    i18n_key = "commands.task.error.precondition_failed"


class AlreadyClaimedError(TaskSystemError):
    i18n_key = "commands.task.error.already_claimed"


class ChildrenNotTerminalError(TaskSystemError):
    i18n_key = "commands.task.error.children_not_terminal"


# --- Pool / ACL ---------------------------------------------------------------


class PoolNotFound(TaskSystemError):
    i18n_key = "commands.task.error.pool_not_found"


class PoolInactive(TaskSystemError):
    i18n_key = "commands.task.error.pool_inactive"


class PublishAclDenied(TaskSystemError):
    i18n_key = "commands.task.error.publish_denied"


class ConsumeAclDenied(TaskSystemError):
    i18n_key = "commands.task.error.consume_denied"


# --- Selector / blocked-by ----------------------------------------------------


class SelectorBoundsExceeded(TaskSystemError):
    i18n_key = "commands.task.error.selector_bounds_exceeded"

    def __init__(self, *, reason: str, count: int, limit: int):
        super().__init__(f"selector bounds exceeded: {reason} count={count} limit={limit}")
        self.reason = reason
        self.count = count
        self.limit = limit


class UnknownTraitMaskName(TaskSystemError):
    i18n_key = "commands.task.error.unknown_trait_mask"


class UnknownTraitClass(TaskSystemError):
    i18n_key = "commands.task.error.unknown_trait_class"


class EmptySelector(TaskSystemError):
    i18n_key = "commands.task.error.empty_selector"


class CycleDetected(TaskSystemError):
    i18n_key = "commands.task.error.cycle_detected"


# --- Permission ---------------------------------------------------------------


class PermissionDenied(TaskSystemError):
    i18n_key = "commands.task.error.forbidden"


class UnauthenticatedActor(TaskSystemError):
    """Raised when the command layer cannot resolve a numeric principal id.

    Production traffic always carries a stringified ``users.id`` integer in
    ``CommandContext.user_id``. UUID/empty/non-numeric values mean the actor
    has not been authenticated through the account system; we MUST refuse to
    fall back to ``system`` (which would bypass all role checks).
    """

    i18n_key = "commands.task.error.unauthenticated"


__all__ = [
    "TaskSystemError",
    "WorkflowEventNotAllowed",
    "WorkflowDefinitionNotFound",
    "WorkflowDefinitionInactive",
    "OptimisticLockError",
    "RoleRequiredError",
    "PreconditionFailed",
    "AlreadyClaimedError",
    "ChildrenNotTerminalError",
    "PoolNotFound",
    "PoolInactive",
    "PublishAclDenied",
    "ConsumeAclDenied",
    "SelectorBoundsExceeded",
    "UnknownTraitMaskName",
    "UnknownTraitClass",
    "EmptySelector",
    "CycleDetected",
    "PermissionDenied",
    "UnauthenticatedActor",
]
