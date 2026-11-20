import subprocess
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from kanon.models import Procedure, ProcedureSection
from kanon.procedures import importer
from kanon.procedures.importer import ImportSummary, ProcedureImportError, import_procedures
from kanon.procedures.repository import (
    CommitNotFoundError,
    ProcedureRepository,
    UndecodableFileError,
)


def counts(session):
    return (
        session.scalar(select(func.count()).select_from(Procedure)),
        session.scalar(select(func.count()).select_from(ProcedureSection)),
    )


def test_imports_all_fixture_procedures_and_sections(db_session, sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        summary = import_procedures(db_session, repo)

    # expense-reports: 4 sections, remote-work: 3, incident-response: 3
    assert summary == ImportSummary(commit_hash=sample_repo.head, files=3, sections=10)
    assert counts(db_session) == (3, 10)
    procedures = db_session.scalars(select(Procedure).order_by(Procedure.path)).all()
    assert [p.path for p in procedures] == list(sample_repo.procedure_paths)
    assert {p.commit_hash for p in procedures} == {sample_repo.head}
    assert [p.title for p in procedures] == ["Expense Reports", "Incident Response", "Remote Work"]


def test_stored_sections_slice_back_to_the_committed_file(db_session, sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        import_procedures(db_session, repo)
        files = {f.path: f for f in repo.list_procedure_files()}

    for procedure in db_session.scalars(select(Procedure)):
        file = files[procedure.path]
        assert procedure.blob_hash == file.blob_hash
        assert [s.position for s in procedure.sections] == list(range(len(procedure.sections)))
        for section in procedure.sections:
            assert file.content[section.start_offset : section.end_offset] == section.text


def test_import_records_headings_levels_and_preamble(db_session, sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        import_procedures(db_session, repo)

    expense = db_session.scalars(select(Procedure).filter_by(title="Expense Reports")).one()

    assert [(s.heading, s.level) for s in expense.sections] == [
        ("Expense Reports", 1),
        ("Submission deadline", 2),
        ("Approval", 2),
        ("Reports over the limit", 3),
    ]


def test_import_of_an_earlier_commit_uses_that_commit(db_session, sample_repo):
    first = sample_repo.commits[0]
    with ProcedureRepository(sample_repo.path) as repo:
        summary = import_procedures(db_session, repo, first[:10])

    assert summary.commit_hash == first  # the full hash, not the prefix that was passed
    assert summary.files == 1
    assert db_session.scalars(select(Procedure.commit_hash)).all() == [first]


def test_uncommitted_changes_are_not_imported(db_session, sample_repo):
    (sample_repo.path / "procedures" / "remote-work.md").write_text("# Edited\n")
    (sample_repo.path / "procedures" / "new.md").write_text("# New\n")

    with ProcedureRepository(sample_repo.path) as repo:
        summary = import_procedures(db_session, repo)

    assert summary.files == 3
    assert "Edited" not in db_session.scalars(select(Procedure.title)).all()


def test_repository_without_procedures_imports_nothing(db_session, tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@e.invalid",
         "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "x"],
        check=True,
    )  # fmt: skip

    with ProcedureRepository(tmp_path) as repo:
        summary = import_procedures(db_session, repo)

    assert (summary.files, summary.sections) == (0, 0)
    assert counts(db_session) == (0, 0)


def test_unknown_commit_stores_nothing(db_session, sample_repo):
    with ProcedureRepository(sample_repo.path) as repo, pytest.raises(CommitNotFoundError):
        import_procedures(db_session, repo, "deadbeef")

    assert counts(db_session) == (0, 0)


def test_a_broken_file_leaves_nothing_behind(db_session, tmp_path):
    repo_path = tmp_path / "repo"
    (repo_path / "procedures").mkdir(parents=True)
    (repo_path / "procedures" / "a-good.md").write_text("# Good\n")
    (repo_path / "procedures" / "b-bad.md").write_bytes(b"\xff\xfe not utf-8")
    subprocess.run(["git", "-C", str(repo_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo_path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "-c", "user.name=t", "-c", "user.email=t@e.invalid",
         "commit", "-q", "--no-gpg-sign", "-m", "x"],
        check=True,
    )  # fmt: skip

    with ProcedureRepository(repo_path) as repo, pytest.raises(UndecodableFileError):
        import_procedures(db_session, repo)

    assert counts(db_session) == (0, 0)


def test_failure_after_earlier_files_were_added_rolls_everything_back(
    db_session, sample_repo, monkeypatch
):
    real_parse = importer.parse_procedure
    calls = []

    def flaky_parse(text, *, default_title):
        calls.append(default_title)
        if len(calls) == 3:  # fail on the last of three files
            raise RuntimeError("parser exploded")
        return real_parse(text, default_title=default_title)

    monkeypatch.setattr(importer, "parse_procedure", flaky_parse)

    with ProcedureRepository(sample_repo.path) as repo:
        with pytest.raises(ProcedureImportError, match=r"procedures/remote-work\.md.*exploded"):
            import_procedures(db_session, repo)

    assert len(calls) == 3  # two files had been added before the failure
    assert counts(db_session) == (0, 0)
    # The session is still usable and a later, healthy import succeeds.
    monkeypatch.setattr(importer, "parse_procedure", real_parse)
    with ProcedureRepository(sample_repo.path) as repo:
        assert import_procedures(db_session, repo).files == 3


def test_importing_the_same_commit_twice_changes_nothing(db_session, sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        first = import_procedures(db_session, repo)
        before = counts(db_session)
        second = import_procedures(db_session, repo)

    assert (first.files, first.sections, first.already_imported) == (3, 10, False)
    assert (second.files, second.sections, second.already_imported) == (0, 0, True)
    assert second.commit_hash == first.commit_hash
    assert counts(db_session) == before == (3, 10)


def test_a_different_spelling_of_the_same_commit_is_still_a_repeat(db_session, sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        import_procedures(db_session, repo, "main")
        again = import_procedures(db_session, repo, sample_repo.head[:12])

    assert again.already_imported
    assert counts(db_session) == (3, 10)


def test_each_commit_is_imported_once_independently(db_session, sample_repo):
    first_commit = sample_repo.commits[0]
    with ProcedureRepository(sample_repo.path) as repo:
        import_procedures(db_session, repo, first_commit)
        head = import_procedures(db_session, repo)  # a different commit is not a repeat

    assert not head.already_imported
    assert counts(db_session) == (1 + 3, 4 + 10)


def test_the_constraint_catches_a_race_the_check_misses(db_session, sample_repo, monkeypatch):
    """Check-then-insert alone is not enough: two imports can both pass the check."""
    with ProcedureRepository(sample_repo.path) as repo:
        import_procedures(db_session, repo)
        before = counts(db_session)

        calls = []
        real = importer._is_imported

        def blind_first_check(session, commit_hash):
            calls.append(commit_hash)
            return False if len(calls) == 1 else real(session, commit_hash)

        monkeypatch.setattr(importer, "_is_imported", blind_first_check)
        result = import_procedures(db_session, repo)

    assert result.already_imported
    assert len(calls) == 2  # the check was fooled once; the constraint caught it
    assert counts(db_session) == before


def test_integrity_errors_that_are_not_a_repeat_still_surface(db_session, sample_repo, monkeypatch):
    def always_collide(session, files, commit_hash):
        raise IntegrityError("INSERT", {}, Exception("some other violation"))

    monkeypatch.setattr(importer, "_store", always_collide)

    with ProcedureRepository(sample_repo.path) as repo, pytest.raises(IntegrityError):
        import_procedures(db_session, repo)


def test_importer_is_free_of_cli_and_http_concerns():
    source = Path(importer.__file__).read_text()

    assert "typer" not in source and "fastapi" not in source
