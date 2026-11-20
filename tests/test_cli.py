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
