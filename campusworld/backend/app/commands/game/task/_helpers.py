"""Shared helpers for the ``task`` command family.

Keeps each subcommand body small; concentrates argv parsing, principal
construction, exception → i18n key mapping and idempotency-key derivation.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.commands.base import CommandContext, CommandResult
from app.commands.i18n.command_resource import get_command_i18n_text
from app.services.task.errors import TaskSystemError, UnauthenticatedActor
from app.services.task.permissions import Principal


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# argv parsing — minimal, no external deps.
# ---------------------------------------------------------------------------


@dataclass
class ParsedArgv:
    positional: List[str]
    flags: Dict[str, str]
    bools: set


def parse_argv(args: List[str], *, bool_flags: Optional[set] = None) -> ParsedArgv:
    """Tiny ``--flag value`` / ``--bool`` parser.

    Long flags only (``--flag``); single-dash flags are treated as positionals.
    Unrecognised tokens are kept positional so command bodies can validate.
    """
    bool_flags = bool_flags or set()
    positional: List[str] = []
    flags: Dict[str, str] = {}
    bools: set = set()
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("--"):
            name = tok[2:]
            if name in bool_flags:
                bools.add(name)
                i += 1
                continue
            if i + 1 >= len(args):
                # treat as bool fallback to avoid eating next positional erroneously
                bools.add(name)
                i += 1
                continue
            flags[name] = args[i + 1]
            i += 2
        else:
            positional.append(tok)
            i += 1
    return ParsedArgv(positional=positional, flags=flags, bools=bools)


# ---------------------------------------------------------------------------
# Principal extraction from CommandContext.
# ---------------------------------------------------------------------------


def principal_from_context(ctx: CommandContext) -> Principal:
    """Resolve the calling user into a strict ``user`` principal.

    Production traffic always carries a stringified ``users.id`` integer in
    ``CommandContext.user_id`` (see ``app/ssh/console.py`` and
    ``app/protocols/base.py``). Anything that fails ``int(...)`` coercion —
    e.g. UUID strings used by tests, ``"guest"`` from unauthenticated SSH
    connections, ``None``, empty strings — is treated as **unauthenticated**
    and raises :class:`UnauthenticatedActor`.

    Internal services that genuinely need the privileged ``system`` actor
    must construct :class:`Principal` (or use :data:`SYSTEM_PRINCIPAL`)
    explicitly; they never go through this helper.
    """
    raw_id = ctx.user_id
    if raw_id is None or raw_id == "" or str(raw_id).lower() == "guest":
        raise UnauthenticatedActor(
            f"command actor is unauthenticated (user_id={raw_id!r}); "
            "cannot construct task principal"
        )
    try:
        actor_id = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise UnauthenticatedActor(
            f"command actor user_id={raw_id!r} is not a numeric account id; "
            "task system requires an authenticated user principal"
        ) from exc
    if actor_id <= 0:
        raise UnauthenticatedActor(
            f"command actor user_id={actor_id} is not a valid account id"
        )
    return Principal(
        id=actor_id,
        kind="user",
        roles=frozenset(ctx.roles or []),
        permissions=frozenset(ctx.permissions or []),
    )


def resolve_principal_or_error(
    ctx: CommandContext,
) -> Tuple[Optional[Principal], Optional[CommandResult]]:
    """Return ``(principal, None)`` on success or ``(None, error_result)``.

    Subcommand handlers should call this **first** and bail out on the
    error path; this guarantees no code path ever silently downgrades to
    a privileged actor.
    """
    try:
        return principal_from_context(ctx), None
    except UnauthenticatedActor as exc:
        return None, task_error_to_result(ctx, exc)


# ---------------------------------------------------------------------------
# Idempotency key derivation (deterministic for the same invocation).
# ---------------------------------------------------------------------------


def derive_idempotency_key(
    *,
    actor: Principal,
    command_name: str,
    args: List[str],
    correlation_id: Optional[str],
) -> str:
    payload = f"{actor.kind}:{actor.id}|{command_name}|{'/'.join(args)}|{correlation_id or ''}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# i18n helpers.
# ---------------------------------------------------------------------------


def _resolve_locale(ctx: CommandContext) -> str:
    md = ctx.metadata or {}
    loc = md.get("locale") or md.get("language")
    if not loc:
        return "zh-CN"
    return str(loc)


def i18n(ctx: CommandContext, key_path: str, default: str = "", **fmt: Any) -> str:
    """Render ``commands.task.<key_path>`` for the caller's locale."""
    locale = _resolve_locale(ctx)
    raw = get_command_i18n_text("task", key_path, locale, default)
    try:
        return raw.format(**fmt) if fmt else raw
    except KeyError:
        return raw


# ---------------------------------------------------------------------------
# Exception translation: TaskSystemError → CommandResult.error_result.
# ---------------------------------------------------------------------------


def _i18n_key_to_path(i18n_key: str) -> str:
    """Strip the ``commands.task.`` prefix from a fully-qualified key."""
    prefix = "commands.task."
    if i18n_key.startswith(prefix):
        return i18n_key[len(prefix):]
    return i18n_key


def task_error_to_result(ctx: CommandContext, exc: TaskSystemError) -> CommandResult:
    fallback = "commands.task.error.generic"
    raw_code = getattr(exc, "i18n_key", fallback)
    code = raw_code if isinstance(raw_code, str) and raw_code else fallback
    key = _i18n_key_to_path(code)
    detail = str(exc)
    msg = i18n(ctx, key, default=detail, detail=detail)
    return CommandResult.error_result(msg, error=code)


def usage_result(ctx: CommandContext, key_path: str, fallback: str) -> CommandResult:
    return CommandResult.usage_result(i18n(ctx, key_path, default=fallback))


# ---------------------------------------------------------------------------
# Permission gate.
# ---------------------------------------------------------------------------


def require_permission(ctx: CommandContext, code: str) -> Optional[CommandResult]:
    """Return an error CommandResult if ``ctx`` lacks ``code``; else ``None``."""
    if ctx.has_permission(code):
        return None
    # Wildcard / role escalation (admin.*, *) handled by permission_checker.
    from app.core.permissions import permission_checker

    if permission_checker.check_permission(ctx.permissions or [], code):
        return None
    msg = i18n(
        ctx,
        "error.forbidden",
        default=f"Permission denied: {code}",
        detail=code,
    )
    return CommandResult.error_result(msg, error="commands.task.error.forbidden")


def correlation_id_from_context(ctx: CommandContext) -> Optional[str]:
    md = ctx.metadata or {}
    cid = md.get("correlation_id")
    return str(cid) if cid else None


def trace_id_from_context(ctx: CommandContext) -> Optional[str]:
    md = ctx.metadata or {}
    tid = md.get("trace_id")
    return str(tid) if tid else None


__all__ = [
    "ParsedArgv",
    "parse_argv",
    "principal_from_context",
    "resolve_principal_or_error",
    "derive_idempotency_key",
    "i18n",
    "task_error_to_result",
    "usage_result",
    "require_permission",
    "correlation_id_from_context",
    "trace_id_from_context",
]
