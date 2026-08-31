"""Structural integrity of this repository: links resolve, and CI runs the tests.

Two failures from the catalogue apply to this repository as much as to any
project adopting it:

* **"Tests present but not collected"** — a test file that CI never runs is
  worse than absent, because it is counted as coverage.
* **Broken cross-references** — the framework is a web of documents that point
  at each other, and a pointer to a file that moved is a silent dead end for a
  cold session, which is exactly the reader this whole design assumes.

The CI check is honest about its limit: it compares the workflow's command text
against the discovery this suite performs. That proves the workflow invokes the
same discovery over the same directory. It does not prove the workflow file is
wired to a runner that exists.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import docset  # noqa: E402

WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
DISCOVERY = "python -m unittest discover -s tests -t ."

#: Markdown link targets, excluding anchors, URLs and mail links.
LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|#)([^)\s]+)\)")

#: Fenced code blocks are stripped before link extraction: a template showing
#: `[contract](<path>)` is an illustration, not a reference to a file.
FENCED = re.compile(r"^(?:```|~~~).*?^(?:```|~~~)", re.S | re.M)

#: Documents whose relative links resolve against an *adopted* tree, not this
#: one. `tests/test_adopt.py` checks those where they are actually valid.
ADOPTED_LAYOUT = ("templates", "adapters")


class TestEveryTestFileIsCollected(unittest.TestCase):
    def _discovered_modules(self) -> set[str]:
        import unittest as ut
        suite = ut.defaultTestLoader.discover(
            str(ROOT / "tests"), top_level_dir=str(ROOT)
        )
        found: set[str] = set()

        def walk(s):
            for item in s:
                if isinstance(item, ut.TestSuite):
                    walk(item)
                else:
                    found.add(type(item).__module__)
        walk(suite)
        return found

    def test_no_test_file_is_silently_skipped(self):
        on_disk = {f"tests.{p.stem}" for p in (ROOT / "tests").glob("test_*.py")}
        discovered = self._discovered_modules()
        missing = sorted(on_disk - discovered)
        self.assertEqual(
            missing, [],
            f"these test files exist but are not collected: {missing}",
        )

    def test_discovery_is_not_empty(self):
        self.assertGreaterEqual(len(self._discovered_modules()), 5)

    def test_no_module_failed_to_import(self):
        # A module that fails to import is collected as a single synthetic
        # failing test named after the loader, which is easy to misread.
        self.assertNotIn(
            "unittest.loader", self._discovered_modules(),
            "a test module failed to import",
        )


class TestCIRunsTheSameDiscovery(unittest.TestCase):
    def test_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file(), "no CI workflow")

    def test_workflow_runs_the_discovery_command_this_suite_uses(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            DISCOVERY, text,
            "CI must run the same discovery over the same directory, or the "
            "collection guarantee above says nothing about CI",
        )


class TestDocumentLinksResolve(unittest.TestCase):
    def _checkable(self) -> list[Path]:
        return [
            p for p in docset.all_documents()
            if not any(part in ADOPTED_LAYOUT for part in p.relative_to(ROOT).parts)
        ]

    def test_there_is_something_to_check(self):
        self.assertGreaterEqual(len(self._checkable()), 10)

    def test_every_relative_link_resolves(self):
        broken: list[str] = []
        for path in self._checkable():
            rel = path.relative_to(ROOT).as_posix()
            # Fenced code blocks hold illustrative templates, not links.
            body = FENCED.sub("", path.read_text(encoding="utf-8"))
            for target in LINK.findall(body):
                clean = target.split("#", 1)[0]
                if not clean:
                    continue
                if not (path.parent / clean).resolve().exists():
                    broken.append(f"{rel} -> {target}")
        self.assertEqual(broken, [], "\n".join(broken))

    def test_the_link_check_can_fail(self):
        """Red before green: the pattern must actually match a broken link."""
        found = LINK.findall("see [the thing](does/not/exist.md) for detail")
        self.assertEqual(found, ["does/not/exist.md"])
        self.assertFalse((ROOT / "does/not/exist.md").exists())

    def test_links_inside_code_fences_are_ignored(self):
        text = "\n".join((
            "```",
            "see [x](<placeholder>)",
            "```",
            "[real](README.md)",
        ))
        self.assertEqual(LINK.findall(FENCED.sub("", text)), ["README.md"])

    def test_urls_and_anchors_are_not_treated_as_paths(self):
        text = "[a](https://example.com) [b](#section) [c](mailto:x@y.z)"
        self.assertEqual(LINK.findall(text), [])


if __name__ == "__main__":
    unittest.main()
