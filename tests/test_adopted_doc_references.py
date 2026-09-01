"""A Markdown file installed into an adopting repository must mean the same
thing from its installed location, however it got there.

THE DEFECT CLASS. `tools/adopt.py` copies the documents in `VERBATIM_DOCS` from
`framework/` into an adopting repository's `docs/agents/`. A relative link is
resolved against the file that holds it, so a link only survives that copy if
its target moves with it. Several did not:

    framework/CONSTITUTION.md   ../tools/neutrality.py
    framework/adapters.md       ../adapters/claude-code/
    framework/topologies.md     case-studies.md          (deliberately not copied)

In the framework repository every one of those resolves, so the existing link
checker passed. In an adopted project `docs/agents/CONSTITUTION.md` plus
`../tools/neutrality.py` is `docs/tools/neutrality.py`, which is nothing. The
reader who hits it is a cold session following a pointer the framework told it
was authoritative — exactly the reader this design assumes.

Note that escaping the copied directory is only the *loudest* member of the
class. `case-studies.md` never escapes anything: it is a plain sibling link in a
copied document, pointing at a document adoption deliberately does not copy. A
guard written against `../` would have missed it. The invariant is about
**meaning surviving the copy**, not about dot-dot.

`VERBATIM_DOCS` is not the only path a Markdown file takes into an adopted
project. `tools/adapters.py` installs whatever files an adapter declares —
`adapters/claude-code/README.md` among them — and that file had the identical
defect, found by actually adopting with `--adapter claude-code` and resolving
its links from `.claude/README.md`, not by inspection:

    adapters/claude-code/README.md   ../../framework/adapters.md
    adapters/claude-code/README.md   ../../tools/adapters.py
    adapters/claude-code/README.md   ../../tests/test_adapter_install_layout.py
    adapters/claude-code/README.md   adapter.json   (the manifest -- excluded from
                                                       installation on purpose)

The behavioural guard below used to skip `.claude/` explicitly, which is why
this second instance was not caught the first time the class was closed. It
does not skip anything now: the rule is about the installed tree, not about
which mechanism put a given file there, so it needs no adapter-specific
knowledge and nothing further to change when the next adapter ships one.

THE RULE, stated so it can be checked mechanically:

    A markdown relative link is a claim that the file it names exists in the
    repository the reader is holding. An installed document may therefore link
    only to other installed documents. Any other path — the framework's
    implementation, its tests, its history — is a reference, not a link: it is
    written as a plain path and the sentence says which repository it is in.

That distinction is the whole mechanism, and it needs no rendering step, no
placeholder, and nothing copied into a project that does not belong to it.

The guards below are: the rule, checked at the `VERBATIM_DOCS` source; the
behaviour, checked by adopting for real — with every adapter installed — and
resolving links **everywhere in the tree that produced**, not only where
`VERBATIM_DOCS` happens to land; and the marker, so an unresolvable reference
cannot quietly stay silent about which repository it means.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adapters as adapter_manifests  # noqa: E402
import adopt  # noqa: E402
from textblocks import logical_lines  # noqa: E402

#: Markdown link targets, excluding anchors, URLs and mail links. Same shape as
#: `tests/test_repo_integrity.py` uses; the difference is which tree it resolves
#: them against.
LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|#)([^)\s]+)\)")

#: Fenced blocks hold illustrative templates, not references.
FENCED = re.compile(r"^(?:```|~~~).*?^(?:```|~~~)", re.S | re.M)

#: A backticked token that looks like a path into a repository: it has a
#: directory separator, and it either names a file or ends in a slash.
BACKTICKED_PATH = re.compile(r"`([A-Za-z0-9_.][\w./-]*/[\w./-]*)`")

#: What a sentence must say when it names a path that an adopting project will
#: not have. Deliberately a phrase a human would write anyway, not a sigil.
SOURCE_MARKER = "framework repository"


def strip_fences(text: str) -> str:
    return FENCED.sub("", text)


def copied_docs() -> list[str]:
    """The framework-relative paths adoption copies verbatim."""
    return list(adopt.VERBATIM_DOCS)


def adopt_maximally(target: Path) -> None:
    """Adopt with every optional part on, so nothing is skipped by accident."""
    code = adopt.main([
        str(target), "--project", "Reference Test",
        "--verifier", "--hooks",
        *[arg for name in adapter_manifests.available(adopt.ADAPTERS)
          for arg in ("--adapter", name)],
    ])
    assert code == 0, "adoption failed"


def installed_paths(target: Path) -> set[str]:
    return {
        p.relative_to(target).as_posix()
        for p in target.rglob("*") if p.is_file()
    }


class AdoptedTreeCase(unittest.TestCase):
    """One real adoption, shared by the tests that read the produced tree."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name)
        adopt_maximally(cls.target)
        cls.installed = installed_paths(cls.target)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


