import random
from pathlib import Path

import pytest

from kanon.procedures.parser import ParsedProcedure, Section, parse_procedure
from kanon.procedures.repository import ProcedureRepository


def parse(text: str) -> ParsedProcedure:
    return parse_procedure(text, default_title="fallback")


def outline(text: str) -> list[tuple[str | None, int | None, str]]:
    """(heading, level, text) for each section."""
    return [(s.heading, s.level, s.text) for s in parse(text).sections]


def assert_offsets_reproduce_text(text: str) -> None:
    sections = parse(text).sections
    for s in sections:
        assert text[s.start : s.end] == s.text
    for before, after in zip(sections, sections[1:], strict=False):
        assert before.end == after.start  # contiguous, never overlapping


# --- Table-driven cases --------------------------------------------------------------------

CASES = {
    "empty file": ("", []),
    "whitespace only": ("  \n\n\t\n", []),
    "no headings is one section": (
        "Just some text.\nMore text.\n",
        [(None, None, "Just some text.\nMore text.\n")],
    ),
    "no headings, no trailing newline": ("one line", [(None, None, "one line")]),
    "single heading": ("# Only\n", [("Only", 1, "# Only\n")]),
    "heading without trailing newline": ("# Only", [("Only", 1, "# Only")]),
    "preamble before first heading": (
        "Intro.\n\n# Title\nBody\n",
        [(None, None, "Intro.\n\n"), ("Title", 1, "# Title\nBody\n")],
    ),
    "blank preamble is dropped": ("\n\n# Title\nBody\n", [("Title", 1, "# Title\nBody\n")]),
    "nested headings are flat sections": (
        "# A\na\n## B\nb\n### C\nc\n## D\nd\n",
        [
            ("A", 1, "# A\na\n"),
            ("B", 2, "## B\nb\n"),
            ("C", 3, "### C\nc\n"),
            ("D", 2, "## D\nd\n"),
        ],
    ),
    "adjacent headings give a heading-only section": (
        "# A\n## B\ntext\n",
        [("A", 1, "# A\n"), ("B", 2, "## B\ntext\n")],
    ),
    "levels one to six": (
        "# 1\n## 2\n### 3\n#### 4\n##### 5\n###### 6\n",
        [(str(n), n, f"{'#' * n} {n}\n") for n in range(1, 7)],
    ),
    "seven hashes is not a heading": ("####### seven\n", [(None, None, "####### seven\n")]),
    "no space after hashes is not a heading": ("#hashtag\n", [(None, None, "#hashtag\n")]),
    "indented hashes are not a heading": ("  # indented\n", [(None, None, "  # indented\n")]),
    "tab after hashes is a heading": ("#\tTabbed\n", [("Tabbed", 1, "#\tTabbed\n")]),
    "blank heading text is not a heading": ("# \n#\n", [(None, None, "# \n#\n")]),
    "setext headings are not recognised": (
        "Title\n=====\n\nBody\n-----\n",
        [(None, None, "Title\n=====\n\nBody\n-----\n")],
    ),
    "backtick fence hides headings": (
        "# A\n```\n# not a heading\n```\n# B\n",
        [("A", 1, "# A\n```\n# not a heading\n```\n"), ("B", 1, "# B\n")],
    ),
    "tilde fence hides headings": (
        "# A\n~~~\n# no\n~~~\nafter\n",
        [("A", 1, "# A\n~~~\n# no\n~~~\nafter\n")],
    ),
    "longer fence is not closed by a shorter one": (
        "# A\n````\n```\n# no\n```\n````\n# B\n",
        [("A", 1, "# A\n````\n```\n# no\n```\n````\n"), ("B", 1, "# B\n")],
    ),
    "other fence character does not close": (
        "# A\n```\n~~~\n# no\n```\n# B\n",
        [("A", 1, "# A\n```\n~~~\n# no\n```\n"), ("B", 1, "# B\n")],
    ),
    "unclosed fence runs to the end": (
        "# A\n```\n# no\n## still no\n",
        [("A", 1, "# A\n```\n# no\n## still no\n")],
    ),
    "front matter is excluded": (
        "---\nowner: x\n---\n# T\nbody\n",
        [("T", 1, "# T\nbody\n")],
    ),
    "front matter followed by text is a preamble": (
        "---\nowner: x\n---\nintro\n# T\n",
        [(None, None, "intro\n"), ("T", 1, "# T\n")],
    ),
    "headings inside front matter are ignored": (
        "---\n# comment\n---\n# Real\n",
        [("Real", 1, "# Real\n")],
    ),
    "unclosed front matter is ordinary content": (
        "---\nfoo\n# T\n",
        [(None, None, "---\nfoo\n"), ("T", 1, "# T\n")],
    ),
    "front matter must start the file": (
        "\n---\nfoo\n---\n",
        [(None, None, "\n---\nfoo\n---\n")],
    ),
    "front matter only": ("---\nowner: x\n---\n", []),
    "crlf line endings": (
        "# A\r\nbody\r\n## B\r\nmore\r\n",
        [("A", 1, "# A\r\nbody\r\n"), ("B", 2, "## B\r\nmore\r\n")],
    ),
    "crlf front matter": (
        "---\r\nowner: x\r\n---\r\n# T\r\n",
        [("T", 1, "# T\r\n")],
    ),
    "lone carriage return is not a line break": (
        "# A\rnot heading\r",
        [("A\rnot heading\r", 1, "# A\rnot heading\r")],
    ),
}


