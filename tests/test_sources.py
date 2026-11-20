import uuid
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import DataError, IntegrityError

from conftest import alembic_config
from kanon.models import SOURCE_TYPE_VALUES, Source, SourceType

HASH = "a" * 64


def source(**overrides):
    values = {
        "original_filename": "meeting-notes.md",
        "content_hash": HASH,
        "stored_path": f"{HASH[:2]}/{HASH}",
        "type": SourceType.MARKDOWN,
    }
    return Source(**{**values, **overrides})


def test_insert_and_read_back(db_session):
    db_session.add(source())
    db_session.flush()
    db_session.expire_all()

    loaded = db_session.scalars(select(Source)).one()

    assert isinstance(loaded.id, uuid.UUID)
    assert loaded.original_filename == "meeting-notes.md"
    assert loaded.content_hash == HASH
    assert loaded.type is SourceType.MARKDOWN


def test_submission_time_is_set_by_the_database(db_session):
    db_session.add(source())
    db_session.flush()
    db_session.expire_all()

    submitted_at = db_session.scalars(select(Source.submitted_at)).one()

    assert submitted_at.tzinfo is not None
    assert abs(datetime.now(UTC) - submitted_at) < timedelta(minutes=1)


def test_identifiers_are_unique_per_source(db_session):
    a, b = source(), source()
    db_session.add_all([a, b])
    db_session.flush()

    assert a.id != b.id


def test_same_content_may_be_submitted_twice(db_session):
    db_session.add_all([source(), source(original_filename="again.md")])
    db_session.flush()

    assert db_session.execute(text("SELECT count(*) FROM sources")).scalar_one() == 2


@pytest.mark.parametrize("known", SOURCE_TYPE_VALUES)
def test_every_known_type_is_accepted(db_session, known):
    db_session.add(source(type=SourceType(known)))
    db_session.flush()


def test_the_known_types_match_the_scope():
    assert set(SOURCE_TYPE_VALUES) == {
        "markdown", "txt", "pdf", "docx", "transcript", "ticket_export"
    }  # fmt: skip


def test_unknown_type_is_rejected_by_the_database(db_session):
    with pytest.raises(IntegrityError, match="ck_sources_type_known"):
        db_session.execute(
            text(
                "INSERT INTO sources (original_filename, content_hash, stored_path, type) "
                "VALUES ('x', :h, 'p', 'spreadsheet')"
            ),
            {"h": HASH},
        )


@pytest.mark.parametrize("bad", ["", "abc", "A" * 64, "g" * 64, "a" * 63, "a" * 65])
def test_content_hash_must_be_sha256_hex(db_session, bad):
    db_session.add(source(content_hash=bad))

    # Too long for the column (DataError) or failing the CHECK (IntegrityError): rejected.
    with pytest.raises((IntegrityError, DataError)):
        db_session.flush()


@pytest.mark.parametrize("column", ["original_filename", "content_hash", "stored_path"])
def test_required_columns_are_not_null(db_session, column):
    db_session.add(source(**{column: None}))

    with pytest.raises(IntegrityError, match=column):
        db_session.flush()


def test_filename_is_stored_as_given(db_session):
    nasty = "../../etc/passwd\x00 ü☕ \\..\\x.md"
    db_session.add(source(original_filename=nasty.replace("\x00", "")))
    db_session.flush()
    db_session.expire_all()

    assert db_session.scalars(select(Source.original_filename)).one() == nasty.replace("\x00", "")


def test_migration_round_trip(migrated_engine, test_database_url, monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", test_database_url)
    cfg = alembic_config()

    def tables():
        return set(inspect(migrated_engine).get_table_names())

    try:
        command.downgrade(cfg, "0002")
        assert "sources" not in tables()
        assert {"procedures", "procedure_sections"} <= tables()  # earlier tables untouched

        command.upgrade(cfg, "head")
        assert "sources" in tables()

        command.downgrade(cfg, "base")
        assert "sources" not in tables()
    finally:
        command.upgrade(cfg, "head")


def test_columns_match_the_requirements(migrated_engine):
    columns = {c["name"]: c for c in inspect(migrated_engine).get_columns("sources")}

    assert set(columns) == {
        "id", "original_filename", "content_hash", "stored_path", "type", "submitted_at"
    }  # fmt: skip
    assert not any(c["nullable"] for c in columns.values())
