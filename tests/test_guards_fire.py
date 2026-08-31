"""Prove every guard red against a deliberately broken tree.

`framework/evidence.md` requires this of any important guard: demonstrate it
failing against the known broken state before trusting it green. A guard nobody
has watched fail is not yet a guard.

So each case below copies this repository to a temporary directory, introduces
one specific defect, runs the guard that should catch it **in that copy**, and
asserts it fails with the expected rule. The mutation never touches the working
tree, so a crash mid-test cannot leave it dirty.

This is deliberately a test rather than a written audit. An audit records that
the guards fired once, on a tree that has since moved; a test re-establishes it
on every run, which is the difference the framework's own rules insist on.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache")


def copy_repo(dest: Path) -> Path:
    target = dest / "repo"
    shutil.copytree(ROOT, target, ignore=IGNORE)
    return target


def run_module(tree: Path, module: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", module],
        cwd=tree, capture_output=True, text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


class MutationCase(unittest.TestCase):
    """One defect, one guard, one expected rule."""

    def assert_guard_fires(
        self, *, path: str, mutate, module: str, expect: str, why: str,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_repo(Path(tmp))
            target = tree / path

            # Sanity: the guard must be green before the mutation, or the test
            # below would "pass" for an unrelated pre-existing failure.
            rc, out = run_module(tree, module)
            self.assertEqual(rc, 0, f"{module} was already failing:\n{out}")

            target.write_text(
                mutate(target.read_text(encoding="utf-8")), encoding="utf-8"
            )
            rc, out = run_module(tree, module)

            self.assertNotEqual(rc, 0, f"guard did not fire: {why}\n{out}")
            self.assertIn(
                expect, out,
                f"guard fired, but not for the expected reason ({why}):\n{out}",
            )


def append(text: str):
    return lambda body: body + text


class TestNeutralityGuardFires(MutationCase):
    MODULE = "tests.test_provider_neutrality"

    def test_a_provider_bound_to_a_role_is_caught(self):
        self.assert_guard_fires(
            path="framework/roles/worker.md",
            mutate=append("\n\nHand this brief to the Acme Worker for the round.\n"),
            module=self.MODULE, expect="compound-lane",
            why="a proper noun bound to a role makes a lane out of the vendor",
        )

    def test_a_provider_branch_namespace_is_caught(self):
        self.assert_guard_fires(
            path="framework/git-and-isolation.md",
            mutate=append("\n\nCut the branch `acme/some-scope` for this round.\n"),
            module=self.MODULE, expect="branch-namespace",
            why="branch namespaces derive from roles, never from providers",
        )

    def test_reclassifying_a_policy_file_as_history_is_caught(self):
        self.assert_guard_fires(
            path="framework/failure-catalogue.md",
            mutate=lambda body: body.replace(
                "**This is a historical document.**", "It records events."
            ),
            module=self.MODULE, expect="must say so in",
            why="the exemption list must not be usable to hide a policy file",
        )

    def test_a_document_outside_the_scanned_directories_is_caught(self):
        """The hole `CHANGELOG.md` briefly fell into.

        A document added *under* `framework/` is normative by default and needs
        no decision. One added elsewhere would previously have been in no
        category at all — scanned by nothing, and silently so.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_repo(Path(tmp))
            rc, out = run_module(tree, self.MODULE)
            self.assertEqual(rc, 0, out)

            (tree / "NOTES.md").write_text("# Notes\n\nSomething.\n", encoding="utf-8")
            rc, out = run_module(tree, self.MODULE)
            self.assertNotEqual(
                rc, 0, "a document outside every scanned directory was classified "
                "by nothing and reported no problem"
            )
            self.assertIn("unclassified", out)

    def test_a_new_framework_document_is_normative_by_default(self):
        """The other half: inside `framework/`, no decision is needed.

        Fail-closed must not mean fail-noisy — a normal new policy document
        should simply be scanned, not rejected.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_repo(Path(tmp))
            (tree / "framework" / "notes.md").write_text(
                "# Notes\n\nThe Worker executes one brief.\n", encoding="utf-8"
            )
            rc, out = run_module(tree, self.MODULE)
            self.assertEqual(rc, 0, f"a clean new policy document was rejected:\n{out}")

            (tree / "framework" / "notes.md").write_text(
                "# Notes\n\nHand it to the Acme Worker.\n", encoding="utf-8"
            )
            rc, out = run_module(tree, self.MODULE)
            self.assertNotEqual(rc, 0, "the new document was not actually scanned")


class TestAuthorityGuardFires(MutationCase):
    MODULE = "tests.test_authority_invariants"

    def test_routine_merge_approval_returning_is_caught(self):
        self.assert_guard_fires(
            path="framework/roles/brain.md",
            mutate=append("\n\nSummarize the change, then offer to merge.\n"),
            module=self.MODULE, expect="routine-approval",
            why="v1's exact failure: routing the routine merge back to the owner",
        )

    def test_the_owner_named_as_merge_actor_is_caught(self):
        self.assert_guard_fires(
            path="framework/CONSTITUTION.md",
            mutate=append("\n\nThe owner merges the pull requests once happy.\n"),
            module=self.MODULE, expect="routine-approval",
            why="the owner is not the merge button",
        )

    def test_executor_self_merge_returning_is_caught(self):
        self.assert_guard_fires(
            path="framework/roles/worker.md",
            mutate=append(
                "\n\nIn a production fire this seat may self-merge the fix.\n"
            ),
            module=self.MODULE, expect="executor-self-merge",
            why="v1 granted an executor emergency self-merge rights",
        )

    def test_losing_the_executor_prohibition_is_caught(self):
        self.assert_guard_fires(
            path="framework/roles/verifier.md",
            mutate=lambda body: body.replace("never", "always").replace(
                "does not", "does"
            ).replace("Does not", "Does"),
            module=self.MODULE, expect="no longer states that it does not merge",
            why="a contract that loses its boundary must not pass",
        )


class TestAdapterGuardFires(MutationCase):
    MODULE = "tests.test_adapter_boundaries"

    def test_an_adapter_granting_merge_rights_is_caught(self):
        self.assert_guard_fires(
            path="adapters/claude-code/agents/worker.md",
            mutate=append("\n\nYou may merge once the checks are green.\n"),
            module=self.MODULE, expect="may merge",
            why="an adapter may never touch authority",
        )

    def test_an_adapter_dropping_its_contract_pointer_is_caught(self):
        self.assert_guard_fires(
            path="adapters/claude-code/agents/brain.md",
            mutate=lambda body: body.replace("docs/agents/roles/brain.md", "the docs"),
            module=self.MODULE, expect="canonical contract",
            why="an adapter that does not point at its contract will drift",
        )


class TestAdapterInstallLayoutGuardFires(MutationCase):
    """Reproduce the shipped defect exactly, and prove the guard rejects it.

    The pre-fix installer derived a provider's destination by prepending a dot
    to its adapter name. Rewriting the manifest to that name-derived value
    recreates the identical broken tree — configuration under a directory the
    tool never reads, and an installed hook command pointing at one that does
    not exist.
    """

    MODULE = "tests.test_adapter_install_layout"

    def test_the_name_derived_destination_is_caught(self):
        self.assert_guard_fires(
            path="adapters/claude-code/adapter.json",
            mutate=lambda body: body.replace(
                '"install_root": ".claude"', '"install_root": ".claude-code"'
            ),
            module=self.MODULE, expect="does not name the destination",
            why="the adapter name is not the tool's configuration directory",
        )

    def test_a_dangling_internal_path_reference_is_caught(self):
        """The failure the wrong destination actually caused, on its own.

        Even with a destination nobody disputes, a file the installed settings
        point at must exist once adoption has run.
        """
        self.assert_guard_fires(
            path="adapters/claude-code/settings.json",
            mutate=lambda body: body.replace(
                "save_agent_reply.py", "not_installed_anywhere.py"
            ),
            module=self.MODULE, expect="not_installed_anywhere.py",
            why="an installed config pointing at a file adoption never wrote "
                "is an inert hook that reports nothing",
        )

    def test_an_adapter_losing_its_manifest_is_caught(self):
        """No fallback to fall back to: refusing beats guessing."""
        with tempfile.TemporaryDirectory() as tmp:
            tree = copy_repo(Path(tmp))
            rc, out = run_module(tree, self.MODULE)
            self.assertEqual(rc, 0, f"{self.MODULE} was already failing:\n{out}")

            (tree / "adapters" / "claude-code" / "adapter.json").unlink()
            rc, out = run_module(tree, self.MODULE)
            self.assertNotEqual(
                rc, 0, "an adapter with no declared layout was accepted"
            )
            self.assertIn("adapter.json", out)


class TestRepositoryIntegrityGuardFires(MutationCase):
    MODULE = "tests.test_repo_integrity"

    def test_a_dangling_cross_reference_is_caught(self):
        self.assert_guard_fires(
            path="framework/CONSTITUTION.md",
            mutate=append("\n\nSee [the missing thing](does-not-exist.md).\n"),
            module=self.MODULE, expect="does-not-exist.md",
            why="a pointer to a moved file is a dead end for a cold session",
        )

    def test_ci_no_longer_running_the_suite_is_caught(self):
        self.assert_guard_fires(
            path=".github/workflows/ci.yml",
            mutate=lambda body: body.replace(
                "python -m unittest discover -s tests -t .", "echo skipped"
            ),
            module=self.MODULE, expect="CI must run the same discovery",
            why="tests that CI does not run are counted as coverage and are not",
        )


if __name__ == "__main__":
    unittest.main()
