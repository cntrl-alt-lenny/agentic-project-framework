"""Adoption is tested by doing it, not by checking that files exist.

`framework/evidence.md` says to test behaviour rather than installation. So this
runs the real script against a real temporary directory and then **runs the
guard it installed there**, in that tree, with that tree's role set. An adopted
project whose installed test cannot even import is the exact "hooks installed
but never executed" failure this framework catalogues.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adopt  # noqa: E402


def run_adopt(target: Path, *extra: str) -> int:
    return adopt.main([str(target), "--project", "Test Project", *extra])


class AdoptionCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


class TestDefaultAdoption(AdoptionCase):
    def setUp(self):
        super().setUp()
        self.assertEqual(run_adopt(self.target), 0)

    def test_expected_tree_is_created(self):
        for rel in (
            "AGENTS.md",
            "docs/agents/CONSTITUTION.md",
            "docs/agents/roles/brain.md",
            "docs/agents/roles/worker.md",
            "docs/agents/roles/verifier.md",
            "docs/agents/lifecycle.md",
            "docs/agents/evidence.md",
            "docs/state.md",
            "docs/briefs/README.md",
            "docs/briefs/active.md",
            "tools/neutrality.py",
            "tools/authority.py",
            "tools/textblocks.py",
            "tests/test_role_neutrality.py",
        ):
            with self.subTest(path=rel):
                self.assertTrue((self.target / rel).is_file(), rel)

    def test_history_is_not_copied(self):
        # The catalogue and case studies are this repository's evidence, not the
        # adopting project's — and they deliberately contain text the guards
        # reject, which would fail the installed test on day one.
        for rel in ("docs/agents/failure-catalogue.md",
                    "docs/agents/case-studies.md",
                    "docs/agents/adoption.md"):
            with self.subTest(path=rel):
                self.assertFalse((self.target / rel).exists(), rel)

    def test_no_unresolved_placeholders(self):
        leftovers = []
        for path in self.target.rglob("*"):
            if path.is_file() and path.suffix in (".md", ".py"):
                text = path.read_text(encoding="utf-8")
                if "{{" in text and "}}" in text:
                    leftovers.append(path.relative_to(self.target).as_posix())
        self.assertEqual(leftovers, [], f"unrendered placeholders: {leftovers}")

    def test_project_name_reaches_the_coordination_document(self):
        text = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Test Project", text)
        self.assertIn("worker", text.lower())

    def test_the_installed_guard_actually_runs_and_passes(self):
        """The whole point: the guard works in the tree it was installed into."""
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=self.target, capture_output=True, text=True,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"installed guard failed in the adopted tree:\n{proc.stdout}\n{proc.stderr}",
        )
        self.assertIn("OK", proc.stderr + proc.stdout)

    def test_the_installed_guard_is_not_vacuous(self):
        """It must have actually scanned something, and it must be able to fail.

        Red-before-green, in the adopted tree: introduce a provider-shaped
        branch namespace into the project's own coordination document and prove
        the installed guard rejects it.
        """
        agents = self.target / "AGENTS.md"
        original = agents.read_text(encoding="utf-8")
        agents.write_text(
            original + "\n\nCut the branch: `someprovider/task-scope` for this "
            "round.\n",
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests",
                 "-t", "."],
                cwd=self.target, capture_output=True, text=True,
            )
            self.assertNotEqual(
                proc.returncode, 0,
                "the installed guard passed against a provider-shaped branch "
                "namespace; it is not guarding anything",
            )
            self.assertIn("branch-namespace", proc.stdout + proc.stderr)
        finally:
            agents.write_text(original, encoding="utf-8")

    def test_stale_authority_language_is_rejected_in_the_adopted_tree(self):
        agents = self.target / "AGENTS.md"
        original = agents.read_text(encoding="utf-8")
        agents.write_text(
            original + "\n\nBrain reviews the work and will offer to merge; "
            "execute on OK.\n",
            encoding="utf-8",
        )
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests",
                 "-t", "."],
                cwd=self.target, capture_output=True, text=True,
            )
            self.assertNotEqual(
                proc.returncode, 0,
                "the installed guard accepted v1's stale authority language",
            )
            self.assertIn("routine-approval", proc.stdout + proc.stderr)
        finally:
            agents.write_text(original, encoding="utf-8")


class TestTopologyOptions(AdoptionCase):
    def test_specialists_and_verifier_reach_the_declared_role_set(self):
        self.assertEqual(
            run_adopt(self.target, "--workers", "decomper,scaffolder", "--verifier"),
            0,
        )
        test_file = (self.target / "tests/test_role_neutrality.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("'decomper'", test_file)
        self.assertIn("'scaffolder'", test_file)
        self.assertIn("'verifier'", test_file)

        agents = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Decomper", agents)
        self.assertIn("Scaffolder", agents)
        self.assertIn("Verifier", agents)

        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=self.target, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_executor_name_clashing_with_a_reserved_role_is_refused(self):
        for bad in ("brain", "verifier", "owner"):
            with self.subTest(name=bad):
                self.assertEqual(run_adopt(self.target, "--workers", bad), 2)

    def test_empty_worker_list_is_refused(self):
        self.assertEqual(run_adopt(self.target, "--workers", ","), 2)

    def test_unknown_adapter_is_refused(self):
        with self.assertRaises(SystemExit):
            run_adopt(self.target, "--adapter", "no-such-tool")

    def test_known_adapter_installs_and_points_at_the_contract(self):
        self.assertEqual(run_adopt(self.target, "--adapter", "claude-code"), 0)
        adapter = self.target / ".claude-code" / "agents" / "worker.md"
        self.assertTrue(adapter.is_file())
        self.assertIn("docs/agents/roles/worker.md", adapter.read_text(encoding="utf-8"))

    def test_hooks_are_installed_only_when_asked(self):
        self.assertEqual(run_adopt(self.target, "--hooks"), 0)
        self.assertTrue((self.target / ".githooks/pre-push").is_file())


class TestSafety(AdoptionCase):
    def test_dry_run_writes_nothing(self):
        before = sorted(p.name for p in self.target.iterdir())
        self.assertEqual(run_adopt(self.target, "--dry-run"), 0)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), before)

    def test_existing_files_are_never_overwritten(self):
        agents = self.target / "AGENTS.md"
        agents.write_text("PROJECT'S OWN FILE\n", encoding="utf-8")
        self.assertEqual(run_adopt(self.target), 0)
        self.assertEqual(agents.read_text(encoding="utf-8"), "PROJECT'S OWN FILE\n")
        self.assertTrue((self.target / "AGENTS.md.framework").is_file())

    def test_rerunning_is_safe(self):
        self.assertEqual(run_adopt(self.target), 0)
        first = (self.target / "docs/agents/CONSTITUTION.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(run_adopt(self.target), 0)
        # Second run collides with itself and writes siblings rather than
        # clobbering; the original is untouched either way.
        self.assertEqual(
            (self.target / "docs/agents/CONSTITUTION.md").read_text(encoding="utf-8"),
            first,
        )

    def test_missing_target_is_refused(self):
        self.assertEqual(
            run_adopt(self.target / "does-not-exist"), 2
        )


class TestVerbatimDocsStayInSync(unittest.TestCase):
    def test_every_copied_document_exists_here(self):
        for rel in adopt.VERBATIM_DOCS:
            with self.subTest(doc=rel):
                self.assertTrue((ROOT / "framework" / rel).is_file(), rel)

    def test_nothing_normative_is_silently_left_behind(self):
        """A new framework document must be a deliberate copy-or-not decision.

        Without this, adding a document here would silently fail to reach any
        adopting project, and nobody would notice until it was needed.
        """
        copied = set(adopt.VERBATIM_DOCS)
        excluded = set(adopt.NOT_COPIED)
        for path in sorted((ROOT / "framework").rglob("*.md")):
            rel = path.relative_to(ROOT / "framework").as_posix()
            with self.subTest(doc=rel):
                self.assertTrue(
                    rel in copied or rel in excluded or path.name in excluded,
                    f"{rel} is neither copied on adoption nor explicitly "
                    f"excluded; decide which and record it in adopt.py",
                )


if __name__ == "__main__":
    unittest.main()
