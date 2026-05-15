# CampusWorld Project Structure Map

本文档是 CampusWorld 的项目结构地图（structure map），用于回答两个问题：

1. 代码和文档分别放在哪里（where）。
2. 每个目录承担什么职责（what）。

治理原则、架构不变量、执行规范请分别以 `docs/architecture/README.md`、`docs/**/SPEC/`、`AGENTS.md` 为准。

## Repository Root

```text
campusworld/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── QUICKSTART.md
├── PROJECT_STRUCTURE.md
├── backend/
├── frontend/
├── client/
├── docs/
├── scripts/
├── docker/
├── docker-compose.yml
└── docker-compose.dev.yml
```

## Top-Level Directory Responsibilities

| Path | Responsibility |
|---|---|
| `backend/` | Python backend: core config, command system, world runtime, API/SSH adapters, persistence, tests |
| `frontend/` | Vue frontend: views/components/stores/api client and interaction UI |
| `client/` | Experimental standalone CLI client package (`campus`) |
| `docs/` | Human-facing documentation root and module SPEC contracts |
| `scripts/` | Repository-level helper scripts |
| `docker/` + compose files | Containerization and local orchestration |

## Backend Map

```text
backend/
├── campusworld.py
├── app/
│   ├── core/          # config, database, logging, security, permissions
│   ├── models/        # graph model and ontology-backed entities
│   ├── commands/      # protocol-neutral command contracts and execution
│   ├── game_engine/   # world loading/runtime and agent runtime framework
│   ├── games/         # world packages (hicampus, ...)
│   ├── api/           # HTTP/FastAPI adapter
│   ├── ssh/           # SSH adapter
│   ├── protocols/     # protocol bridge/shared handlers
│   ├── services/      # domain services
│   ├── repositories/  # persistence/repository helpers
│   └── schemas/       # API schemas
├── db/
│   ├── schemas/
│   ├── ontology/
│   ├── seeds/
│   └── schema_migrations.py
├── config/
├── scripts/
└── tests/
```

Backend boundaries align with root `AGENTS.md`:

- `app/commands/` is the shared business interaction layer.
- `app/api/`, `app/ssh/`, `app/protocols/` are adapters over shared services/commands.
- world packages are under `backend/app/games/<world_id>/`.

## Frontend Map

```text
frontend/
├── src/
│   ├── api/           # HTTP client calls
│   ├── stores/        # Pinia stores
│   ├── views/         # page-level views
│   ├── components/    # reusable UI components
│   ├── router/
│   ├── composables/
│   ├── websocket/
│   ├── styles/
│   ├── types/
│   └── test/
├── public/
└── package.json
```

## Client Map (`client/campus`)

`client/campus` is implemented and currently treated as an experimental standalone CLI client.

```text
client/
├── campus/
│   ├── __main__.py
│   ├── config.py
│   ├── connection.py
│   ├── protocol.py
│   ├── terminal.py
│   └── terminal.css
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Docs Map

```text
docs/
├── README.md
├── architecture/
├── standards/
├── command/
├── models/
├── task/
├── frontend/
├── testing/
├── games/
└── ... other module docs
```

Documentation contract layout follows:

- `docs/<module>/SPEC/SPEC.md`
- `docs/<module>/SPEC/TODO.md`
- `docs/<module>/SPEC/ACCEPTANCE.md`
- `docs/<module>/SPEC/features/*.md`

Normative naming/placement rules are defined in `docs/standards/DOC_NAMING_SPEC.md`.

## Update Rule

When repository structure changes in a way that affects onboarding, ownership, or cross-team navigation:

1. Update this map (`PROJECT_STRUCTURE.md`) to reflect actual paths.
2. Keep architecture/governance statements in their own SSOT docs.
3. Avoid adding implementation policy details here; link out instead.
