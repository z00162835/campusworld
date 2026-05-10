# CampusWorld Claude Compatibility Entry

`AGENTS.md` is the primary instruction source for coding agents in this repository.

Claude Code / Cursor style tools that read `CLAUDE.md` should follow:

- [AGENTS.md](AGENTS.md) for root execution rules and invariants.
- Child `AGENTS.md` files in the working subtree for module-specific rules.
- `docs/**/SPEC/` as the source of truth for behavior contracts.

Do not duplicate architectural guidance here. Update `AGENTS.md` first, then keep this file as a compatibility pointer.
