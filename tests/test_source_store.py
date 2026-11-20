import hashlib
import os
import stat
from pathlib import Path

import pytest
from sqlalchemy import func, select

from kanon.models import Source, SourceType
from kanon.settings import Settings
from kanon.sources import store
from kanon.sources.store import (
    SourceStorageError,
    blob_path,
    clean_filename,
    read_source_bytes,
    store_source,
)

DATA = b"# Decision\n\nWe now reimburse within 45 days.\n"
DIGEST = hashlib.sha256(DATA).hexdigest()

HOSTILE_NAMES = [
    "../../etc/passwd",
    "../escape.md",
    "/etc/cron.d/evil",
    "C:\\Windows\\system32\\evil.md",
    "..\\..\\evil.md",
    "sub/dir/file.md",
    "nul\x00byte.md",
    "new\nline\r\n.md",
    "..",
    ".",
    "",
    "   ",
    "é☕🙂 — ünïcode.md",
    "a" * 1000 + ".md",
]


def count_sources(session):
    return session.scalar(select(func.count()).select_from(Source))


def all_files(root: Path) -> set[Path]:
    return {p for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def storage(tmp_path):
    return tmp_path / "storage"


def test_stored_file_is_byte_identical(db_session, storage):
    source = store_source(db_session, storage, "notes.md", DATA, SourceType.MARKDOWN)

    assert blob_path(storage, source.content_hash).read_bytes() == DATA
    assert read_source_bytes(storage, source) == DATA


def test_binary_and_empty_content_round_trips(db_session, storage):
    for data in (b"", bytes(range(256)) * 100, b"\xff\xfe\x00\r\n\r"):
        source = store_source(db_session, storage, "f.md", data, SourceType.MARKDOWN)
        assert read_source_bytes(storage, source) == data


def test_row_records_hash_path_type_and_cleaned_name(db_session, storage):
    source = store_source(db_session, storage, "notes.md", DATA, SourceType.TRANSCRIPT)

    assert source.content_hash == DIGEST
    assert source.stored_path == f"{DIGEST[:2]}/{DIGEST}"
    assert source.type is SourceType.TRANSCRIPT
    assert source.original_filename == "notes.md"
    assert source.id is not None
    assert count_sources(db_session) == 1


def test_storage_layout_is_sharded_by_hash_prefix(db_session, storage):
    store_source(db_session, storage, "x.md", DATA, SourceType.MARKDOWN)

    assert all_files(storage) == {storage / DIGEST[:2] / DIGEST}


@pytest.mark.parametrize("filename", HOSTILE_NAMES)
def test_the_filename_never_determines_the_storage_path(db_session, tmp_path, filename):
    sandbox = tmp_path / "sandbox"
    storage = sandbox / "storage"

    source = store_source(db_session, storage, filename, DATA, SourceType.MARKDOWN)

    # The only file written anywhere under tmp_path is the blob named by the hash.
    assert all_files(tmp_path) == {storage / DIGEST[:2] / DIGEST}
    assert source.stored_path == f"{DIGEST[:2]}/{DIGEST}"
    assert "\x00" not in source.original_filename
    assert 0 < len(source.original_filename) <= 255
    assert read_source_bytes(storage, source) == DATA


def test_path_separators_survive_only_as_display_text(db_session, storage):
    source = store_source(db_session, storage, "../../etc/passwd", DATA, SourceType.MARKDOWN)
    db_session.expire_all()

    assert db_session.scalars(select(Source.original_filename)).one() == "../../etc/passwd"
    assert ".." not in source.stored_path


def test_different_names_same_bytes_share_one_blob(db_session, storage):
    a = store_source(db_session, storage, "a.md", DATA, SourceType.MARKDOWN)
    b = store_source(db_session, storage, "b.md", DATA, SourceType.MARKDOWN)

    assert a.id != b.id
    assert a.stored_path == b.stored_path
    assert len(all_files(storage)) == 1
    assert count_sources(db_session) == 2


def test_different_bytes_get_different_blobs(db_session, storage):
    a = store_source(db_session, storage, "a.md", b"one", SourceType.MARKDOWN)
    b = store_source(db_session, storage, "a.md", b"two", SourceType.MARKDOWN)

    assert a.stored_path != b.stored_path
    assert len(all_files(storage)) == 2


def test_no_row_is_created_if_the_directory_cannot_be_created(db_session, tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("I am a file, not a directory")

    with pytest.raises(SourceStorageError, match="cannot store file"):
        store_source(db_session, blocker / "storage", "a.md", DATA, SourceType.MARKDOWN)

    assert count_sources(db_session) == 0


def test_no_row_and_no_leftovers_if_the_final_rename_fails(db_session, storage, monkeypatch):
    def broken_replace(src, dst):
        raise OSError("disk exploded")

    monkeypatch.setattr(store.os, "replace", broken_replace)

    with pytest.raises(SourceStorageError, match="disk exploded"):
        store_source(db_session, storage, "a.md", DATA, SourceType.MARKDOWN)

    assert count_sources(db_session) == 0
    assert all_files(storage) == set()  # the temporary file was cleaned up


def test_no_row_if_writing_the_bytes_fails(db_session, storage, monkeypatch):
    real_fsync = os.fsync

    def failing_fsync(fd):
        raise OSError("no space left on device")

    monkeypatch.setattr(store.os, "fsync", failing_fsync)

    with pytest.raises(SourceStorageError, match="no space"):
        store_source(db_session, storage, "a.md", DATA, SourceType.MARKDOWN)

    monkeypatch.setattr(store.os, "fsync", real_fsync)
    assert count_sources(db_session) == 0
    assert all_files(storage) == set()


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_no_row_if_the_directory_is_read_only(db_session, storage):
    storage.mkdir()
    storage.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(SourceStorageError):
            store_source(db_session, storage, "a.md", DATA, SourceType.MARKDOWN)
    finally:
        storage.chmod(stat.S_IRWXU)

    assert count_sources(db_session) == 0


def test_an_existing_blob_is_reused_not_rewritten(db_session, storage, monkeypatch):
    store_source(db_session, storage, "a.md", DATA, SourceType.MARKDOWN)

    def must_not_write(*args, **kwargs):
        raise AssertionError("blob was rewritten")

    monkeypatch.setattr(store.tempfile, "NamedTemporaryFile", must_not_write)
    second = store_source(db_session, storage, "b.md", DATA, SourceType.MARKDOWN)

    assert read_source_bytes(storage, second) == DATA


def test_reading_a_missing_blob_is_a_domain_error(db_session, storage):
    source = store_source(db_session, storage, "a.md", DATA, SourceType.MARKDOWN)
    blob_path(storage, source.content_hash).unlink()

    with pytest.raises(SourceStorageError, match="cannot read"):
        read_source_bytes(storage, source)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("report.md", "report.md"),
        ("a\x00b", "ab"),
        ("tab\there", "tabhere"),
        ("  padded.md  ", "padded.md"),
        ("", "unnamed"),
        ("\x00\x01", "unnamed"),
        ("é☕", "é☕"),
        ("../x", "../x"),
    ],
)
def test_clean_filename(raw, expected):
    assert clean_filename(raw) == expected


def test_clean_filename_bounds_the_length():
    assert len(clean_filename("x" * 5000)) == 255


def test_content_hash_is_sha256_hex():
    assert store.content_hash(DATA) == DIGEST
    assert store.relative_path(DIGEST).count("/") == 1


def test_storage_directory_setting_defaults_and_is_configurable(tmp_path, monkeypatch):
    assert Settings(database_url="postgresql://x/y").source_storage_dir == Path("data/sources")

    monkeypatch.setenv("KANON_DATABASE_URL", "postgresql://x/y")
    monkeypatch.setenv("KANON_SOURCE_STORAGE_DIR", str(tmp_path / "s"))
    assert Settings().source_storage_dir == tmp_path / "s"
