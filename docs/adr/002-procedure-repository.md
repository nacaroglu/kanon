# ADR-002: Procedure repository layout and Markdown conventions

- **Status:** Accepted
- **Date:** 2026-11-20
- **Backlog / issue:** #20 (`REPO-001`)

## Context

Git is the source of truth for approved procedures (Product Scope 1.3, section 6.1, Decision 8). Kanon imports an existing repository (section 2.1), reads it at a specific commit, and later writes approved changes back as commits. People edit these files in ordinary editors; programs split them into sections for retrieval and contradiction detection, and point proposals at exact text.

The convention is therefore a file-based data contract with two kinds of reader. It must be easy to write by hand, and it must be tolerant, because an imported real repository will have little metadata and was not written for Kanon.

## Options considered

### Decision A: Where procedures live

| Option | Trade-off |
|---|---|
| Dedicated `procedures/` directory at the repository root | Unambiguous scope; other files (README, CI config, images) are never mistaken for procedures. Imported repositories must have, or move their Markdown into, that directory. |
| Every `*.md` in the repository | Zero setup for imports; picks up READMEs, changelogs and contribution guides as "procedures". |

### Decision B: Granularity of a file

| Option | Trade-off |
|---|---|
| One procedure per file | Git history, last-change dates and staleness (section 2.5) are per file, so a file maps to exactly one procedure. Many small files. |
| Several procedures per file | Fewer files; file-level history and staleness become ambiguous. |

### Decision C: Metadata

| Option | Trade-off |
|---|---|
| Optional YAML front matter; everything derivable is derived | Real repositories work unchanged; metadata can be added gradually. Some fields may be absent, so every consumer must cope. |
| Required front matter (`id`, `title`, `owner`, ...) | Uniform data; rejects most real repositories on import. |

### Decision D: What counts as a section

| Option | Trade-off |
|---|---|
| Every heading starts a new, flat section | One rule that can be applied by hand; small, precise retrieval units. A parent heading's section holds only its own introduction. |
| Split only at level 1–3 headings | Larger units; needs a second rule for "deeper" headings and for which level is the cut-off. |
| Hierarchical sections (a section contains its subsections) | Matches document structure; sections overlap, so offsets and "exact text" stop being unique. |

## Decision

### 1. Layout

- Approved procedures live under the **`procedures/`** directory at the repository root, at any depth.
- A procedure is a file whose name ends in lowercase **`.md`** inside that directory. Other files there (images, `.txt`) and Markdown files outside the directory (for example the root `README.md`) are not procedures.
- **One procedure per file.** A procedure's identity is its path relative to the repository root, for example `procedures/expense-reports.md`. A rename is a new procedure in v1.
- Files are UTF-8. Kanon reads committed content only, never the working directory.

### 2. Metadata

Required, and always resolvable for any file:

| Field | Source |
|---|---|
| Path | Git tree entry. |
| Title | The text of the first level-1 heading (`# Title`) that is outside front matter and code fences; otherwise the file name without `.md`. |

Optional YAML front matter. Kanon never rejects a file because a field is missing, and ignores unknown keys:

| Field | Meaning |
|---|---|
| `owner` | Person or team responsible for the procedure. |
| `tags` | List of short labels used for filtering. |
| `summary` | One-sentence description. |

The date of a procedure's last approved change is **not** metadata. It is taken from the Git history of the file (section 2.5).

Front matter is the block at the very start of the file that begins with a line that is exactly `---` and ends at the next line that is exactly `---`. If the first line is `---` but no closing line follows, there is no front matter and the line is ordinary content.

### 3. Sections

A **section** is the unit of retrieval and of proposal targeting. The rule below is applied to the file text after the front matter (if any). It is purely textual and needs no Markdown renderer.

1. **Lines.** Lines end with `\n` or `\r\n`. A line start is offset 0 or the offset just after a line terminator.
2. **Code fences.** A line that starts with three or more backticks, or three or more tildes, opens a fenced code block. It closes at the next line that starts with the same character repeated at least as many times. An unclosed fence runs to the end of the file. Lines inside a fence are never headings.
3. **Headings.** A heading is a line outside a fence that starts at column 0 with one to six `#`, then at least one space or tab, then text. Closing `#` characters (a run of `#` preceded by a space or tab at the end of the line) and surrounding whitespace are not part of the heading text. A line whose text is blank is not a heading. `#hashtag` and indented lines are not headings. Setext headings (underlined with `===` or `---`) are not recognised.
4. **Splitting.** Every heading starts a new section, regardless of its level. A section runs from the start of its heading line to the start of the next heading line, or to the end of the file. Sections are flat: nested headings produce separate, non-overlapping sections.
5. **Preamble.** Text between the end of the front matter (or the start of the file) and the first heading forms an extra section with no heading. It exists only if it contains a non-whitespace character. A file with no headings therefore has exactly one section if it has any text, and none if it is blank.
6. **Offsets.** A section records `start` and `end` as character offsets (Unicode code points, `end` exclusive) into the original file text, so that `text[start:end]` reproduces the section exactly, including its trailing blank lines. Sections are contiguous after the first one: each section's `end` is the next section's `start`.

### 4. Example

`procedures/expense-reports.md`:

```markdown
---
owner: Finance Operations
tags: [finance, expenses]
---

# Expense Reports

Employees submit expense reports so that the company can reimburse
business costs.

## Submission deadline

Submit each report within 30 days of the expense date.

## Approval

Reports under 500 EUR are approved by the employee's manager.

### Reports over the limit

Reports of 500 EUR or more also require approval from the finance team.
```

Applying the rules: the title is `Expense Reports` (rule in section 2). The front matter is lines 1–4. The only text before the first heading is the blank line 5, so there is no preamble section (rule 5). Lines 6, 11, 15 and 19 are headings. The result is four sections:

| # | Heading | Level | Lines |
|---|---|---|---|
| 1 | Expense Reports | 1 | 6–10 |
| 2 | Submission deadline | 2 | 11–14 |
| 3 | Approval | 2 | 15–18 |
| 4 | Reports over the limit | 3 | 19–21 |

Section 3 ends where section 4 begins, even though section 4 is nested under it.

## Consequences

- A repository that keeps its Markdown elsewhere must move it under `procedures/` (or a later ADR makes the directory configurable) before import.
- Sections can be tiny, for example a title heading followed immediately by a subheading. Retrieval has to tolerate that, or later merge sections for display.
- Because offsets index the original text, proposals can target exact ranges and be checked against the commit they were made for. Offsets are only valid for the exact file version they were computed from.
- Indented headings and Setext headings are deliberately not recognised. A repository that uses them yields fewer, larger sections but is never rejected.
- Revisit if real imported repositories commonly use Setext or indented headings, or if hierarchical context turns out to matter for retrieval quality.
