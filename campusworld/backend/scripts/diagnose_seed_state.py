#!/usr/bin/env python3
"""
诊断当前数据库种子数据状态（只读）
"""

import sys
from pathlib import Path

from sqlalchemy import text

# 确保可导入 app.*
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from app.core.database import get_engine  # noqa: E402


def main() -> int:
    engine = get_engine()
    with engine.connect() as c:
        def count(table: str) -> int:
            return int(c.execute(text(f"select count(*) from {table}")).scalar() or 0)

        print("=== Seed State ===")
        for t in ["node_types", "relationship_types", "nodes", "relationships"]:
            try:
                print(f"{t}: {count(t)}")
            except Exception as e:
                print(f"{t}: ERROR {e}")

        try:
            types = c.execute(text("select type_code from node_types order by type_code")).fetchall()
            print("node_types.type_code:", [r[0] for r in types])
        except Exception as e:
            print("node_types.type_code: ERROR", e)

        try:
            accounts = c.execute(
                text(
                    "select id,name,access_level from nodes where type_code='account' order by id"
                )
            ).fetchall()
            print("account nodes:", accounts)
        except Exception as e:
            print("account nodes: ERROR", e)

        try:
            root = c.execute(
                text(
                    "select id,name from nodes where type_code='room' and (attributes->>'is_root')='true' limit 1"
                )
            ).fetchall()
            print("root node:", root)
        except Exception as e:
            print("root node: ERROR", e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

