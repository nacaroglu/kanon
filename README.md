# Kanon

Kanon is a document-driven workflow tool: it turns source documents into reviewed, evidence-backed proposals using LLMs, with a CLI and a Web UI, a reviewer step, and an evaluation harness to measure quality.

> **Status: early development.** Nothing here is stable or ready for use yet.

## Documentation

- [Product Scope v1.3](docs/product-scope-v1.3.md) — the agreed scope of Kanon v1.

## Development setup

Requires [uv](https://docs.astral.sh/uv/). From a fresh clone:

```bash
uv sync
```

See [ADR-001](docs/adr/001-python-tooling.md) for the tooling decisions.

### CLI

```bash
uv run kanon --help
uv run kanon version
```

The CLI calls application code in-process rather than going through HTTP.
=======
### Configuration

Settings are read only through `kanon.settings.Settings` (environment variables with the `KANON_` prefix, or a `.env` file). Copy the example and adjust:

```bash
cp .env.example .env
```

`KANON_DATABASE_URL` is required; the app refuses to start without it. `.env` is ignored by Git.

### Database migrations

Schema changes go through Alembic; the database URL is read from settings (`KANON_DATABASE_URL`), never from `alembic.ini`.

```bash
# Against the Compose database (the db port is not published, so run inside the stack):
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic downgrade base

# Against any database reachable from the host:
KANON_DATABASE_URL=postgresql://user:pass@localhost:5432/kanon uv run alembic upgrade head
```

Create a revision with `uv run alembic revision -m "describe the change"`.

### Run the API

```bash
uv run uvicorn kanon.api.app:create_app --factory --reload
curl http://127.0.0.1:8000/health   # {"status":"ok"}
```

The service binds to localhost by default (Product Scope 9.2).

### Logging

Logs are JSON, one object per line on stderr, with the level taken from `KANON_LOG_LEVEL`. Each HTTP request produces exactly one line with `method`, `path`, `status` and `duration_ms`. Log identifiers, never document content.
=======
### Run with Docker Compose

```bash
cp .env.example .env     # credentials come from this file
docker compose up --build
curl http://127.0.0.1:8000/health
```

**Localhost only.** Kanon v1 is single-user with no authentication (Product Scope 9.2), so published ports are bound to `127.0.0.1` only (`127.0.0.1:8000:8000`). The service is not reachable from other machines. The database port is not published at all. Inside the container uvicorn still listens on all interfaces; the restriction is the port mapping. Do not change it to `0.0.0.0` or `8000:8000`.

Database data lives in the named volume `db-data` and survives `docker compose down` / `up`. Use `docker compose down -v` to delete it.

### Run in Docker

```bash
docker build -t kanon-backend .
docker run --rm -p 127.0.0.1:8000:8000 -e KANON_DATABASE_URL=postgresql://x/y kanon-backend
curl http://127.0.0.1:8000/health
```

The image installs from `uv.lock`, runs as a non-root user, and keeps dependencies in a separate layer from application code.


### Lint and format

```bash
uv run ruff check .          # lint
uv run ruff format .         # format (use `--check` to only report)
```

### Tests

```bash
uv run pytest
```

Database tests need a real PostgreSQL and are skipped unless `KANON_TEST_DATABASE_URL` points at a throwaway database (migrations are applied to it once per session; each test runs in a rolled-back transaction):

```bash
KANON_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/kanon_test uv run pytest
```

CI provides a PostgreSQL service and runs these tests.

### Pre-commit hooks

Install once per clone; afterwards Ruff lint and format run on every commit:

```bash
uv run pre-commit install
```

### Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request and push to `main`. It installs from the lockfile (`uv sync --frozen`), then runs lint, the format check and the tests: the same commands as above.
