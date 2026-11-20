import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError

from conftest import alembic_config
from kanon.models import Procedure, ProcedureSection

C1 = "a" * 40
C2 = "b" * 40
BLOB = "c" * 40


def procedure(path="procedures/a.md", commit=C1, sections=2):
    return Procedure(
        path=path,
        title="A",
        commit_hash=commit,
        blob_hash=BLOB,
        sections=[
            ProcedureSection(
                position=i, heading=f"H{i}", level=1, text=f"# H{i}\n", start_offset=i * 5,
                end_offset=i * 5 + 5,
            )
            for i in range(sections)
        ],
    )  # fmt: skip


def count(session, table):
    return session.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()


def test_insert_and_read_back_in_order(db_session):
    db_session.add(procedure(sections=3))
    db_session.flush()
    db_session.expire_all()

    loaded = db_session.scalars(select(Procedure)).one()

    assert [s.position for s in loaded.sections] == [0, 1, 2]
    assert loaded.sections[1].heading == "H1"
    assert (loaded.commit_hash, loaded.blob_hash) == (C1, BLOB)


def test_preamble_section_may_have_no_heading_or_level(db_session):
    db_session.add(
        Procedure(
            path="p.md", title="t", commit_hash=C1, blob_hash=BLOB,
            sections=[ProcedureSection(position=0, text="x", start_offset=0, end_offset=1)],
        )
    )  # fmt: skip
    db_session.flush()


def test_path_is_unique_per_commit(db_session):
    db_session.add(procedure())
    db_session.flush()

    db_session.add(procedure())  # same path, same commit
    with pytest.raises(IntegrityError, match="uq_procedures_commit_hash_path"):
        db_session.flush()


def test_same_path_at_another_commit_is_allowed(db_session):
    db_session.add_all([procedure(commit=C1), procedure(commit=C2)])
    db_session.flush()

    assert count(db_session, "procedures") == 2


def test_other_path_at_same_commit_is_allowed(db_session):
    db_session.add_all([procedure(path="procedures/a.md"), procedure(path="procedures/b.md")])
    db_session.flush()

    assert count(db_session, "procedures") == 2


def test_deleting_a_procedure_removes_its_sections(db_session):
    db_session.add_all([procedure(path="procedures/a.md"), procedure(path="procedures/b.md")])
    db_session.flush()
    assert count(db_session, "procedure_sections") == 4

    db_session.delete(db_session.scalars(select(Procedure).filter_by(path="procedures/a.md")).one())
    db_session.flush()

    assert count(db_session, "procedure_sections") == 2


def test_database_cascades_even_without_the_orm(db_session):
    db_session.add(procedure())
    db_session.flush()

    db_session.execute(text("DELETE FROM procedures"))

    assert count(db_session, "procedure_sections") == 0


def test_section_position_is_unique_within_a_procedure(db_session):
    p = procedure(sections=1)
    db_session.add(p)
    db_session.flush()

    p.sections.append(ProcedureSection(position=0, text="dup", start_offset=0, end_offset=1))
    with pytest.raises(IntegrityError, match="uq_procedure_sections_procedure_position"):
        db_session.flush()


@pytest.mark.parametrize(
    ("values", "constraint"),
    [
        ({"position": -1}, "position_non_negative"),
        ({"start_offset": -1}, "start_offset_non_negative"),
        ({"start_offset": 5, "end_offset": 4}, "end_after_start"),
        ({"level": 0}, "level_range"),
        ({"level": 7}, "level_range"),
    ],
)
def test_section_check_constraints(db_session, values, constraint):
    base = {"position": 0, "text": "x", "start_offset": 0, "end_offset": 1}
    db_session.add(
        Procedure(
            path="p.md", title="t", commit_hash=C1, blob_hash=BLOB,
            sections=[ProcedureSection(**{**base, **values})],
        )
    )  # fmt: skip

    with pytest.raises(IntegrityError, match=constraint):
        db_session.flush()


def test_required_columns_are_not_null(db_session):
    db_session.add(Procedure(path="p.md", title="t", commit_hash=C1))  # no blob hash

    with pytest.raises(IntegrityError, match="blob_hash"):
        db_session.flush()


def test_migration_round_trip(migrated_engine, test_database_url, monkeypatch):
    """Downgrade past this migration and back up; the schema must match each time."""
    monkeypatch.setenv("KANON_DATABASE_URL", test_database_url)  # read by alembic/env.py
    cfg = alembic_config()

    def tables():
        return set(inspect(migrated_engine).get_table_names())

    try:
        command.downgrade(cfg, "0001")
        assert not {"procedures", "procedure_sections"} & tables()

        command.upgrade(cfg, "head")
        assert {"procedures", "procedure_sections"} <= tables()

        command.downgrade(cfg, "base")
        assert {"procedures", "procedure_sections"}.isdisjoint(tables())
    finally:
        command.upgrade(cfg, "head")  # leave the shared test database migrated


def test_models_match_the_migration(migrated_engine):
    """Autogenerate finds no difference between the models and the migrated database."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from kanon.models import Base

    with migrated_engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == []
