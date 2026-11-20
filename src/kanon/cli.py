"""The `kanon` command-line interface.

Design: the CLI calls application code in-process rather than going through HTTP,
so it works without a running server and shares services with the API.
"""

from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from kanon import __version__
from kanon.procedures.importer import ProcedureImportError, import_from_path
from kanon.procedures.repository import RepositoryError

app = typer.Typer(help="Kanon command-line interface.", no_args_is_help=True)


@app.callback()
def main() -> None:
    """Kanon command-line interface."""


@app.command()
def version() -> None:
    """Print the Kanon version."""
    typer.echo(__version__)


@app.command()
def init(
    path: Annotated[
        Path | None,
        typer.Argument(help="Procedure repository to import (default: KANON_PROCEDURE_REPO_PATH)."),
    ] = None,
    commit: Annotated[
        str | None, typer.Option(help="Commit to import: hash, branch or tag (default: HEAD).")
    ] = None,
) -> None:
    """Import the approved procedures of a Git repository into Kanon."""
    try:
        summary = import_from_path(path, commit)
    except (RepositoryError, ProcedureImportError) as error:
        _fail(str(error))
    except ValidationError as error:
        _fail(f"invalid configuration: {error.errors()[0]['loc'][0]}: {error.errors()[0]['msg']}")
    except SQLAlchemyError as error:
        _fail(f"database error: {type(error).__name__}")
    if summary.already_imported:
        typer.echo(f"Nothing to import: commit {summary.commit_hash} is already imported")
        return
    typer.echo(
        f"Imported {summary.files} procedures ({summary.sections} sections) "
        f"from commit {summary.commit_hash}"
    )


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=1)