@pytest.mark.parametrize(("text", "expected"), CASES.values(), ids=CASES.keys())
def test_sections(text, expected):
    assert outline(text) == expected
    assert_offsets_reproduce_text(text)


@pytest.mark.parametrize(
    ("line", "heading"),
    [
        ("## Title ##", "Title"),
        ("## Title ##  ", "Title"),
        ("### C#", "C#"),  # not preceded by whitespace: part of the text
        ("# Title#", "Title#"),
        ("#  ##", "##"),  # nothing before the hashes: they are the text
        ("#   spaced   out   ", "spaced   out"),
        ("# **Bold** and `code`", "**Bold** and `code`"),
    ],
)
def test_heading_text(line, heading):
    (section,) = parse(line + "\n").sections
    assert section.heading == heading


# --- Offsets ---------------------------------------------------------------------------------


def test_offsets_of_a_small_file_are_exact():
    text = "---\na: b\n---\n\n# One\nx\n## Two\ny\n"

    sections = parse(text).sections

    assert [(s.start, s.end) for s in sections] == [(14, 22), (22, 31)]
    assert text[14:22] == "# One\nx\n"
    assert text[22:31] == "## Two\ny\n"


def test_preamble_starts_right_after_front_matter():
    text = "---\na: b\n---\n\nintro\n# T\n"

    preamble, _ = parse(text).sections

    assert preamble.start == len("---\na: b\n---\n")
    assert preamble.text == "\nintro\n"


def test_offsets_count_characters_not_bytes():
    text = "# Café ☕\nbody 🙂\n## Düsseldorf\nend\n"

    sections = parse(text).sections

    assert [s.text for s in sections] == ["# Café ☕\nbody 🙂\n", "## Düsseldorf\nend\n"]
    assert sections[1].start == len("# Café ☕\nbody 🙂\n")
    assert len(text.encode()) != len(text)  # the test is meaningful


def test_offsets_always_reproduce_the_original_text():
    pool = [
        "# H1", "## H2", "### H3", "text", "", "  ", "```", "~~~", "````", "---", "#hash",
        "  # indented", "# ", "## T ##", "Title", "=====", "é☕🙂", "\t", "####### x",
    ]  # fmt: skip
    rng = random.Random(1234)
    for _ in range(500):
        newline = rng.choice(["\n", "\r\n"])
        lines = [rng.choice(pool) for _ in range(rng.randint(0, 12))]
        text = newline.join(lines) + rng.choice(["", newline])

        assert_offsets_reproduce_text(text)
        sections = parse(text).sections
        # Every section but the first ends where the next begins, and the last one ends the file.
        if sections:
            assert sections[-1].end == len(text)


def test_section_with_negative_offsets_is_rejected():
    with pytest.raises(ValueError):
        Section("x", 1, 5, 2, "")


# --- Title -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "title"),
    [
        ("# Real Title\n", "Real Title"),
        ("Intro\n\n## Sub\n# Late H1\n", "Late H1"),
        ("# First\n# Second\n", "First"),
        ("## Only H2\n", "fallback"),
        ("no headings\n", "fallback"),
        ("", "fallback"),
        ("```\n# in fence\n```\n", "fallback"),
        ("---\n# yaml comment\n---\ntext\n", "fallback"),
        ("---\ntitle: ignored\n---\n# Heading\n", "Heading"),
    ],
)
def test_title(text, title):
    assert parse(text).title == title


# --- The fixture files -------------------------------------------------------------------------


def lines_of(text: str, section: Section) -> tuple[int, int]:
    """1-based first and last line of a section."""
    return text[: section.start].count("\n") + 1, text[: section.end].count("\n")


def parse_fixture(sample_repo, name):
    with ProcedureRepository(sample_repo.path) as repo:
        file = next(f for f in repo.list_procedure_files() if f.path.endswith(name))
    parsed = parse_procedure(file.content, default_title=Path(file.path).stem)
    return file.content, parsed


def test_expense_reports_matches_the_adr_table(sample_repo):
    text, parsed = parse_fixture(sample_repo, "expense-reports.md")

    assert parsed.title == "Expense Reports"
    assert [(s.heading, s.level, lines_of(text, s)) for s in parsed.sections] == [
        ("Expense Reports", 1, (6, 10)),
        ("Submission deadline", 2, (11, 14)),
        ("Approval", 2, (15, 18)),
        ("Reports over the limit", 3, (19, 21)),
    ]


def test_remote_work_without_front_matter(sample_repo):
    text, parsed = parse_fixture(sample_repo, "remote-work.md")

    assert parsed.title == "Remote Work"
    assert [(s.heading, lines_of(text, s)) for s in parsed.sections] == [
        ("Remote Work", (1, 4)),
        ("Eligibility", (5, 8)),
        ("Equipment", (9, 11)),
    ]


def test_incident_response_ignores_the_heading_inside_the_code_fence(sample_repo):
    text, parsed = parse_fixture(sample_repo, "incident-response.md")

    assert parsed.title == "Incident Response"
    assert [(s.heading, lines_of(text, s)) for s in parsed.sections] == [
        ("Incident Response", (6, 9)),
        ("Declaring an incident", (10, 20)),
        ("Escalation", (21, 23)),
    ]
    assert "# Incident: <service>" in parsed.sections[1].text


def test_every_fixture_section_slices_back_to_the_original(sample_repo):
    with ProcedureRepository(sample_repo.path) as repo:
        files = repo.list_procedure_files()

    for file in files:
        parsed = parse_procedure(file.content, default_title="x")
        assert parsed.sections
        for s in parsed.sections:
            assert file.content[s.start : s.end] == s.text