class TestCopiedDocumentsOnlyLinkToCopiedDocuments(unittest.TestCase):
    """The rule, checked where the documents are written."""

    def test_there_is_something_to_check(self):
        self.assertGreaterEqual(len(copied_docs()), 10)

    def test_every_relative_link_targets_a_document_that_is_also_copied(self):
        copied = {(ROOT / "framework" / rel).resolve() for rel in copied_docs()}
        # A link may name a directory of copied documents, e.g. `roles/`.
        copied_dirs = {p.parent for p in copied}
        problems: list[str] = []
        for rel in copied_docs():
            path = ROOT / "framework" / rel
            for target in LINK.findall(strip_fences(path.read_text(encoding="utf-8"))):
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                resolved = (path.parent / clean).resolve()
                if resolved in copied or resolved in copied_dirs:
                    continue
                problems.append(
                    f"framework/{rel} -> {target} "
                    f"(not copied; it would dangle in an adopted project)"
                )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_rule_can_fail(self):
        """Red before green: a sibling link to a non-copied document breaks it.

        Written against `case-studies.md` because that is a real instance —
        a plain sibling link, no `../` anywhere, and still meaningless in the
        copy.
        """
        not_copied = (ROOT / "framework" / "case-studies.md")
        self.assertTrue(not_copied.is_file(), "the example document moved")
        self.assertNotIn(
            "case-studies.md", copied_docs(),
            "this document is deliberately not copied; see adopt.NOT_COPIED",
        )


class TestLinksResolveInTheAdoptedTree(AdoptedTreeCase):
    """The behaviour, checked by adopting for real — everything installed.

    Deliberately **not** scoped to `VERBATIM_DOCS`, or to any one adapter, or to
    any directory name: it walks every `.md` file the adoption in `setUpClass`
    actually produced, whatever put it there. That is what makes it the general
    guard rather than one more list of specific paths to keep in sync — a new
    adapter, or a new `VERBATIM_DOCS` entry, is covered the moment it installs
    anything, with no change here.
    """

    def _adopted_markdown(self) -> list[Path]:
        return sorted(p for p in self.target.rglob("*.md") if p.is_file())

    def test_there_is_something_to_check(self):
        self.assertGreaterEqual(
            len(self._adopted_markdown()), 10,
            "fail closed: no adopted documentation was found to check",
        )

    def test_the_check_covers_adapter_installed_markdown_too(self):
        """Fail closed on the generalisation itself.

        Without this, dropping the old `.claude` exclusion could silently stop
        mattering again -- e.g. if a future refactor reintroduced a directory
        skip -- and nothing would say so until the next dangling link shipped.
        """
        rels = {p.relative_to(self.target).as_posix() for p in self._adopted_markdown()}
        under_claude = [r for r in rels if r.startswith(".claude/")]
        self.assertTrue(
            under_claude,
            "no adapter-installed Markdown was found to check; either the "
            "claude-code adapter installed nothing, or this check stopped "
            "looking under .claude/ again",
        )

    def test_every_internal_link_resolves_where_it_was_installed(self):
        broken: list[str] = []
        checked = 0
        for path in self._adopted_markdown():
            rel = path.relative_to(self.target).as_posix()
            for target in LINK.findall(strip_fences(path.read_text(encoding="utf-8"))):
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                checked += 1
                if not (path.parent / clean).resolve().exists():
                    broken.append(f"{rel} -> {target}")
        self.assertGreater(
            checked, 0, "no links were resolved; this guard would pass vacuously"
        )
        self.assertEqual(broken, [], "\n".join(broken))

    def test_the_resolution_check_can_fail(self):
        """Red before green, in the adopted tree itself -- the VERBATIM_DOCS path."""
        doc = self.target / "docs" / "agents" / "CONSTITUTION.md"
        original = doc.read_text(encoding="utf-8")
        doc.write_text(
            original + "\n\nSee [the scanner](../tools/neutrality.py).\n",
            encoding="utf-8",
        )
        try:
            broken = [
                t for t in LINK.findall(strip_fences(doc.read_text(encoding="utf-8")))
                if not (doc.parent / t.split("#", 1)[0]).resolve().exists()
            ]
            self.assertIn(
                "../tools/neutrality.py", broken,
                "the check does not notice a link that escapes the copied "
                "directory, which is the original defect",
            )
        finally:
            doc.write_text(original, encoding="utf-8")

    def test_the_resolution_check_can_fail_for_an_adapter_installed_file(self):
        """Red before green again, for the adapter path this time.

        This is the mutation the earlier pass on this repository missed: the
        file lives under `.claude/`, which the check used to skip outright, so
        a broken framework-relative link there passed silently. Proven directly
        against the installed file, the same way the VERBATIM_DOCS case above
        is: mutate it, confirm the extraction-and-resolve logic actually flags
        it, restore it.
        """
        doc = self.target / ".claude" / "README.md"
        self.assertTrue(doc.is_file(), "no adapter README was installed to mutate")
        original = doc.read_text(encoding="utf-8")
        doc.write_text(
            original + "\n\nSee [the framework](../../framework/does-not-exist.md).\n",
            encoding="utf-8",
        )
        try:
            broken = [
                t for t in LINK.findall(strip_fences(doc.read_text(encoding="utf-8")))
                if not (doc.parent / t.split("#", 1)[0]).resolve().exists()
            ]
            self.assertIn(
                "../../framework/does-not-exist.md", broken,
                "an invalid framework-relative link inside adapter-installed "
                "Markdown was not caught",
            )
        finally:
            doc.write_text(original, encoding="utf-8")


