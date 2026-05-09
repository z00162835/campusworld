"""Optional argv normalization for shell-like short-option clusters (command-specific)."""

from __future__ import annotations

from typing import List, Optional

# Tokens that must never be split into single-letter flags (multi-char subcommands).
_AICO_CLUSTER_BLOCKLIST_EXACT = frozenset({"-his", "-cd", "-nd"})
_AICO_CLUSTER_SPLITTABLE = frozenset({"l", "a"})


def expand_aico_argv(args: List[str]) -> List[str]:
    """Expand POSIX-style combined short flags for ``aico`` where safe.

    Currently: ``-la`` / ``-al`` / ``-ll`` where every letter after ``-`` is only
    ``l`` or ``a`` becomes ``-l`` then ``-a`` (deduped per letter). Does **not**
    touch ``-his``, ``-cd``, ``-nd``, ``-i…``, or tokens with letters outside ``{l,a}``.
    """
    out: List[str] = []
    for tok in args:
        expanded = _try_expand_aico_cluster(tok)
        if expanded is not None:
            out.extend(expanded)
        else:
            out.append(tok)
    return out


def _try_expand_aico_cluster(tok: str) -> Optional[List[str]]:
    if len(tok) < 3 or not tok.startswith("-") or tok.startswith("--"):
        return None
    if tok in _AICO_CLUSTER_BLOCKLIST_EXACT:
        return None
    if tok.startswith("-i"):
        return None
    body = tok[1:]
    if not body.isascii() or not body.isalpha() or not body.islower():
        return None
    if not all(c in _AICO_CLUSTER_SPLITTABLE for c in body):
        return None
    flags: List[str] = []
    if "l" in body:
        flags.append("-l")
    if "a" in body:
        flags.append("-a")
    return flags if flags else None
