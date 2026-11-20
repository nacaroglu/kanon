"""Proves the database fixtures isolate tests from each other."""

from sqlalchemy import text


def _insert_same_row(db_session):
    # DDL is transactional in PostgreSQL, so this table disappears on rollback too.
    db_session.execute(text("CREATE TABLE fixture_probe (id integer PRIMARY KEY, name text)"))
    db_session.execute(text("INSERT INTO fixture_probe VALUES (1, 'same row')"))
    count = db_session.execute(text("SELECT count(*) FROM fixture_probe")).scalar_one()
    assert count == 1


def test_insert_row_first(db_session):
    _insert_same_row(db_session)


def test_insert_same_row_second(db_session):
    _insert_same_row(db_session)


def test_migrations_applied(db_session):
    version = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0001"
