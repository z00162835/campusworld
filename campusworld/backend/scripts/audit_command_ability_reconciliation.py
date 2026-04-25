#!/usr/bin/env python3
"""
Compare registered commands with ``type_code=system_command_ability`` graph nodes (by ``command_name``).

Exit 0 if sets match. Exit 1 on mismatch (and print only-in- registry / only-in-graph). Requires DB.

  cd backend && python scripts/audit_command_ability_reconciliation.py
"""
from __future__ import annotations

import sys
from typing import Set

from sqlalchemy import and_


def _main() -> int:
    from app.commands.init_commands import initialize_commands
    from app.commands.registry import command_registry
    from app.core.database import db_session_context
    from app.models.graph import Node

    initialize_commands()
    reg: Set[str] = {c.name for c in command_registry.get_all_commands()}

    with db_session_context() as session:
        rows = (
            session.query(Node)
            .filter(
                and_(
                    Node.type_code == "system_command_ability",
                    Node.is_active == True,  # noqa: E712
                )
            )
            .all()
        )
    graph: Set[str] = set()
    for n in rows:
        attrs = n.attributes or {}
        cn = attrs.get("command_name")
        if isinstance(cn, str) and cn.strip():
            graph.add(cn.strip())

    only_reg = sorted(reg - graph)
    only_graph = sorted(graph - reg)

    if only_reg or only_graph:
        if only_reg:
            print("Only in command_registry:", only_reg)
        if only_graph:
            print("Only in graph (system_command_ability):", only_graph)
        return 1
    print("OK: registry and graph system_command_ability names match (count %d)." % len(reg))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
