"""The only module that talks to Git.

Everything else asks `ProcedureRepository` for what it needs, so the Git library can be
replaced without touching the rest of the code base.
"""

import stat
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import TracebackType
from typing import Self

from dulwich.errors import NotGitRepository
from dulwich.object_store import iter_tree_contents
from dulwich.objects import Commit as GitCommit
from dulwich.objectspec import parse_commit
from dulwich.repo import Repo

# Where approved procedures live in the repository (ADR-002).
PROCEDURES_DIR = "procedures"
PROCEDURE_SUFFIX = ".md"


class RepositoryError(Exception):
    """Base class for errors raised by the procedure repository."""


class NotAGitRepositoryError(RepositoryError):
    """The configured path is not the root of a Git repository."""


class EmptyRepositoryError(RepositoryError):
    """The repository has no commits yet, so there is no HEAD to read."""


class CommitNotFoundError(RepositoryError):
    """The requested commit does not exist in the repository."""


class UndecodableFileError(RepositoryError):
    """A procedure file (or its path) is not valid UTF-8."""


@dataclass(frozen=True)
class Commit:
    hash: str  # full 40-character hex object id
    committed_at: datetime  # timezone-aware, in the committer's recorded offset


@dataclass(frozen=True)
class ProcedureFile:
    path: str  # relative to the repository root, with "/" separators
    content: str  # decoded UTF-8 text, exactly as committed
    blob_hash: str  # Git object id of the file content


class ProcedureRepository:
    """Read access to the approved procedure repository."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        try:
            # Opens exactly this directory; Git is not searched for in parent directories.
            self._repo = Repo(str(self.path))
        except NotGitRepository:
            raise NotAGitRepositoryError(f"not a Git repository: {self.path}") from None

    def close(self) -> None:
        self._repo.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def head_commit(self) -> Commit:
        """The commit that HEAD currently points to (through its branch, if any)."""
        return self._commit(self._head_sha())

    def list_procedure_files(self, commit: str | None = None) -> list[ProcedureFile]:
        """The procedure files as committed at `commit`, sorted by path.

        `commit` is a full or abbreviated hash, or a branch/tag name; the default is HEAD.
        Content is read from Git objects, never from the working directory, so uncommitted
        changes cannot affect the result. A procedure is a regular file named `*.md` under
        `procedures/` (ADR-002); everything else is ignored.
        """
        tree_id = self._resolve_commit(commit).tree
        prefix = f"{PROCEDURES_DIR}/".encode()
        files: list[ProcedureFile] = []
        for entry in iter_tree_contents(self._repo.object_store, tree_id):
            if not (
                entry.path.startswith(prefix) and entry.path.endswith(PROCEDURE_SUFFIX.encode())
            ):
                continue
            if not stat.S_ISREG(entry.mode):  # skips symlinks and submodules
                continue
            try:
                path = entry.path.decode("utf-8")
                content = self._repo[entry.sha].data.decode("utf-8")
            except UnicodeDecodeError:
                raise UndecodableFileError(
                    f"not valid UTF-8: {entry.path!r} in {self.path}"
                ) from None
            files.append(ProcedureFile(path, content, entry.sha.decode("ascii")))
        return sorted(files, key=lambda f: f.path)

    def _resolve_commit(self, commit: str | None) -> GitCommit:
        if commit is None:
            return self._repo[self._head_sha()]
        if not commit.strip():
            raise CommitNotFoundError(f"no such commit in {self.path}: {commit!r}")
        try:
            return parse_commit(self._repo, commit)
        except KeyError:
            raise CommitNotFoundError(f"no such commit in {self.path}: {commit!r}") from None

    def _head_sha(self) -> bytes:
        try:
            return self._repo.head()
        except KeyError:
            raise EmptyRepositoryError(f"repository has no commits: {self.path}") from None

    def _commit(self, sha: bytes) -> Commit:
        raw = self._repo[sha]
        offset = timezone(timedelta(seconds=raw.commit_timezone))
        return Commit(
            hash=sha.decode("ascii"),
            committed_at=datetime.fromtimestamp(raw.commit_time, tz=UTC).astimezone(offset),
        )
