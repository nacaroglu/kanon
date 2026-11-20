"""Submit a source file: validate it, store it, record it. No CLI or HTTP concerns here."""

import uuid
from dataclasses import dataclass
from pathlib import Path

from kanon.db import session_scope
from kanon.models import SourceType
from kanon.settings import get_settings
from kanon.sources.store import store_source
from kanon.sources.text import SourceTextError, normalize_text

MARKDOWN_SUFFIXES = (".md", ".markdown")


class SubmissionError(Exception):
    """The file was rejected; nothing was stored."""


@dataclass(frozen=True)
class SubmittedSource:
    id: uuid.UUID
    original_filename: str
    content_hash: str


def submit_markdown(path: Path) -> SubmittedSource:
    """Store a Markdown file as a new source and return its identifier."""
    path = Path(path)
    if path.suffix.lower() not in MARKDOWN_SUFFIXES:
        shown = path.suffix or "(no extension)"
        raise SubmissionError(
            f"unsupported file type {shown}: only Markdown files (.md) can be submitted for now"
        )
    if not path.is_file():
        raise SubmissionError(f"file not found: {path}")
    try:
        data = path.read_bytes()
    except OSError as error:
        raise SubmissionError(f"cannot read {path}: {error.strerror or error}") from error
    try:
        normalize_text(data)  # reject now what could never be read back later
    except SourceTextError as error:
        raise SubmissionError(f"{path}: {error}") from error

    with session_scope() as session:
        source = store_source(
            session,
            get_settings().source_storage_dir,
            path.name,
            data,
            SourceType.MARKDOWN,
        )
        return SubmittedSource(source.id, source.original_filename, source.content_hash)
