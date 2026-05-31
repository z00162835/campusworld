# CampusWorld Next UI Implementation Plan

Status: active

Generated: 2026-05-31

## Summary

`/works` is upgraded into the CampusWorld world interaction surface. The implementation uses stable domain names in code and keeps phase names out of API paths, services, stores, components, and types.

## Implementation Snapshot

- Current location is restored from account `location_id`.
- `world-sessions` is an HTTP aggregation adapter, not a new position source of truth.
- World entry and exit actions are routed through `enter <world_id>` and `leave`.
- Decision actions resolve generated `decision_event_id + option_id` pairs and dispatch through the command layer or task commands.
- `/` in the decision input opens a mode selector with `Command` and `AICO`.
- `/works` renders `WorldInteractionView`.

## Verification

- Frontend type-check and tests.
- Frontend production build.
- Backend API tests, including world interaction adapter routes.
- Config validation and command alias validation in the `campusworld` Conda environment.

## Known Follow-Up

- Full authenticated browser inspection requires a running backend and a valid Web UI session.
- SPEC layout validation currently fails on the pre-existing command doc filename `docs/command/SPEC/features/ALIAS_GOVERNANCE.md`.
