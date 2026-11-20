import hashlib
import inspect
import uuid

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

import kanon
from kanon import cli
from kanon.cli import app

runner = CliRunner()


def test_version_prints_package_version():
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == kanon.__version__


def test_help_lists_version_command():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


# --- kanon init ------------------------------------------------------------------------------

SAMPLE_OUTPUT = "Imported 3 procedures (10 sections) from commit "


@pytest.fixture
def cli_database(migrated_engine, test_database_url, monkeypatch, tmp_path):
    """Point the CLI at the test database; it commits for real, so clean up afterwards."""
    monkeypatch.setenv("KANON_DATABASE_URL", test_database_url)
    monkeypatch.setenv("KANON_SOURCE_STORAGE_DIR", str(tmp_path / "stored-sources"))
    yield migrated_engine
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM procedures"))
        connection.execute(text("DELETE FROM sources"))


def row_counts(engine):
    with engine.connect() as connection:
        return tuple(
            connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in ("procedures", "procedure_sections")
        )


def test_init_imports_the_fixture_and_prints_counts(cli_database, sample_repo):
    result = runner.invoke(app, ["init", str(sample_repo.path)])

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == SAMPLE_OUTPUT + sample_repo.head
    assert row_counts(cli_database) == (3, 10)


def test_init_twice_changes_nothing_and_says_so(cli_database, sample_repo):
    first = runner.invoke(app, ["init", str(sample_repo.path)])
    counts_after_first = row_counts(cli_database)
    second = runner.invoke(app, ["init", str(sample_repo.path)])

    assert first.exit_code == second.exit_code == 0, second.output
    assert second.stdout.strip() == (
        f"Nothing to import: commit {sample_repo.head} is already imported"
    )
    assert row_counts(cli_database) == counts_after_first == (3, 10)


def test_init_uses_the_configured_repository_by_default(cli_database, sample_repo, monkeypatch):
    monkeypatch.setenv("KANON_PROCEDURE_REPO_PATH", str(sample_repo.path))

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    assert row_counts(cli_database) == (3, 10)


def test_init_can_import_an_earlier_commit(cli_database, sample_repo):
    result = runner.invoke(app, ["init", str(sample_repo.path), "--commit", sample_repo.commits[0]])

    assert result.exit_code == 0, result.output
    assert "Imported 1 procedures (4 sections)" in result.stdout
    assert row_counts(cli_database) == (1, 4)


def test_init_rejects_a_path_that_is_not_a_repository(cli_database, tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path)])

    assert result.exit_code == 1
    assert result.stderr.strip() == f"error: not a Git repository: {tmp_path}"
    assert "Traceback" not in result.output
    assert row_counts(cli_database) == (0, 0)


def test_init_rejects_a_missing_path(cli_database, tmp_path):
    result = runner.invoke(app, ["init", str(tmp_path / "missing")])

    assert result.exit_code == 1
    assert "error: not a Git repository" in result.stderr


def test_init_reports_an_unknown_commit(cli_database, sample_repo):
    result = runner.invoke(app, ["init", str(sample_repo.path), "--commit", "nope"])

    assert result.exit_code == 1
    assert "no such commit" in result.stderr
    assert row_counts(cli_database) == (0, 0)


def test_init_without_a_path_or_setting_explains_what_to_do(cli_database):
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "KANON_PROCEDURE_REPO_PATH" in result.stderr


def test_init_without_database_configuration_is_a_readable_error(sample_repo):
    result = runner.invoke(app, ["init", str(sample_repo.path)])  # no KANON_DATABASE_URL

    assert result.exit_code == 1
    assert "invalid configuration: database_url" in result.stderr
    assert "Traceback" not in result.output


def test_init_with_an_unreachable_database_is_a_readable_error(sample_repo, monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")

    result = runner.invoke(app, ["init", str(sample_repo.path)])

    assert result.exit_code == 1
    assert result.stderr.startswith("error: database error")


def test_init_command_is_a_thin_wrapper():
    source = inspect.getsource(cli.init)
    assert "import_from_path(" in source
    assert "ProcedureRepository" not in source and "session" not in source


def test_help_lists_init():
    assert "init" in runner.invoke(app, ["--help"]).output


# --- kanon submit ----------------------------------------------------------------------------


def source_rows(engine):
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT id, original_filename, content_hash, type FROM sources")
        ).all()


@pytest.fixture
def notes(tmp_path):
    path = tmp_path / "meeting-notes.md"
    path.write_bytes(b"# Decision\r\n\r\nReimburse within 45 days.\r\n")
    return path


