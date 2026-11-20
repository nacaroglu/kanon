import inspect

import pytest
from sqlalchemy import text
from typer.testing import CliRunner

import kanon
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
def cli_database(migrated_engine, test_database_url, monkeypatch):
    """Point the CLI at the test database; it commits for real, so clean up afterwards."""
    monkeypatch.setenv("KANON_DATABASE_URL", test_database_url)
    yield migrated_engine
    with migrated_engine.begin() as connection:
        connection.execute(text("DELETE FROM procedures"))


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
    from kanon import cli

    source = inspect.getsource(cli.init)
    assert "import_from_path(" in source
    assert "ProcedureRepository" not in source and "session" not in source


def test_help_lists_init():
    assert "init" in runner.invoke(app, ["--help"]).output
