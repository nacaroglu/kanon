FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.8 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

RUN useradd --create-home --uid 1000 kanon
WORKDIR /app
RUN chown kanon:kanon /app
USER kanon

# Dependency layer: rebuilt only when pyproject.toml or uv.lock change.
COPY --chown=kanon:kanon pyproject.toml uv.lock .python-version README.md LICENSE ./
RUN --mount=type=cache,target=/home/kanon/.cache/uv,uid=1000,gid=1000 \
    uv sync --frozen --no-dev --no-install-project

# Application layer: rebuilt on every source change, without reinstalling dependencies.
COPY --chown=kanon:kanon src ./src
COPY --chown=kanon:kanon alembic.ini ./
COPY --chown=kanon:kanon alembic ./alembic
RUN --mount=type=cache,target=/home/kanon/.cache/uv,uid=1000,gid=1000 \
    uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uvicorn", "kanon.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
