#!/usr/bin/env python3
"""Join soft-wrapped Markdown into logical lines.

Prose in this repository is hard-wrapped at about 80 columns, so a sentence
routinely spans two physical lines. A detector that reads one physical line at a
time then sees fragments — and any rule that depends on words appearing near
each other breaks in both directions:

  * **False positive.** "You do not\\nmerge it." — the negation is on the
    previous line, so the second line reads as a permission. This was a real
    failure of the authority guard, caught by its own test suite.
  * **False negative.** "the SomeProvider\\nWorker" — the compound never appears
    on one line, so a lane-identity rule misses it.

`logical_lines` joins continuation lines within a paragraph or a list item, and
keeps genuinely separate block elements — table rows, headings, fence lines,
block quotes, list item starts — apart. Each result carries the physical line
number where it began, so findings still point at a real place in the file.
"""

from __future__ import annotations

import re

__all__ = ["logical_lines", "counterexample_blocks", "negated", "NEGATORS",
           "COUNTEREXAMPLE_OPEN", "COUNTEREXAMPLE_CLOSE"]

#: A normative document sometimes needs to quote a banned form in order to
#: prohibit it, or to name what a guard catches. Wrap it:
#:
#:     <!-- guard:counterexample -->
#:     ... text that SHOULD be rejected ...
#:     <!-- /guard:counterexample -->
#:
#: Findings inside are suppressed, but callers still get the blocks back so they
#: can assert every block actually contains something the guard rejects. An
#: exemption that protects nothing is a silent widening.
COUNTEREXAMPLE_OPEN = "<!-- guard:counterexample -->"
COUNTEREXAMPLE_CLOSE = "<!-- /guard:counterexample -->"

#: A line that begins a new block element rather than continuing the previous
#: one. Table rows and list items must stay separate: joining them would let a
#: negation in one row silence a permission in the next.
BLOCK_START = re.compile(
    r"^\s*(?:[-*+]\s+"          # bullet list item
    r"|\d+[.)]\s+"              # ordered list item
    r"|\|"                      # table row
    r"|#{1,6}\s"                # heading
    r"|>"                       # block quote
    r"|```|~~~"                 # fence
    r"|<!--"                    # html comment / marker
    r")"
)
FENCE = re.compile(r"^\s*(?:```|~~~)")
#: A line that is nothing but an HTML comment is a marker, not prose. It must
#: not absorb the line after it: doing so made a counterexample body share a
#: logical line with its opening marker, so suppression keyed on the body's line
#: number missed it.
STANDALONE_COMMENT = re.compile(r"^\s*<!--.*-->\s*$")


def logical_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(starting_physical_line_number, joined_text)`` pairs.

    Content inside fenced code blocks is returned line by line, unjoined: code
    is not prose and joining it would invent adjacency that is not there.
    """
    out: list[tuple[int, str]] = []
    start: int | None = None
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal start, buf
        if start is not None and buf:
            out.append((start, " ".join(s.strip() for s in buf).strip()))
        start, buf = None, []

    for n, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            flush()
            out.append((n, line))
            in_fence = not in_fence
            continue
        if in_fence:
            out.append((n, line))
            continue
        if not line.strip():
            flush()
            continue
        if STANDALONE_COMMENT.match(line):
            flush()
            out.append((n, line))
            continue
        if BLOCK_START.match(line):
            flush()
            start, buf = n, [line]
            continue
        if start is None:
            start, buf = n, [line]
        else:
            buf.append(line)
    flush()
    return out


def counterexample_blocks(text: str) -> tuple[list[tuple[int, str]], set[int]]:
    """Return ``(blocks, suppressed_physical_line_numbers)``.

    ``blocks`` is a list of ``(1-indexed start line, block text)``. Marker lines
    themselves are not suppressed, only the bodies.
    """
    blocks: list[tuple[int, str]] = []
    suppressed: set[int] = set()
    start: int | None = None
    body: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped == COUNTEREXAMPLE_OPEN:
            start, body = n, []
            continue
        if stripped == COUNTEREXAMPLE_CLOSE:
            if start is not None:
                blocks.append((start, '\n'.join(body)))
            start, body = None, []
            continue
        if start is not None:
            body.append(line)
            suppressed.add(n)
    if start is not None:  # unclosed: treat what we have as a block
        blocks.append((start, '\n'.join(body)))
    return blocks, suppressed


#: Words that turn a statement about a thing into a statement PROHIBITING it.
#: Both guards need this: correct documents talk about merging and about queues
#: constantly, in the form "never merges", "no queue", "may not merge". A match
#: preceded by one of these is the shape we want to see, not a violation.
#: Word boundaries are load-bearing: without them "another" contains
#: "not" and "nonetheless" contains "none", so half the prose in a
#: normative document would silently count as a prohibition and the guards
#: would stop reporting anything. tests/test_guard_honesty.py pins this.
NEGATORS = re.compile(
    r"\b(never|not|no|nor|none|cannot|can't|don't|doesn't|won't|must\s+not"
    r"|may\s+not|is\s+not|are\s+not|does\s+not|do\s+not|without|prohibit\w*"
    r"|forbid\w*|refuse[sd]?|prevent[sd]?|prevents|stops?|stopped|reject[sed]*"
    r"|rather\s+than|instead\s+of|avoids?|avoided|stale|superseded|obsolete)\b",
    re.IGNORECASE,
)


def negated(line: str, start: int) -> bool:
    """True if a match at ``start`` is part of a prohibition, not a permission."""
    return bool(NEGATORS.search(line[:start]))
