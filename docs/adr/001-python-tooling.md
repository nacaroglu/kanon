# ADR-001: Python version, package manager and repository layout

- **Status:** Accepted
- **Date:** 2026-11-17
- **Backlog / issue:** #3 (`SETUP-002`)

## Context

Product Scope 1.3, section 9.3 fixes the stack at Python + FastAPI, PostgreSQL/pgvector, React, Docker Compose and a CLI, but leaves tooling open. Section 9.1 requires local, Docker Compose based deployment, and section 16 leaves module boundaries and the job library undecided. Every later issue assumes the choices below.

Both decisions are cheap to reverse early and expensive later, so they are made now and time-boxed.

## Options considered

### Decision 1: Python version

| Option | Trade-off |
|---|---|
| Python 3.12 | Widely supported by FastAPI, SQLAlchemy, psycopg and ML/embedding libraries; slightly older than the newest release. |
| Python 3.13 | Newest features and performance; some compiled dependencies may lag behind. |

### Decision 2: Dependency manager

| Option | Lockfile | Speed | Docker friendliness |
|---|---|---|---|
| uv | `uv.lock`, cross-platform, includes hashes | Very fast resolve and install | Official images, `uv sync --frozen` gives reproducible, cache-friendly layers |
| Poetry | `poetry.lock`, mature | Noticeably slower resolve/install | Works, but needs extra setup (plugin/export) for lean images |

### Decision 3: Repository layout

| Option | Trade-off |
|---|---|
| `src/` layout | Tests always run against the installed package, avoiding accidental imports from the working directory; one extra directory level. |
| Flat layout | Simplest tree; easy to import untested local code by accident. |

## Decision

1. **Python 3.12**, pinned in `.python-version` and `requires-python = ">=3.12,<3.13"`.
2. **uv** as dependency and environment manager, with `pyproject.toml` and a committed `uv.lock`.
3. **`src/` layout** with a single importable package `kanon`. The React frontend lives in a separate top-level `frontend/` directory.

Intended top-level layout (created by later issues, not this one):

```text
.
├── src/kanon/        # backend, API and CLI package
├── tests/
├── frontend/         # React app
├── docs/             # scope, ADRs
├── pyproject.toml
├── uv.lock
└── docker-compose.yml
```

Commands contributors will use:

| Task | Command |
|---|---|
| Install dependencies | `uv sync` |
| Add a dependency | `uv add <package>` (dev: `uv add --dev <package>`) |
| Run a command in the environment | `uv run <command>` |
| Run tests | `uv run pytest` |
| Install exactly from the lockfile (Docker/CI) | `uv sync --frozen` |

## Consequences

- Fast, reproducible installs locally, in CI and in Docker images.
- Contributors need uv installed; Poetry-based workflows are not supported.
- The `src/` layout means the package must be installed (done by `uv sync`) before tests or the CLI run.
- Moving to Python 3.13 later is a small change (version pin plus a CI check) once key dependencies support it.
- Revisit if uv becomes unmaintained, or a required dependency does not support Python 3.12.
