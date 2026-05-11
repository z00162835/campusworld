#!/usr/bin/env python3
"""Rewrite Chinese string fragments inside logger calls to English using logger_fragment_en.json."""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


LOG_METHODS = frozenset({"debug", "info", "warning", "error", "critical", "exception"})


def _name_like_logger(ident: str) -> bool:
    return ident == "logger" or ident.endswith("_logger") or ident in ("log", "_log")


def _is_logging_get_logger_call(value: ast.expr) -> bool:
    """True for ``logging.getLogger(...)``."""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "logging"
        and func.attr == "getLogger"
    )


def is_logger_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in LOG_METHODS:
        return False
    v = node.func.value
    if isinstance(v, ast.Name):
        return _name_like_logger(v.id)
    if isinstance(v, ast.Attribute):
        return v.attr == "logger" or _name_like_logger(v.attr)
    if _is_logging_get_logger_call(v):
        return True
    return False


def rewrite_fragment(expr: ast.expr, mapping: dict[str, str]) -> ast.expr:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        new_val = mapping.get(expr.value, expr.value)
        if new_val != expr.value:
            return ast.Constant(value=new_val)
        return expr
    if isinstance(expr, ast.JoinedStr):
        new_values: list[ast.expr] = []
        for part in expr.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                nv = mapping.get(part.value, part.value)
                new_values.append(ast.Constant(value=nv))
            elif isinstance(part, ast.FormattedValue):
                new_values.append(
                    ast.FormattedValue(
                        value=rewrite_fragment(part.value, mapping),
                        conversion=part.conversion,
                        format_spec=part.format_spec,
                    )
                )
            else:
                new_values.append(part)
        return ast.JoinedStr(values=new_values)
    return expr


def rewrite_logger_call(node: ast.Call, mapping: dict[str, str]) -> ast.Call:
    new_args = [rewrite_fragment(a, mapping) for a in node.args]
    new_keywords = []
    for kw in node.keywords:
        new_keywords.append(ast.keyword(arg=kw.arg, value=rewrite_fragment(kw.value, mapping)))
    return ast.Call(func=node.func, args=new_args, keywords=new_keywords)


class _Rewrite(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = mapping

    def visit_Call(self, node: ast.Call) -> ast.Call:
        node = self.generic_visit(node)
        if is_logger_call(node):
            return rewrite_logger_call(node, self.mapping)
        return node


def rewrite_source(src: str, mapping: dict[str, str]) -> str:
    tree = ast.parse(src)
    new_tree = _Rewrite(mapping).visit(tree)
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree) + "\n"


def iter_py_files(root: Path) -> list[Path]:
    files = [root / "campusworld.py"]
    files.extend(sorted((root / "app").rglob("*.py")))
    return files


def main(argv: list[str]) -> int:
    backend_root = Path(__file__).resolve().parents[1]
    scripts = Path(__file__).resolve().parent
    mapping_path = scripts / "logger_fragment_en.json"
    mapping: dict[str, str] = json.loads(mapping_path.read_text(encoding="utf-8"))

    roots = [backend_root]
    if argv[1:]:
        roots = [Path(p).resolve() for p in argv[1:]]

    changed = 0
    for root in roots:
        for path in iter_py_files(root if root.name == "backend" else root):
            if not path.is_file():
                continue
            try:
                src = path.read_text(encoding="utf-8")
            except OSError:
                continue
            try:
                new_src = rewrite_source(src, mapping)
            except SyntaxError as e:
                print(f"SKIP syntax {path}: {e}", file=sys.stderr)
                continue
            if new_src != src:
                path.write_text(new_src, encoding="utf-8")
                changed += 1
                print(path)
    print(f"rewrote_files={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
