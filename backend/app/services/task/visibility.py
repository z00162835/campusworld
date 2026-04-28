"""Task visibility constants (Phase B subset).

SSOT: ``docs/task/SPEC/SPEC.md §1.5``.

Phase B supports three visibility kinds:

* ``private``     — only principals with an active assignment can see the task.
* ``explicit``    — anyone ever assigned (active or released) can see it.
* ``pool_open``   — the task is in a public pool slot (state ∈ {open, rejected})
                    and the actor passes the pool's ``consume_acl``.

``role_scope`` and ``world_scope`` will be enabled in Phase C once the F11
data-access predicate is wired (see ``F11_DATA_ACCESS_POLICY.md``). Until then
the command layer rejects them at write time and excludes them from the
visibility predicate at read time. This is **not** a silent deny: callers
hitting these visibility kinds receive
``commands.task.error.visibility_unsupported``.
"""

from __future__ import annotations

from typing import FrozenSet


PHASE_B_SUPPORTED_VISIBILITIES: FrozenSet[str] = frozenset(
    {"private", "explicit", "pool_open"}
)


PHASE_B_DEFERRED_VISIBILITIES: FrozenSet[str] = frozenset(
    {"role_scope", "world_scope"}
)


ALL_VISIBILITIES: FrozenSet[str] = (
    PHASE_B_SUPPORTED_VISIBILITIES | PHASE_B_DEFERRED_VISIBILITIES
)


def is_phase_b_supported(visibility: str) -> bool:
    """Return ``True`` iff ``visibility`` is enabled in Phase B."""
    return visibility in PHASE_B_SUPPORTED_VISIBILITIES


__all__ = [
    "PHASE_B_SUPPORTED_VISIBILITIES",
    "PHASE_B_DEFERRED_VISIBILITIES",
    "ALL_VISIBILITIES",
    "is_phase_b_supported",
]
