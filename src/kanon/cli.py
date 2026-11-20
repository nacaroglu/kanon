"""The `kanon` command-line interface.

Design: the CLI calls application code in-process rather than going through HTTP,
so it works without a running server and shares services with the API.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from kanon import __version__
from kanon.procedures.importer import ProcedureImportError, import_from_path
from kanon.procedures.repository import RepositoryError
from kanon.sources.store import SourceStorageError
from kanon.sources.submit import SubmissionError, submit_markdown

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
    with _reporting_errors():
        summary = import_from_path(path, commit)
    if summary.already_imported:
        typer.echo(f"Nothing to import: commit {summary.commit_hash} is already imported")
        return
    typer.echo(
        f"Imported {summary.files} procedures ({summary.sections} sections) "
        f"from commit {summary.commit_hash}"
    )


@app.command()
def submit(
    file: Annotated[Path, typer.Argument(help="Markdown file to submit as a source document.")],
) -> None:
    """Store a source document and print its identifier.

    Only the identifier goes to standard output, so it can be captured:
    `SOURCE=$(kanon submit notes.md)`. Anything meant for people goes to standard error.
    """
    with _reporting_errors():
        submitted = submit_markdown(file)
    typer.echo(f"Submitted {submitted.original_filename}", err=True)
    typer.echo(str(submitted.id))


@contextmanager
def _reporting_errors() -> Iterator[None]:
    """Turn expected failures into `error: ...` on stderr and exit code 1, without a traceback."""
    try:
        yield
    except (RepositoryError, ProcedureImportError, SubmissionError, SourceStorageError) as error:
        _fail(str(error))
    except ValidationError as error:
        first = error.errors()[0]
        _fail(f"invalid configuration: {first['loc'][0]}: {first['msg']}")
    except SQLAlchemyError as error:
        _fail(f"database error: {type(error).__name__}")


def _fail(message: str) -> typer.Exit:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=1)
