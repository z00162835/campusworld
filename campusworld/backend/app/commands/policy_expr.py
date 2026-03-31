"""
Evennia-inspired policy expression evaluation.

Supports a safe subset:
- perm(<permission_pattern>)
- role(<role_name>)
- all()
- AND / OR / NOT with parentheses

Examples:
    perm(admin.*) OR perm(admin.system_notice)
    role(admin) AND NOT perm(world.delete)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.core.permissions import permission_checker


class PolicyExprError(ValueError):
    pass


@dataclass
class _Token:
    kind: str
    value: str


def _strip_lockstring(expr: str) -> str:
    s = (expr or "").strip()
    if not s:
        return ""
    # Accept evennia-style 'cmd:...;' and take first clause.
    if ":" in s and s.split(":", 1)[0].isidentifier():
        s = s.split(":", 1)[1]
    if ";" in s:
        s = s.split(";", 1)[0]
    return s.strip()


def _tokenize(expr: str) -> List[_Token]:
    s = _strip_lockstring(expr)
    out: List[_Token] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "()":
            out.append(_Token(kind=ch, value=ch))
            i += 1
            continue
        if ch == ",":
            out.append(_Token(kind=",", value=","))
            i += 1
            continue
        # keyword/operator/identifier/arg chunk
        j = i
        while j < n and (not s[j].isspace()) and s[j] not in "(),":
            j += 1
        word = s[i:j]
        up = word.upper()
        if up in {"AND", "OR", "NOT"}:
            out.append(_Token(kind=up, value=up))
        else:
            out.append(_Token(kind="WORD", value=word))
        i = j
    return out


class _Parser:
    def __init__(self, tokens: List[_Token]):
        self.toks = tokens
        self.i = 0

    def _peek(self) -> Optional[_Token]:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def _eat(self, kind: str) -> _Token:
        tok = self._peek()
        if tok is None or tok.kind != kind:
            raise PolicyExprError(f"expected {kind}, got {tok.kind if tok else 'EOF'}")
        self.i += 1
        return tok

    def parse(self):
        node = self._parse_or()
        if self._peek() is not None:
            raise PolicyExprError("trailing tokens")
        return node

    # precedence: NOT > AND > OR
    def _parse_or(self):
        node = self._parse_and()
        while True:
            tok = self._peek()
            if tok and tok.kind == "OR":
                self._eat("OR")
                rhs = self._parse_and()
                node = ("OR", node, rhs)
                continue
            return node

    def _parse_and(self):
        node = self._parse_not()
        while True:
            tok = self._peek()
            if tok and tok.kind == "AND":
                self._eat("AND")
                rhs = self._parse_not()
                node = ("AND", node, rhs)
                continue
            return node

    def _parse_not(self):
        tok = self._peek()
        if tok and tok.kind == "NOT":
            self._eat("NOT")
            return ("NOT", self._parse_not())
        return self._parse_atom()

    def _parse_atom(self):
        tok = self._peek()
        if tok is None:
            raise PolicyExprError("unexpected EOF")
        if tok.kind == "(":
            self._eat("(")
            node = self._parse_or()
            self._eat(")")
            return node
        if tok.kind == "WORD":
            return self._parse_call()
        raise PolicyExprError(f"unexpected token {tok.kind}")

    def _parse_call(self):
        name = self._eat("WORD").value
        self._eat("(")
        args: List[str] = []
        tok = self._peek()
        if tok and tok.kind == ")":
            self._eat(")")
            return ("CALL", name, args)
        while True:
            arg_tok = self._eat("WORD")
            args.append(arg_tok.value)
            tok = self._peek()
            if tok and tok.kind == ",":
                self._eat(",")
                continue
            break
        self._eat(")")
        return ("CALL", name, args)


def evaluate_policy_expr(expr: str, *, user_permissions: List[str], user_roles: List[str]) -> bool:
    """
    Evaluate expression. Raises PolicyExprError on parse/eval problems.
    """
    tokens = _tokenize(expr)
    if not tokens:
        raise PolicyExprError("empty expr")
    ast = _Parser(tokens).parse()

    def _eval(node) -> bool:
        op = node[0]
        if op == "OR":
            return _eval(node[1]) or _eval(node[2])
        if op == "AND":
            return _eval(node[1]) and _eval(node[2])
        if op == "NOT":
            return not _eval(node[1])
        if op == "CALL":
            name, args = node[1], node[2]
            lname = str(name).lower()
            if lname == "all":
                return True
            if lname == "perm":
                if not args:
                    return False
                return permission_checker.check_permission(user_permissions, str(args[0]))
            if lname == "role":
                if not args:
                    return False
                return permission_checker.check_role(user_roles, str(args[0]))
            raise PolicyExprError(f"unknown func: {name}")
        raise PolicyExprError(f"bad node: {op}")

    return bool(_eval(ast))

