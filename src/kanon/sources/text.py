"""Turn a stored Markdown source into the one canonical text that claims are traced against.

Claims extracted from a source later quote it, and a quote is only verifiable if every reader
sees exactly the same characters. So normalization is a pure, deterministic function of the
stored bytes, and the normalized text is *reproduced* on demand rather than stored: there is
nothing to get out of sync with the file.

Rules, applied in this order:

1. Decode as strict UTF-8. Anything else is an error, never silently repaired.
2. Drop one leading byte order mark (U+FEFF); it is an encoding artefact, not content.
3. Line endings become "\\n": "\\r\\n" and a lone "\\r" are both converted.
4. Unicode is put in NFC, so a composed "é" and "e" + combining accent compare equal.

Nothing else is touched. Whitespace, trailing spaces, blank lines and a missing final newline
are all preserved.

If these rules ever change, offsets recorded against the old text stop being valid, so bump
`NORMALIZATION_VERSION` and treat older recorded offsets as stale.
"""

import unicodedata
from pathlib import Path

from kanon.models import Source, SourceType
from kanon.sources.store import read_source_bytes

NORMALIZATION_VERSION = 1
_BOM = "﻿"


class SourceTextError(Exception):
    """The source cannot be turned into text."""


class InvalidEncodingError(SourceTextError):
    """The file is not valid UTF-8."""


class UnsupportedSourceTypeError(SourceTextError):
    """Only Markdown sources are read in this slice."""


def normalize_text(raw: bytes) -> str:
    """The canonical text of `raw`. Deterministic: the same bytes always give the same text."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidEncodingError(
            f"not valid UTF-8 (invalid byte at offset {error.start})"
        ) from None
    text = text.removeprefix(_BOM)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return unicodedata.normalize("NFC", text)


def read_source_text(storage_dir: Path, source: Source) -> str:
    """The normalized text of a stored Markdown source."""
    if source.type is not SourceType.MARKDOWN:
        raise UnsupportedSourceTypeError(
            f"cannot read a {source.type.value!r} source as text yet; only Markdown is supported"
        )
    try:
        return normalize_text(read_source_bytes(storage_dir, source))
    except InvalidEncodingError as error:
        raise InvalidEncodingError(f"source {source.id}: {error}") from None
