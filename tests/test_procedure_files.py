import os
import subprocess
from pathlib import Path

import pytest

from kanon.procedures.repository import (
    CommitNotFoundError,
    EmptyRepositoryError,
    ProcedureRepository,
    UndecodableFileError,
)

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def git(repo: Path, *args: str) -> str:
    env = {**os.environ, **GIT_ENV}
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True, env=env
    )
    return result.stdout.strip()


def commit_files(repo: Path, files: dict[str, bytes | None]) -> None:
    """Write (or, for None, delete) files and commit them in one commit."""
    repo.mkdir(parents=True, exist_ok=True)
    if not (repo / ".git").exists():
        git(repo, "init", "-q")
    for name, data in files.items():
        target = repo / name
        if data is None:
            target.unlink()
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "--no-gpg-sign", "-m", "test")


def paths(files):
    return [f.path for f in files]


def test_returns_exactly_the_fixture_procedures(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        files = repo.list_procedure_files()

    assert tuple(paths(files)) == sample_repo.procedure_paths


def test_content_and_blob_hash_match_git(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        files = repo.list_procedure_files()

    for f in files:
        assert f.content == git(sample_repo.path, "show", f"HEAD:{f.path}") + "\n"
        assert f.blob_hash == git(sample_repo.path, "rev-parse", f"HEAD:{f.path}")
    expense = next(f for f in files if f.path.endswith("expense-reports.md"))
    assert expense.content.startswith("---\nowner: Finance Operations\n")


def test_non_markdown_and_markdown_outside_directory_are_ignored(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        found = set(paths(repo.list_procedure_files()))

    assert "README.md" not in found
    assert "procedures/index.txt" not in found


def test_uncommitted_changes_do_not_affect_the_result(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        before = repo.list_procedure_files()

    root = sample_repo.path / "procedures"
    (root / "remote-work.md").write_text("edited but not committed")  # modified
    (root / "incident-response.md").unlink()  # deleted
    (root / "untracked.md").write_text("never added")  # untracked
    (root / "staged.md").write_text("staged only")
    git(sample_repo.path, "add", "procedures/staged.md")  # staged, not committed

    with ProcedureRepository(sample_repo.path) as repo:
        assert repo.list_procedure_files() == before


def test_reads_an_earlier_commit_by_hash_and_prefix(sample_repo):
    first = sample_repo.commits[0]
    with ProcedureRepository(sample_repo.path) as repo:
        by_full = repo.list_procedure_files(first)
        by_prefix = repo.list_procedure_files(first[:10])

    assert paths(by_full) == ["procedures/expense-reports.md"]
    assert by_prefix == by_full


def test_file_versions_differ_between_commits(tmp_path):
    repo_path = tmp_path / "repo"
    commit_files(repo_path, {"procedures/a.md": b"# A\n\nold\n"})
    old = git(repo_path, "rev-parse", "HEAD")
    commit_files(repo_path, {"procedures/a.md": b"# A\n\nnew\n"})

    with ProcedureRepository(repo_path) as repo:
        (old_file,) = repo.list_procedure_files(old)
        (new_file,) = repo.list_procedure_files()

    assert old_file.content.endswith("old\n") and new_file.content.endswith("new\n")
    assert old_file.blob_hash != new_file.blob_hash


def test_nested_directories_are_included_and_sorted(tmp_path):
    repo_path = tmp_path / "repo"
    commit_files(
        repo_path,
        {
            "procedures/b.md": b"b",
            "procedures/hr/leave.md": b"leave",
            "procedures/hr/deep/onboarding.md": b"onboarding",
            "procedures/a.md": b"a",
        },
    )

    with ProcedureRepository(repo_path) as repo:
        found = paths(repo.list_procedure_files())

    assert found == [
        "procedures/a.md",
        "procedures/b.md",
        "procedures/hr/deep/onboarding.md",
        "procedures/hr/leave.md",
    ]


def test_only_lowercase_md_regular_files_under_the_directory_count(tmp_path):
    repo_path = tmp_path / "repo"
    commit_files(
        repo_path,
        {
            "procedures/ok.md": b"ok",
            "procedures/UPPER.MD": b"no",
            "procedures/notes.markdown": b"no",
            "procedures/script.py": b"no",
            "procedures.md": b"no",
            "docs/procedures/other.md": b"no",
            "proceduresx/other.md": b"no",
        },
    )
    (repo_path / "procedures" / "link.md").symlink_to("ok.md")
    git(repo_path, "add", "-A")
    git(repo_path, "commit", "-q", "--no-gpg-sign", "-m", "symlink")

    with ProcedureRepository(repo_path) as repo:
        assert paths(repo.list_procedure_files()) == ["procedures/ok.md"]


def test_repository_without_procedures_returns_empty_list(tmp_path):
    repo_path = tmp_path / "repo"
    commit_files(repo_path, {"README.md": b"hi"})

    with ProcedureRepository(repo_path) as repo:
        assert repo.list_procedure_files() == []


def test_unknown_commit_raises_domain_error(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        for bad in ("0" * 40, "nope", ""):
            with pytest.raises(CommitNotFoundError):
                repo.list_procedure_files(bad)


def test_empty_repository_raises_domain_error(tmp_path):
    git(tmp_path, "init", "-q")

    with ProcedureRepository(tmp_path) as repo, pytest.raises(EmptyRepositoryError):
        repo.list_procedure_files()


def test_invalid_utf8_raises_domain_error(tmp_path):
    repo_path = tmp_path / "repo"
    commit_files(repo_path, {"procedures/bad.md": b"\xff\xfe not utf-8"})

    with (
        ProcedureRepository(repo_path) as repo,
        pytest.raises(UndecodableFileError, match="bad.md"),
    ):
        repo.list_procedure_files()


def test_content_is_returned_byte_for_byte(tmp_path):
    repo_path = tmp_path / "repo"
    raw = "# T\r\n\r\ncafé — line\r\n".encode()
    commit_files(repo_path, {"procedures/crlf.md": raw})

    with ProcedureRepository(repo_path) as repo:
        (file,) = repo.list_procedure_files()

    assert file.content.encode() == raw
