"""
Print trait migration consistency report.
"""

from __future__ import annotations

import json

from db.trait_migration_check import run_trait_migration_checks


def main() -> int:
    report = run_trait_migration_checks().to_dict()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    ok = (
        report["node_type_mismatch"] == 0
        and report["relationship_type_mismatch"] == 0
        and report["null_or_negative_masks"] == 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
