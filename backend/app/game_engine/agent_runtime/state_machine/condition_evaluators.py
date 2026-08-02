"""Minimal expression grammar for state-machine transition ``when`` clauses."""
from __future__ import annotations

import ast
import operator
from typing import TYPE_CHECKING, Any, Mapping, Optional

if TYPE_CHECKING:
    from app.game_engine.agent_runtime.state_machine.state_machine import (
        StateMachine,
        StateMachineSnapshot,
        TransitionContext,
    )

_BINOPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def resolve_field(
    path: str,
    snapshot: "StateMachineSnapshot",
    runtime: Mapping[str, Any],
    sm: "StateMachine",
) -> Any:
    """Resolve ``state.*`` / ``runtime.*`` / ``sm.*`` field paths."""
    if path.startswith("state."):
        key = path[6:]
        if key == "replan_count":
            return snapshot.replan_count
        if key == "turn_count":
            return snapshot.turn_count
        if key == "current_state":
            return snapshot.current_state
        if key == "last_event":
            return snapshot.last_event
        return None
    if path.startswith("runtime."):
        return runtime.get(path[8:])
    if path.startswith("sm."):
        key = path[3:]
        if key == "max_replans":
            return sm.max_replans
        return None
    if path in runtime:
        return runtime[path]
    if hasattr(snapshot, path):
        return getattr(snapshot, path)
    return None


def _eval_node(
    node: ast.AST,
    snapshot: "StateMachineSnapshot",
    runtime: Mapping[str, Any],
    sm: "StateMachine",
) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, snapshot, runtime, sm)
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, snapshot, runtime, sm) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, snapshot, runtime, sm) for v in node.values)
        raise ValueError(f"unsupported boolop: {type(node.op).__name__}")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, snapshot, runtime, sm)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, snapshot, runtime, sm)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, snapshot, runtime, sm)
            fn = _BINOPS.get(type(op))
            if fn is None:
                raise ValueError(f"unsupported compare: {type(op).__name__}")
            if not fn(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return resolve_field(node.id, snapshot, runtime, sm)
    if isinstance(node, ast.Attribute):
        parts = []
        cur: ast.AST = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
            path = ".".join(reversed(parts))
            return resolve_field(path, snapshot, runtime, sm)
        raise ValueError("unsupported attribute chain")
    if isinstance(node, ast.List):
        return [_eval_node(e, snapshot, runtime, sm) for e in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(e, snapshot, runtime, sm) for e in node.elts)
    raise ValueError(f"unsupported expression node: {type(node).__name__}")


def evaluate_when(expr: Optional[str], ctx: "TransitionContext", sm: "StateMachine") -> bool:
    """Evaluate a transition ``when`` expression. Empty/None means always true.

    v1 grammar: ``field op literal`` with ``op`` in ``== != < > <= >= in``,
    composed with ``and`` / ``or`` / ``not``. Paths: ``state.*``, ``runtime.*``,
    ``sm.*``. Does not support ``${skill.*}``.
    """
    if expr is None or not str(expr).strip():
        return True
    tree = ast.parse(str(expr).strip(), mode="eval")
    return bool(_eval_node(tree, ctx.snapshot, ctx.runtime or {}, sm))
