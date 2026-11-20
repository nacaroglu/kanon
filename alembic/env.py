"""Alembic environment. The database URL comes from application settings."""

from alembic import context

from kanon.db import get_engine
from kanon.settings import get_settings

config = context.config

# Models arrive in later issues; they will set this to their metadata.
target_metadata = None


def run_migrations_offline() -> None:
    url = get_settings().database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = get_engine()
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
