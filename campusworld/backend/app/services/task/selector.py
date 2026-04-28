"""Scope-selector DSL validator (Phase B).

SSOT: ``docs/task/SPEC/features/F01_TASK_ONTOLOGY_AND_NODE_TYPES.md §4``.

Phase B scope is **validation only**. Full late-binding SQL translation,
descendants_of_anchor recursion and result-set freeze (``§4.2`` / ``§4.4.4``)
are deferred to Phase C; the validator however already enforces:

- ``_schema_version`` defaulting (``1``) and JSON schema shape
- ``bounds`` shape and resolved-count guards (callers pass ``actual_count``
  to :func:`enforce_bounds`)
- ``trait_class`` whitelist
- ``trait_mask_*`` names must be exposed by ``app.constants.trait_mask``
- ``include`` non-empty unless ``TARGETS_PINNED`` edges exist (caller supplies
  ``allow_empty_include``)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from app.services.task.errors import (
    EmptySelector,
    SelectorBoundsExceeded,
    UnknownTraitClass,
    UnknownTraitMaskName,
)


# Whitelist of trait_class strings used elsewhere in the YAML overlays.
# Centralised here to keep the selector guard close to the SPEC text.
_KNOWN_TRAIT_CLASSES: Set[str] = {
    "DEVICE",
    "SPACE",
    "AGENT",
    "ENV",
    "TASK",
    "ITEM",
    "PROCESS",
    "ABSTRACT",
}


def _known_trait_mask_names() -> Set[str]:
    """Return the set of upper-case constants exposed by ``trait_mask`` module."""
    from app.constants import trait_mask as tm

    return {
        name
        for name in dir(tm)
        if not name.startswith("_") and name.isupper() and isinstance(getattr(tm, name), int)
    }


@dataclass
class ValidatedSelector:
    """Validated selector DSL.

    Phase B keeps the original dict unchanged and returns metadata derived
    during validation for the state machine to act on; Phase C will materialise
    a SQL-translatable representation.
    """

    raw: Dict[str, Any]
    schema_version: int
    anchor_ref: Optional[int]
    bounds: Dict[str, int]
    include: List[Dict[str, Any]] = field(default_factory=list)
    exclude: List[Dict[str, Any]] = field(default_factory=list)


_DEFAULT_BOUNDS = {"min": 0, "max": 10000}


def validate_selector(
    dsl: Optional[Dict[str, Any]],
    *,
    allow_empty_include: bool = False,
) -> ValidatedSelector:
    """Validate the selector DSL.

    ``allow_empty_include=True`` is used by callers that already added
    ``TARGETS_PINNED`` edges (F01 §4.3); otherwise an empty include set raises
    :class:`EmptySelector`.
    """

    if not isinstance(dsl, dict):
        raise EmptySelector("selector must be a JSON object")

    schema_version = int(dsl.get("_schema_version", 1) or 1)
    if schema_version != 1:
        raise EmptySelector(f"unsupported _schema_version: {schema_version}")

    anchor_ref = dsl.get("anchor_ref")
    if anchor_ref is not None:
        try:
            anchor_ref = int(anchor_ref)
        except (TypeError, ValueError) as exc:
            raise EmptySelector("anchor_ref must be int") from exc

    bounds = dict(_DEFAULT_BOUNDS)
    bnd = dsl.get("bounds")
    if isinstance(bnd, dict):
        for key in ("min", "max"):
            if key in bnd:
                try:
                    bounds[key] = int(bnd[key])
                except (TypeError, ValueError) as exc:
                    raise EmptySelector(f"bounds.{key} must be int") from exc
    if bounds["min"] < 0:
        raise EmptySelector("bounds.min must be >= 0")
    if bounds["max"] < 1:
        raise EmptySelector("bounds.max must be >= 1")
    if bounds["min"] > bounds["max"]:
        raise EmptySelector("bounds.min must be <= bounds.max")

    include = list(dsl.get("include") or [])
    exclude = list(dsl.get("exclude") or [])

    if not include and not allow_empty_include:
        raise EmptySelector(
            "selector.include must contain at least one clause "
            "(or supply TARGETS_PINNED edges and pass allow_empty_include=True)"
        )

    known_masks = _known_trait_mask_names()
    for clause_list, label in ((include, "include"), (exclude, "exclude")):
        for idx, clause in enumerate(clause_list):
            _validate_clause(clause, known_masks, where=f"{label}[{idx}]")

    return ValidatedSelector(
        raw=dict(dsl),
        schema_version=schema_version,
        anchor_ref=anchor_ref,
        bounds=bounds,
        include=include,
        exclude=exclude,
    )


def _validate_clause(clause: Any, known_masks: Set[str], *, where: str) -> None:
    if not isinstance(clause, dict):
        raise EmptySelector(f"{where} must be an object")

    trait_class = clause.get("trait_class")
    if trait_class is not None:
        if not isinstance(trait_class, str):
            raise UnknownTraitClass(f"{where}.trait_class must be string")
        if trait_class not in _KNOWN_TRAIT_CLASSES:
            raise UnknownTraitClass(f"{where}.trait_class={trait_class!r} is not registered")

    for mask_field in ("trait_mask_any_of", "trait_mask_all_of"):
        names = clause.get(mask_field)
        if names is None:
            continue
        if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
            raise UnknownTraitMaskName(f"{where}.{mask_field} must be list[str]")
        for name in names:
            if name not in known_masks:
                raise UnknownTraitMaskName(
                    f"{where}.{mask_field} contains unknown trait_mask name {name!r}"
                )


def enforce_bounds(validated: ValidatedSelector, *, actual_count: int) -> None:
    """Raise :class:`SelectorBoundsExceeded` when resolved size is out of bounds."""
    if actual_count < validated.bounds["min"]:
        raise SelectorBoundsExceeded(
            reason="min",
            count=actual_count,
            limit=validated.bounds["min"],
        )
    if actual_count > validated.bounds["max"]:
        raise SelectorBoundsExceeded(
            reason="max",
            count=actual_count,
            limit=validated.bounds["max"],
        )


__all__ = [
    "ValidatedSelector",
    "validate_selector",
    "enforce_bounds",
]
