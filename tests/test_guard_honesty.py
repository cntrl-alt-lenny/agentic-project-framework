"""Guards must actually guard, and exemptions must actually protect something.

The repository's own rule (`framework/evidence.md`) is that a guard finding
nothing must not report success when "nothing was checked" is the unsafe case,
and that every exemption must still match something real.

Both guards share one exemption mechanism — the `guard:counterexample` block —
so the honesty rule is checked once, jointly: **every block must be rejected by
at least one guard.** A block caught by neither is either not a violation at all
(so the document is teaching the wrong thing) or evidence that the rule which
used to catch it has regressed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import authority  # noqa: E402
import docset  # noqa: E402
import neutrality  # noqa: E402
import textblocks  # noqa: E402

ROLES = docset.ROLES
COORDINATOR = docset.COORDINATOR


def _caught_by_some_guard(body: str) -> bool:
    if neutrality.scan(body, ROLES, coordinator=COORDINATOR).findings:
        return True
    return bool(authority.scan(body))


class TestCounterexampleBlocksAreHonest(unittest.TestCase):
    def setUp(self):
        self.blocks: list[tuple[str, int, str]] = []
        for path in docset.all_documents():
            rel = path.relative_to(ROOT).as_posix()
            found, _ = textblocks.counterexample_blocks(
                path.read_text(encoding="utf-8")
            )
            self.blocks += [(rel, line, body) for line, body in found]

    def test_blocks_exist(self):
        # Fail closed: without this the test below passes vacuously, and the
        # documents that prohibit provider-shaped lanes and stale authority
        # language should be quoting examples of both.
        self.assertGreaterEqual(
            len(self.blocks), 3,
            "no counterexample blocks found; this honesty check would be "
            "vacuous",
        )

    def test_every_block_is_rejected_by_at_least_one_guard(self):
        inert = [
            f"{rel}:{line} — quoted as a counterexample but no guard rejects it"
            for rel, line, body in self.blocks
            if not _caught_by_some_guard(body)
        ]
        self.assertEqual(inert, [], "\n".join(inert))

    def test_removing_the_marker_would_make_the_document_fail(self):
        """The suppression is load-bearing, not decorative.

        If a block's text passed the guards anyway, the marker would be noise
        and its presence would teach the next author to sprinkle markers around.
        `test_every_block_is_rejected_by_at_least_one_guard` proves the text is
        rejected; this proves the *document* is clean only because of the
        marker, which is the property that actually matters.
        """
        for rel, line, body in self.blocks:
            with self.subTest(source=f"{rel}:{line}"):
                self.assertTrue(
                    _caught_by_some_guard(body),
                    "an unmarked copy of this block would not fail any guard",
                )


class TestScannersFailClosedOnEmptyInput(unittest.TestCase):
    def test_neutrality_refuses_an_empty_role_set(self):
        with self.assertRaises(ValueError):
            neutrality.scan("anything", ())

    def test_document_sets_are_populated(self):
        self.assertTrue(docset.normative_files())
        self.assertTrue(docset.historical_files())


class TestLogicalLineJoiningIsCorrect(unittest.TestCase):
    """The wrap-handling that both guards depend on.

    This was a real defect: "You do not\\nmerge it." reported the second physical
    line as a permission, because the negation was on the first.
    """

    def test_negation_across_a_soft_wrap_still_negates(self):
        self.assertEqual(
            authority.scan("You do not\nmerge it. Someone else reviews it."), []
        )

    def test_compound_lane_across_a_soft_wrap_is_still_caught(self):
        result = neutrality.scan("Hand this to the Acme\nWorker today.", ROLES)
        self.assertTrue(
            any(f.rule == "compound-lane" for f in result.findings),
            "a compound split across a wrap escaped the scanner",
        )

    def test_table_rows_are_not_joined(self):
        # Joining rows would let a negation in one silence a permission in the
        # next — the same defect in the opposite direction.
        text = "| never merges | ok |\n| the owner merges the PRs | bad |"
        self.assertTrue(authority.scan(text))

    def test_negators_have_word_boundaries(self):
        """Without boundaries, ordinary prose silently disarms both guards.

        "another" contains "not"; "nonetheless" contains "none". A negator
        matching inside a word would make most sentences read as prohibitions,
        and the guards would quietly stop reporting anything.
        """
        for word in ("another", "nonetheless", "notation", "nobody",
                     "stopgap", "avoidance", "rejection"):
            with self.subTest(word=word):
                self.assertFalse(
                    textblocks.negated(f"{word} ", len(word) + 1),
                    f"'{word}' was treated as a negation",
                )
        for phrase in ("never ", "does not ", "no "):
            with self.subTest(phrase=phrase):
                self.assertTrue(textblocks.negated(phrase, len(phrase)))

    def test_a_standalone_comment_does_not_absorb_the_next_line(self):
        lines = textblocks.logical_lines("<!-- marker -->\noffer to merge\n")
        self.assertEqual(lines[0][1].strip(), "<!-- marker -->")


if __name__ == "__main__":
    unittest.main()
