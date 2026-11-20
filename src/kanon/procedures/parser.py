"""Split a procedure file into a title and flat sections, exactly as ADR-002 defines.

Pure and dependency-free: text in, data out. Offsets are character (code point) offsets into
the text that was passed in, so `text[section.start:section.end]` always reproduces a section.
"""

import re
from dataclasses import dataclass

_LINE = re.compile(r"[^\n]*\n|[^\n]+")  # lines end with "\n" (a preceding "\r" is allowed)
_FENCE = re.compile(r"(`{3,}|~{3,})")
_HEADING = re.compile(r"(#{1,6})[ \t]+(.*)")
_CLOSING_HASHES = re.compile(r"[ \t]+#+$")
FRONT_MATTER_DELIMITER = "---"


@dataclass(frozen=True)
class Section:
    heading: str | None  # None only for the preamble (text before the first heading)
    level: int | None  # 1-6; None for the preamble
    start: int  # offset of the first character, inclusive
    end: int  # offset after the last character, exclusive
    text: str  # text[start:end] of the parsed file

    def __post_init__(self) -> None:
        if not 0 <= self.start <= self.end:
            raise ValueError(f"invalid section offsets: {self.start}..{self.end}")


@dataclass(frozen=True)
class ParsedProcedure:
    title: str
    sections: tuple[Section, ...]


def parse_procedure(text: str, *, default_title: str) -> ParsedProcedure:
    """Parse a procedure file.

    `default_title` is used when the file has no level-1 heading; callers pass the file name
    without its extension.
    """
    lines = [(m.start(), m.end(), _content(m.group())) for m in _LINE.finditer(text)]
    body_start, first_body_line = _front_matter_end(lines)

    headings: list[tuple[int, int, str]] = []  # (offset, level, heading text)
    fence: str | None = None  # the fence's opening marker while inside a fenced block
    for offset, _, content in lines[first_body_line:]:
        if fence is not None:
            if content.startswith(fence[0] * len(fence)):
                fence = None
            continue
        if opening := _FENCE.match(content):
            fence = opening.group(1)
            continue
        if heading := _heading(content):
            headings.append((offset, *heading))

    sections: list[Section] = []
    first_heading = headings[0][0] if headings else len(text)
    if text[body_start:first_heading].strip():
        sections.append(
            Section(None, None, body_start, first_heading, text[body_start:first_heading])
        )
    for i, (offset, level, heading_text) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        sections.append(Section(heading_text, level, offset, end, text[offset:end]))

    title = next((h for _, level, h in headings if level == 1), default_title)
    return ParsedProcedure(title=title, sections=tuple(sections))


def _content(line: str) -> str:
    """The line without its terminator: "\\n" or "\\r\\n". A lone "\\r" is ordinary text."""
    return line.removesuffix("\n").removesuffix("\r") if line.endswith("\n") else line


def _front_matter_end(lines: list[tuple[int, int, str]]) -> tuple[int, int]:
    """(character offset, line index) where the body starts, after any front matter."""
    if lines and lines[0][2] == FRONT_MATTER_DELIMITER:
        for index in range(1, len(lines)):
            if lines[index][2] == FRONT_MATTER_DELIMITER:
                return lines[index][1], index + 1
    return 0, 0  # absent, or never closed: the first "---" is ordinary content


def _heading(line: str) -> tuple[int, str] | None:
    match = _HEADING.fullmatch(line)
    if not match:
        return None
    text = _CLOSING_HASHES.sub("", match.group(2).strip(" \t"))
    if not text:
        return None
    return len(match.group(1)), text
