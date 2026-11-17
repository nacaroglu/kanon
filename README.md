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

### Lint and format

```bash
uv run ruff check .          # lint
uv run ruff format .         # format (use `--check` to only report)
```
