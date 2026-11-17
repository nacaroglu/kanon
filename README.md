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

### Configuration

Settings are read only through `kanon.settings.Settings` (environment variables with the `KANON_` prefix, or a `.env` file). Copy the example and adjust:

```bash
cp .env.example .env
```

`KANON_DATABASE_URL` is required; the app refuses to start without it. `.env` is ignored by Git.

### Run the API

```bash
uv run uvicorn kanon.api.app:create_app --factory --reload
curl http://127.0.0.1:8000/health   # {"status":"ok"}
```

The service binds to localhost by default (Product Scope 9.2).

### Lint and format

```bash
uv run ruff check .          # lint
uv run ruff format .         # format (use `--check` to only report)
```

### Tests

```bash
uv run pytest
```

### Pre-commit hooks

Install once per clone; afterwards Ruff lint and format run on every commit:

```bash
uv run pre-commit install
```

### Continuous integration

GitHub Actions (`.github/workflows/ci.yml`) runs on every pull request and push to `main`. It installs from the lockfile (`uv sync --frozen`), then runs lint, the format check and the tests: the same commands as above.
