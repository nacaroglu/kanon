import unicodedata

import pytest

from kanon.models import SourceType
from kanon.sources.store import SourceStorageError, blob_path, store_source
from kanon.sources.text import (
    InvalidEncodingError,
    SourceTextError,
    UnsupportedSourceTypeError,
    normalize_text,
    read_source_text,
)

COMPOSED = "café"  # é as one code point
DECOMPOSED = "café"  # e + combining acute accent


# --- Determinism -------------------------------------------------------------------------


def test_same_bytes_always_give_the_same_text():
    raw = "# Titel\r\n\r\nGrüße — ☕\r\n".encode()

    assert len({normalize_text(raw) for _ in range(20)}) == 1


def test_normalization_is_idempotent():
    raw = f"a\r\nb\rc\n{DECOMPOSED}\r\n".encode()
    once = normalize_text(raw)

    assert normalize_text(once.encode()) == once


# --- Line endings ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (b"a\r\nb\r\nc", "a\nb\nc"),
        (b"a\rb\rc", "a\nb\nc"),
        (b"a\nb\nc", "a\nb\nc"),
        (b"a\r\nb\rc\nd", "a\nb\nc\nd"),
        (b"a\r\n\r\nb", "a\n\nb"),
        (b"a\r\r\nb", "a\n\nb"),  # a lone CR followed by CRLF is two breaks, not three
        (b"line\r\n", "line\n"),
        (b"\r\n", "\n"),
    ],
)
def test_line_endings_become_lf(raw, expected):
    assert normalize_text(raw) == expected


def test_windows_and_unix_versions_of_a_file_give_identical_text():
    unix = b"# Title\n\nBody text.\n\n- item\n"
    windows = unix.replace(b"\n", b"\r\n")
    old_mac = unix.replace(b"\n", b"\r")

    assert normalize_text(unix) == normalize_text(windows) == normalize_text(old_mac)


def test_other_unicode_line_separators_are_left_alone():
    text = "a b c\x0bd\x0ce\x85f"

    assert normalize_text(text.encode()) == text


# --- Unicode form ------------------------------------------------------------------------


def test_composed_and_decomposed_characters_normalize_to_the_same_text():
    assert COMPOSED != DECOMPOSED  # visually identical, different strings
    assert len(COMPOSED) != len(DECOMPOSED)

    assert normalize_text(COMPOSED.encode()) == normalize_text(DECOMPOSED.encode()) == COMPOSED


def test_result_is_nfc():
    text = normalize_text("Amélie, Å Å, ﬁ, 한국어, 가".encode())

    assert unicodedata.is_normalized("NFC", text)


def test_nfc_does_not_apply_compatibility_folding():
    # NFKC would turn the ligature and the fullwidth letter into plain text; NFC must not.
    text = "ﬁ Ａ ② ½"

    assert normalize_text(text.encode()) == text


def test_a_quote_taken_from_the_text_is_found_in_it():
    text = normalize_text(f"Rule:\r\n{DECOMPOSED} must be approved.\r\n".encode())
    quote = f"{COMPOSED} must be approved."

    start = text.index(quote)
    assert text[start : start + len(quote)] == quote


# --- Nothing is stripped -----------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "  leading spaces",
        "trailing spaces   \n",
        "\n\n\nleading blank lines",
        "trailing blank lines\n\n\n",
        "no final newline",
        "tabs\tinside\t\n",
        " nbsp  and ​ zero width ​",
        "",
        "\n",
        "   ",
        "trailing two spaces  \nare a Markdown line break\n",
    ],
)
def test_content_is_preserved(text):
    assert normalize_text(text.encode()) == text


def test_markdown_structure_is_untouched():
    markdown = "---\ntitle: x\n---\n\n# H\n\n```\ncode  \n```\n\n> quote\n"

    assert normalize_text(markdown.encode()) == markdown


# --- Byte order mark ---------------------------------------------------------------------


def test_a_leading_bom_is_dropped():
    assert normalize_text(b"\xef\xbb\xbf# Title\n") == "# Title\n"


def test_only_one_leading_bom_is_dropped_and_none_in_the_middle():
    assert normalize_text(b"\xef\xbb\xbf\xef\xbb\xbfx") == "﻿x"
    assert normalize_text("a﻿b".encode()) == "a﻿b"


# --- Invalid encoding --------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff\xfe\x00",
        b"ok so far \x80 then bad",
        "truncated é".encode()[:-1],
        "hello".encode("utf-16"),
        "café".encode("latin-1"),
        b"\xed\xa0\x80",  # a UTF-16 surrogate encoded in UTF-8
        b"\xc0\xaf",  # overlong encoding
    ],
)
def test_invalid_utf8_raises_a_domain_error(raw):
    with pytest.raises(InvalidEncodingError, match="not valid UTF-8") as error:
        normalize_text(raw)

    assert isinstance(error.value, SourceTextError)
    assert not isinstance(error.value, UnicodeDecodeError)


def test_the_error_says_where_the_bad_byte_is():
    with pytest.raises(InvalidEncodingError, match="offset 6"):
        normalize_text(b"hello \xff")


# --- Reading a stored source -------------------------------------------------------------


def test_read_source_text_normalizes_the_stored_file(db_session, tmp_path):
    raw = f"# Politique\r\n\r\n{DECOMPOSED}\r\n".encode()
    source = store_source(db_session, tmp_path, "p.md", raw, SourceType.MARKDOWN)

    assert read_source_text(tmp_path, source) == f"# Politique\n\n{COMPOSED}\n"


def test_the_stored_bytes_are_not_modified_by_reading(db_session, tmp_path):
    raw = b"a\r\nb\r\n"
    source = store_source(db_session, tmp_path, "p.md", raw, SourceType.MARKDOWN)

    read_source_text(tmp_path, source)

    assert blob_path(tmp_path, source.content_hash).read_bytes() == raw


def test_reading_twice_gives_the_same_text(db_session, tmp_path):
    source = store_source(db_session, tmp_path, "p.md", b"x\r\ny", SourceType.MARKDOWN)

    assert read_source_text(tmp_path, source) == read_source_text(tmp_path, source)


def test_invalid_encoding_in_a_stored_source_names_the_source(db_session, tmp_path):
    source = store_source(db_session, tmp_path, "p.md", b"\xff\xfe", SourceType.MARKDOWN)

    with pytest.raises(InvalidEncodingError, match=str(source.id)):
        read_source_text(tmp_path, source)


def test_other_types_are_not_supported_yet(db_session, tmp_path):
    source = store_source(db_session, tmp_path, "p.txt", b"plain", SourceType.TXT)

    with pytest.raises(UnsupportedSourceTypeError, match="txt"):
        read_source_text(tmp_path, source)


def test_a_missing_file_is_a_storage_error_not_a_crash(db_session, tmp_path):
    source = store_source(db_session, tmp_path, "p.md", b"x", SourceType.MARKDOWN)
    blob_path(tmp_path, source.content_hash).unlink()

    with pytest.raises(SourceStorageError):
        read_source_text(tmp_path, source)
