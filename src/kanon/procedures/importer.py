"""Import the approved procedures at one commit into the database.

Git stays canonical; this builds the queryable copy that retrieval and contradiction detection
work on. The service knows nothing about the CLI or HTTP: callers pass a session and a repository.
"""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from sqlalchemy.orm import Session

from kanon.db import session_scope
from kanon.models import Procedure, ProcedureSection
from kanon.procedures.parser import parse_procedure
from kanon.procedures.repository import ProcedureRepository
from kanon.settings import get_settings


class ProcedureImportError(Exception):
    """A procedure file could not be imported; nothing from the attempt was stored."""


@dataclass(frozen=True)
class ImportSummary:
    commit_hash: str
    files: int
    sections: int


def import_procedures(
    session: Session, repository: ProcedureRepository, commit: str | None = None
) -> ImportSummary:
    """Store every procedure (and its sections) at `commit`, or HEAD, as one unit.

    All rows are written inside a savepoint: if anything fails, none of this import's rows
    remain, so retrieval never sees half of a repository. The caller owns the outer
    transaction and decides when to commit it.

    Raises `RepositoryError` subclasses for Git problems and `ProcedureImportError` when a
    file cannot be parsed or stored.
    """
    target = repository.get_commit(commit)
    # List by the resolved hash so the files and the stored commit hash can never disagree.
    files = repository.list_procedure_files(target.hash)

    section_count = 0
    with session.begin_nested():
        for file in files:
            try:
                parsed = parse_procedure(file.content, default_title=PurePosixPath(file.path).stem)
                session.add(
                    Procedure(
                        path=file.path,
                        title=parsed.title,
                        commit_hash=target.hash,
                        blob_hash=file.blob_hash,
                        sections=[
                            ProcedureSection(
                                position=position,
                                heading=section.heading,
                                level=section.level,
                                text=section.text,
                                start_offset=section.start,
                                end_offset=section.end,
                            )
                            for position, section in enumerate(parsed.sections)
                        ],
                    )
                )
                section_count += len(parsed.sections)
            except Exception as error:
                raise ProcedureImportError(f"could not import {file.path}: {error}") from error
        session.flush()

    return ImportSummary(commit_hash=target.hash, files=len(files), sections=section_count)


def import_from_path(path: Path | None = None, commit: str | None = None) -> ImportSummary:
    """Open the repository at `path` (default: the configured one) and import it, committing.

    This is what `kanon init` runs; the command itself only parses arguments and prints.
    """
    if path is None:
        path = get_settings().procedure_repo_path
        if path is None:
            raise ProcedureImportError(
                "no repository given: pass a path or set KANON_PROCEDURE_REPO_PATH"
            )
    with ProcedureRepository(path) as repository, session_scope() as session:
        return import_procedures(session, repository, commit)
