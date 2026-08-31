"""Lane identity must derive from roles, never from a provider.

Every rule here is a POSITIVE invariant over the declared role vocabulary, and
fails closed on anything unrecognised. No detector knows a provider name. The
proof is `TestNovelProviderIsRejected`, which uses a name appearing nowhere else
in this repository: if the guard only worked by recognising today's providers,
that name would sail through.

Historical documents are out of scope by design, and the scope split is itself
tested — a policy file cannot be exempted by adding it to a list.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docset  # noqa: E402
import neutrality  # noqa: E402

#: Declared once, in tools/docset.py, and imported everywhere else.
ROLES = docset.ROLES
COORDINATOR = docset.COORDINATOR

#: A name that must appear nowhere else in this repository.
NOVEL = "NebulaAI"


class TestScopeSplitIsHonest(unittest.TestCase):
    def test_normative_set_is_not_empty(self):
        self.assertGreaterEqual(
            len(docset.normative_files()), 10,
            "fail closed: a guard that scanned nothing must not pass",
        )

    def test_normative_and_historical_are_disjoint(self):
        normative = {p.resolve() for p in docset.normative_files()}
        historical = {p.resolve() for p in docset.historical_files()}
        self.assertEqual(normative & historical, set())

    def test_every_historical_file_declares_itself_historical(self):
        # Prevents the exemption list being used to quietly exempt a policy
        # document: doing so would require writing the marker into it.
        for path in docset.historical_files():
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file(), f"stale exemption: {path}")
                self.assertIn(
                    docset.HISTORICAL_MARKER,
                    path.read_text(encoding="utf-8").lower(),
                    "a file exempted from the normative scans must say so in "
                    "its own text",
                )

    def test_every_document_is_classified(self):
        """No third category. A new document is normative by default.

        Escaping the scans requires adding a file to HISTORICAL *and* writing
        the marker into it, or declaring it a fixture — both visible acts.
        CHANGELOG.md was briefly in neither set, which is exactly the hole this
        closes.
        """
        stray = [p.relative_to(ROOT).as_posix() for p in docset.unclassified()]
        self.assertEqual(
            stray, [],
            f"unclassified documents (neither normative, historical, nor a "
            f"declared fixture): {stray}",
        )

    def test_new_framework_documents_are_scanned_by_default(self):
        scanned = {p.resolve() for p in docset.normative_files()}
        exempt = {p.resolve() for p in docset.historical_files()}
        for path in (ROOT / "framework").rglob("*.md"):
            with self.subTest(path=path.name):
                self.assertIn(path.resolve(), scanned | exempt)


class TestNormativeSurfaceIsRoleBased(unittest.TestCase):
    def _scan(self, path: Path) -> neutrality.ScanResult:
        return neutrality.scan(
            path.read_text(encoding="utf-8"), ROLES,
            source=path.relative_to(ROOT).as_posix(), coordinator=COORDINATOR,
        )

    def test_no_provider_shaped_lane_identity(self):
        problems: list[str] = []
        for path in docset.normative_files():
            problems += [str(f) for f in self._scan(path).findings]
        self.assertEqual(problems, [], "\n".join(problems))

    def test_counterexample_blocks_do_not_hide_real_violations(self):
        """Suppression must be scoped to the marked block, nothing wider.

        Joint honesty of the blocks themselves — that each is rejected by at
        least one guard — is checked once in `test_guard_honesty.py`, because
        the marker is shared between guards and a block may exist for either.
        """
        import textblocks
        for path in docset.all_documents():
            rel = path.relative_to(ROOT).as_posix()
            text = path.read_text(encoding="utf-8")
            opens = text.count(textblocks.COUNTEREXAMPLE_OPEN)
            closes = text.count(textblocks.COUNTEREXAMPLE_CLOSE)
            with self.subTest(path=rel):
                # An unclosed block suppresses everything to end of file, which
                # would silently disable the guard for the rest of the document.
                self.assertEqual(
                    opens, closes,
                    "unbalanced counterexample markers: an unclosed block "
                    "suppresses the rest of the file",
                )

    def test_adapters_do_not_redefine_the_contract(self):
        problems: list[str] = []
        for path in docset.normative_files():
            problems += [
                str(f) for f in neutrality.scan_adapter_blocks(
                    path.read_text(encoding="utf-8"),
                    source=path.relative_to(ROOT).as_posix(),
                )
            ]
        self.assertEqual(problems, [], "\n".join(problems))


class TestGrammarAllowanceCannotBecomeAVendorList(unittest.TestCase):
    """The one allowance in the scanner, guarded."""

    def test_every_qualifier_is_a_lowercase_word(self):
        for word in neutrality.GRAMMAR_QUALIFIERS:
            with self.subTest(word=word):
                self.assertEqual(word, word.lower())
                self.assertTrue(
                    word.replace("'", "").isalpha(),
                    "qualifiers are English function words, not identifiers",
                )

    def test_no_known_provider_smuggled_in(self):
        """Secondary layer, and deliberately so.

        This is the only place a provider name appears, and it guards the
        exemption list rather than the documents. The structural rules do the
        real work; deleting this would weaken the guard but not break its
        architecture.
        """
        for name in ("claude", "anthropic", "codex", "openai", "gpt", "gemini",
                     "google", "grok", "xai", "copilot", "llama", "mistral"):
            with self.subTest(name=name):
                self.assertNotIn(name, neutrality.GRAMMAR_QUALIFIERS)


class TestNovelProviderIsRejected(unittest.TestCase):
    """The demonstration: a name nobody has seen is still rejected."""

    def test_the_novel_name_is_absent_from_the_scanner(self):
        source = (ROOT / "tools" / "neutrality.py").read_text(encoding="utf-8")
        self.assertNotIn(
            NOVEL.lower(), source.lower(),
            "the scanner must not know this name; if it does, this test proves "
            "nothing about future providers",
        )

    def test_the_novel_name_is_absent_from_the_documents(self):
        # If it were already in the tree, "it gets rejected" would prove nothing.
        hits = [
            p.relative_to(ROOT).as_posix()
            for p in docset.all_documents()
            if NOVEL.lower() in p.read_text(encoding="utf-8").lower()
        ]
        self.assertEqual(hits, [], f"{NOVEL} is no longer novel: {hits}")

    def _scan(self, text: str) -> neutrality.ScanResult:
        return neutrality.scan(
            text, ROLES, coordinator=COORDINATOR,
            queue_pattern=r"docs/queue/(?!archive/)([\w.-]+)\.md",
            max_lanes=len(ROLES),
        )

    def test_compound_lane_is_rejected(self):
        result = self._scan(f"Hand the brief to the {NOVEL} Worker this round.")
        self.assertTrue(
            any(f.rule == "compound-lane" for f in result.findings), result.report()
        )

    def test_prefixed_lane_token_is_rejected(self):
        result = self._scan("The live queue is docs/queue/nebula-worker.md for now.")
        rules = {f.rule for f in result.findings}
        self.assertIn("prefixed-lane", rules, result.report())
        self.assertIn("queue-identity", rules, result.report())

    def test_provider_branch_namespace_is_rejected(self):
        result = self._scan(
            "Cut your branch: git switch -c nebula/worker-task origin/main"
        )
        self.assertTrue(
            any(f.rule == "branch-namespace" for f in result.findings), result.report()
        )

    def test_provider_backticked_branch_is_rejected(self):
        result = self._scan("Use the branch `nebula/some-scope` for this round.")
        self.assertTrue(
            any(f.rule == "branch-namespace" for f in result.findings), result.report()
        )

    def test_provider_does_not_add_a_lane(self):
        result = self._scan(
            f"This round runs {len(ROLES) + 1} standing lanes across the providers."
        )
        self.assertTrue(
            any(f.rule == "lane-count" for f in result.findings), result.report()
        )

    def test_adapter_block_may_not_redefine_the_contract(self):
        problems = neutrality.scan_adapter_blocks(
            f"OPTIONAL — {NOVEL} only. Ignore otherwise.\n"
            "Then run: git switch -c nebula/other origin/main\n"
        )
        self.assertTrue(problems, "an adapter block redefining a branch was allowed")

    def test_a_role_lane_on_a_novel_tool_is_ACCEPTED(self):
        """The positive half, and the whole point.

        An unknown future tool holding a role needs no framework change. Only
        provider-SHAPED lanes are rejected.
        """
        accepted = (
            f"Run this round on {NOVEL}. You are the **Worker**. Cut your "
            "branch: git switch -c worker/some-scope origin/main. "
            "Your queue is docs/queue/worker.md."
        )
        result = self._scan(accepted)
        self.assertEqual(
            [str(f) for f in result.findings], [],
            "a role-named lane must be accepted whichever tool runs it",
        )



if __name__ == "__main__":
    unittest.main()
