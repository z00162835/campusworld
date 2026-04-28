"""
Run trait sync worker once.
"""

from __future__ import annotations

from app.services.trait_sync_worker import process_trait_sync_jobs


def main() -> int:
    result = process_trait_sync_jobs(limit=500)
    print(result)
    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
