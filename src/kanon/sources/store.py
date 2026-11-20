"""Content-addressed storage for submitted source files.

A file is stored once, under a path derived only from the SHA-256 of its bytes:

    <storage_dir>/<first two hex digits>/<64 hex digits>

The submitter's filename is untrusted text. It is recorded in the database for display and is
never used to build a path, so it cannot point the write anywhere (`../../etc/cron.d/x`,
absolute paths, drive letters, NUL bytes and so on all end up as inert text).
"""

import hashlib
import os
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from kanon.models import Source, SourceType

MAX_FILENAME_LENGTH = 255
UNNAMED = "unnamed"


class SourceStorageError(Exception):
    """The file could not be written; no source row was created."""


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_path(digest: str) -> str:
    """Where a blob lives, relative to the storage directory (always "/"-separated)."""
    return f"{digest[:2]}/{digest}"


def blob_path(storage_dir: Path, digest: str) -> Path:
    return Path(storage_dir) / digest[:2] / digest


def clean_filename(filename: str) -> str:
    """Make an untrusted filename safe to store and show: no control characters, bounded size.

    The result is still arbitrary text (it may contain `/` or `..`); that is fine because it is
    never used as a path.
    """
    cleaned = "".join(ch for ch in filename if ch.isprintable()).strip()
    return cleaned[:MAX_FILENAME_LENGTH] or UNNAMED


def store_source(
    session: Session,
    storage_dir: Path,
    filename: str,
    data: bytes,
    source_type: SourceType,
) -> Source:
    """Write `data` under its hash and record it as a source.

    The file is written first and the row added only afterwards, so a failed write leaves no row.
    A failed insert can leave an unreferenced blob behind; that is harmless (the name is the
    content's hash, so another submission of the same bytes would reuse it) and is never deleted
    here because a concurrent submission may already depend on it.
    """
    digest = content_hash(data)
    _write_blob(blob_path(storage_dir, digest), data)

    source = Source(
        original_filename=clean_filename(filename),
        content_hash=digest,
        stored_path=relative_path(digest),
        type=source_type,
    )
    session.add(source)
    session.flush()
    return source


def read_source_bytes(storage_dir: Path, source: Source) -> bytes:
    """The exact bytes that were submitted."""
    path = blob_path(storage_dir, source.content_hash)
    try:
        return path.read_bytes()
    except OSError as error:
        raise SourceStorageError(f"cannot read stored source {source.id}: {error}") from error


def _write_blob(path: Path, data: bytes) -> None:
    """Create `path` with exactly `data`, atomically; do nothing if the blob already exists."""
    if path.is_file():
        return  # same name means same hash means same bytes
    temp_name: str | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write beside the destination, then rename: readers never see a half-written blob.
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".tmp-", delete=False) as temp:
            temp_name = temp.name
            temp.write(data)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    except OSError as error:
        if temp_name is not None:
            Path(temp_name).unlink(missing_ok=True)
        raise SourceStorageError(f"cannot store file: {error}") from error