class TestUnresolvableReferencesSayWhichRepository(AdoptedTreeCase):
    """An external reference must not read like an internal one.

    A path that an adopting project will not have is legitimate — the framework's
    own implementation and history are worth pointing at. What is not legitimate
    is leaving the reader to discover by failure that it is not theirs. So such
    a path is written as a reference rather than a link, and its sentence names
    the repository it belongs to.
    """

    def _framework_only(self, path_text: str) -> bool:
        """True if this path exists here but not in an adopted project."""
        here = (ROOT / path_text.rstrip("/"))
        if not here.exists():
            return False  # not a reference to a file in this repository at all
        stem = path_text.rstrip("/")
        return not any(
            p == stem or p.startswith(stem + "/") for p in self.installed
        )

    def test_every_framework_only_reference_is_marked(self):
        problems: list[str] = []
        for rel in copied_docs():
            path = ROOT / "framework" / rel
            for n, line in logical_lines(path.read_text(encoding="utf-8")):
                for candidate in BACKTICKED_PATH.findall(line):
                    if not self._framework_only(candidate):
                        continue
                    if SOURCE_MARKER in line.lower():
                        continue
                    problems.append(
                        f"framework/{rel}:{n} names `{candidate}`, which an "
                        f"adopting project does not have, without saying it is "
                        f"in the {SOURCE_MARKER}"
                    )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_marker_rule_can_fail(self):
        """Red before green, and in both directions."""
        # A path this repository has and adoption does not install.
        self.assertTrue(
            self._framework_only("tests/test_repo_integrity.py"),
            "this test file is not installed into adopting projects; if that "
            "changed, pick another example",
        )
        # A path adoption does install at the same place: not framework-only.
        self.assertIn("tools/neutrality.py", self.installed)
        self.assertFalse(self._framework_only("tools/neutrality.py"))
        # And something that is not a repository path at all.
        self.assertFalse(self._framework_only("worker/some-scope"))

    def test_useful_references_are_preserved_not_deleted(self):
        """The rule must not be satisfiable by removing every pointer.

        Deleting the reference passes a link checker and loses the reader the
        thing they were being sent to, which is a worse outcome than a broken
        link, not a better one.
        """
        text = "\n".join(
            (ROOT / "framework" / rel).read_text(encoding="utf-8")
            for rel in copied_docs()
        )
        for reference in (
            "neutrality.py",
            "test_role_neutrality.py",
            "case-studies.md",
        ):
            with self.subTest(reference=reference):
                self.assertIn(
                    reference, text,
                    "a reference the copied documents relied on has been "
                    "dropped rather than made target-safe",
                )


if __name__ == "__main__":
    unittest.main()
