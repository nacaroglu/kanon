import subprocess
from datetime import UTC, datetime

from conftest import SAMPLE_COMMITS, SAMPLE_PROCEDURE_PATHS, build_sample_repo


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def test_known_hashes(sample_repo):
    assert sample_repo.head == SAMPLE_COMMITS[-1]
    assert git(sample_repo.path, "rev-list", "--reverse", "HEAD").split() == list(SAMPLE_COMMITS)


def test_two_runs_produce_identical_history(sample_repo, tmp_path):
    second = tmp_path / "second"

    assert build_sample_repo(second) == sample_repo.head
    assert git(second, "rev-parse", "HEAD") == git(sample_repo.path, "rev-parse", "HEAD")


def test_commits_touch_different_files(sample_repo):
    touched = [
        set(git(sample_repo.path, "show", "--name-only", "--format=", commit).split())
        for commit in SAMPLE_COMMITS
    ]

    assert len(touched) >= 2
    assert touched[1] == {"procedures/remote-work.md"}
    assert touched[2] == {"procedures/incident-response.md"}
    assert touched[1].isdisjoint(touched[2])


def test_procedures_and_non_procedures(sample_repo):
    files = set(git(sample_repo.path, "ls-files").split())

    assert set(SAMPLE_PROCEDURE_PATHS) <= files
    assert {"README.md", "procedures/index.txt"} <= files  # present but not procedures
    assert git(sample_repo.path, "status", "--porcelain") == ""


def test_commit_dates_are_fixed(sample_repo):
    dates = git(sample_repo.path, "log", "--reverse", "--format=%ct").split()

    # Unix timestamps of the fixed UTC dates; avoids depending on Git's date formatting.
    assert [int(d) for d in dates] == [
        int(datetime(2026, 1, 5, 9, 0, tzinfo=UTC).timestamp()),
        int(datetime(2026, 2, 10, 10, 30, tzinfo=UTC).timestamp()),
        int(datetime(2026, 3, 16, 14, 15, tzinfo=UTC).timestamp()),
    ]
