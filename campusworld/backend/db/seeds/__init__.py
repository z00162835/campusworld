"""Lightweight seed-data helpers loaded by ``db.schema_migrations``.

Modules here MUST avoid importing heavy app subsystems (SQLAlchemy ORM models,
service singletons, etc.) so that ``ensure_*_seed`` migration steps can run on
fresh databases before the application package finishes initialising.
"""
