# HiCampus World Package Agent Guide

Follow root and backend `AGENTS.md` first. This file covers the HiCampus content package.

## Source Of Truth

- Contract: `../../../../docs/games/hicampus/SPEC/SPEC.md`
- Package README: `package/README.md`
- Runtime manifest: `manifest.yaml`
- Content data: `data/`

## Invariants

- HiCampus is a world package under `backend/app/games/hicampus/`; do not move its business data into global seeds.
- `manifest.yaml` must keep `world_id`, `version`, `api_version`, and `data_dir`.
- `graph_seed: true` requires PostgreSQL migrations and writes package snapshots through `game_engine/graph_seed/`.
- Environments without PostgreSQL should use `graph_seed: false` only when graph navigation is not required.
- Spawn points and movement targets must exist in graph data before `enter hicampus` can work.
- World entrances are managed via `world_entry_service`; do not model them as `type_code=world` metadata nodes.
- HiCampus requires exactly one `world_environment` in `world.yaml`; outdoor `look` uses tag `environment:outdoor` (plaza/bridge only, not gate).

## Verification

- Validate package data after YAML changes using the package tools documented in `package/README.md`.
- With DB available: `world install hicampus`, `look`, `enter hicampus`, then `world validate hicampus`.
- After changing `world.yaml` / outdoor tags: `python -m db.init_database migrate` then `world reload hicampus`.
- Check representative path: `n`, `n`, `n`, `w`, `e`, `u`, `n`.

## Change Discipline

- Keep package IDs stable unless a migration explicitly covers the rename.
- Update docs and generated package artifacts together when source YAML changes.
- Do not hand-edit generated outputs when a generator is the source of truth.