def test_submit_prints_only_the_identifier_on_stdout(cli_database, notes):
    result = runner.invoke(app, ["submit", str(notes)])

    assert result.exit_code == 0, result.stderr
    identifier = result.stdout.strip()
    assert str(uuid.UUID(identifier)) == identifier
    assert result.stdout == identifier + "\n"  # nothing else, so it can be captured
    assert "Submitted meeting-notes.md" in result.stderr


def test_submit_creates_exactly_one_source(cli_database, notes):
    result = runner.invoke(app, ["submit", str(notes)])

    (row,) = source_rows(cli_database)
    assert str(row.id) == result.stdout.strip()
    assert (row.original_filename, row.type) == ("meeting-notes.md", "markdown")
    assert row.content_hash == hashlib.sha256(notes.read_bytes()).hexdigest()


def test_submit_stores_the_bytes_unchanged(cli_database, notes, tmp_path):
    runner.invoke(app, ["submit", str(notes)])

    (row,) = source_rows(cli_database)
    stored = tmp_path / "stored-sources" / row.content_hash[:2] / row.content_hash
    assert stored.read_bytes() == notes.read_bytes()


def test_submitting_twice_creates_two_sources_with_different_identifiers(cli_database, notes):
    first = runner.invoke(app, ["submit", str(notes)]).stdout.strip()
    second = runner.invoke(app, ["submit", str(notes)]).stdout.strip()

    assert first != second
    assert len(source_rows(cli_database)) == 2


def test_submit_accepts_uppercase_and_long_markdown_extensions(cli_database, tmp_path):
    for name in ("A.MD", "b.markdown"):
        path = tmp_path / name
        path.write_text("# x\n")
        assert runner.invoke(app, ["submit", str(path)]).exit_code == 0


@pytest.mark.parametrize("name", ["report.pdf", "data.txt", "notes.docx", "README", "x.md.exe"])
def test_submit_rejects_other_types_with_a_clear_message(cli_database, tmp_path, name):
    path = tmp_path / name
    path.write_text("content")

    result = runner.invoke(app, ["submit", str(path)])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "unsupported file type" in result.stderr and "Markdown" in result.stderr
    assert "Traceback" not in result.output
    assert source_rows(cli_database) == []


def test_submit_rejects_a_missing_file(cli_database, tmp_path):
    result = runner.invoke(app, ["submit", str(tmp_path / "nope.md")])

    assert result.exit_code == 1
    assert "file not found" in result.stderr
    assert source_rows(cli_database) == []


def test_submit_rejects_a_directory(cli_database, tmp_path):
    (tmp_path / "dir.md").mkdir()

    result = runner.invoke(app, ["submit", str(tmp_path / "dir.md")])

    assert result.exit_code == 1
    assert "file not found" in result.stderr


def test_submit_rejects_a_file_that_is_not_utf8(cli_database, tmp_path):
    path = tmp_path / "latin1.md"
    path.write_bytes("café".encode("latin-1"))

    result = runner.invoke(app, ["submit", str(path)])

    assert result.exit_code == 1
    assert "not valid UTF-8" in result.stderr
    assert source_rows(cli_database) == []


def test_submit_reports_a_storage_failure_and_creates_no_source(
    cli_database, notes, tmp_path, monkeypatch
):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where the storage directory should be")
    monkeypatch.setenv("KANON_SOURCE_STORAGE_DIR", str(blocker / "sources"))

    result = runner.invoke(app, ["submit", str(notes)])

    assert result.exit_code == 1
    assert "cannot store file" in result.stderr
    assert source_rows(cli_database) == []


def test_submit_without_database_configuration_is_a_readable_error(notes):
    result = runner.invoke(app, ["submit", str(notes)])

    assert result.exit_code == 1
    assert "invalid configuration: database_url" in result.stderr


def test_submit_with_an_unreachable_database_is_a_readable_error(notes, monkeypatch):
    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://u:p@127.0.0.1:1/none")

    result = runner.invoke(app, ["submit", str(notes)])

    assert result.exit_code == 1
    assert result.stderr.startswith("error: database error")


def test_submit_only_stores_it_and_does_not_start_analysis(cli_database, notes):
    runner.invoke(app, ["submit", str(notes)])

    with cli_database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM procedures")).scalar_one() == 0


def test_submit_command_is_a_thin_wrapper():
    source = inspect.getsource(cli.submit)

    assert "submit_markdown(" in source
    assert "session" not in source and "store_source" not in source


def test_help_lists_submit():
    assert "submit" in runner.invoke(app, ["--help"]).output
