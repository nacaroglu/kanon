"""The only module that talks to Git.

Everything else asks `ProcedureRepository` for what it needs, so the Git library can be
replaced without touching the rest of the code base.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import TracebackType
from typing import Self

from dulwich.errors import NotGitRepository
from dulwich.repo import Repo


class RepositoryError(Exception):
    """Base class for errors raised by the procedure repository."""


class NotAGitRepositoryError(RepositoryError):
    """The configured path is not the root of a Git repository."""


class EmptyRepositoryError(RepositoryError):
    """The repository has no commits yet, so there is no HEAD to read."""


@dataclass(frozen=True)
class Commit:
    hash: str  # full 40-character hex object id
    committed_at: datetime  # timezone-aware, in the committer's recorded offset


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
        try:
            sha = self._repo.head()
        except KeyError:
            raise EmptyRepositoryError(f"repository has no commits: {self.path}") from None
        return self._commit(sha)

    def _commit(self, sha: bytes) -> Commit:
        raw = self._repo[sha]
        offset = timezone(timedelta(seconds=raw.commit_timezone))
        return Commit(
            hash=sha.decode("ascii"),
            committed_at=datetime.fromtimestamp(raw.commit_time, tz=UTC).astimezone(offset),
        )
