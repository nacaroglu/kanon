import os
import subprocess
from datetime import UTC, datetime

import pytest

from kanon.procedures.repository import (
    EmptyRepositoryError,
    NotAGitRepositoryError,
    ProcedureRepository,
    RepositoryError,
)


def test_head_commit_returns_the_fixture_hash_and_date(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        head = repo.head_commit()

    assert head.hash == sample_repo.head
    assert head.committed_at == datetime(2026, 3, 16, 14, 15, tzinfo=UTC)
    assert head.committed_at.utcoffset().total_seconds() == 0


def test_head_ignores_uncommitted_changes(sample_repo):
    (sample_repo.path / "procedures" / "remote-work.md").write_text("changed")
    (sample_repo.path / "procedures" / "new.md").write_text("new")

    with ProcedureRepository(sample_repo.path) as repo:
        assert repo.head_commit().hash == sample_repo.head


def test_head_follows_a_detached_head(sample_repo):
    subprocess.run(
        [
            "git",
            "-C",
            str(sample_repo.path),
            "checkout",
            "--quiet",
            "--detach",
            sample_repo.commits[0],
        ],
        check=True,
    )

    with ProcedureRepository(sample_repo.path) as repo:
        assert repo.head_commit().hash == sample_repo.commits[0]


def test_commit_date_keeps_the_committer_offset(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    env = {
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_DATE": "2026-05-01T12:00:00+0530",
        "GIT_AUTHOR_DATE": "2026-05-01T12:00:00+0530",
        "PATH": os.environ["PATH"],
    }
    for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "x"]):
        subprocess.run(["git", "-C", str(repo_path), *args], check=True, env=env)

    with ProcedureRepository(repo_path) as repo:
        committed_at = repo.head_commit().committed_at

    assert committed_at == datetime(2026, 5, 1, 6, 30, tzinfo=UTC)
    assert committed_at.utcoffset().total_seconds() == 5.5 * 3600


def test_plain_directory_raises_domain_error(tmp_path):
    with pytest.raises(NotAGitRepositoryError, match="not a Git repository"):
        ProcedureRepository(tmp_path)


def test_missing_directory_raises_domain_error(tmp_path):
    with pytest.raises(NotAGitRepositoryError):
        ProcedureRepository(tmp_path / "missing")


def test_subdirectory_of_a_repository_is_not_a_repository(sample_repo):
    with pytest.raises(NotAGitRepositoryError):
        ProcedureRepository(sample_repo.path / "procedures")


def test_repository_without_commits_raises_domain_error(tmp_path):
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)

    with ProcedureRepository(tmp_path) as repo, pytest.raises(EmptyRepositoryError):
        repo.head_commit()


def test_domain_errors_share_a_base_class():
    assert issubclass(NotAGitRepositoryError, RepositoryError)
    assert issubclass(EmptyRepositoryError, RepositoryError)
