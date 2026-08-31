"""An adapter starts a role on one tool. It never restates policy.

A provider adapter that paraphrases the contract becomes a second source of
truth, and it drifts — silently, in a real project, until a test caught an
adapter still describing a superseded authority model long after the contracts
had moved on (`framework/failure-catalogue.md`, entry 8).

So the shape is enforced: point at the contract, add launch mechanics, and stop.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import authority  # noqa: E402
import neutrality  # noqa: E402

ADAPTERS = ROOT / "adapters"

#: Where a role adapter must send the reader for the authoritative text, in the
#: layout adoption produces.
CONTRACT_PATH = re.compile(r"docs/agents/roles/(brain|worker|verifier)\.md")


def adapter_role_files() -> list[Path]:
    return sorted(ADAPTERS.rglob("agents/*.md"))


def adapter_files() -> list[Path]:
    return sorted(p for p in ADAPTERS.rglob("*") if p.is_file())


class TestAdaptersExistAndAreScanned(unittest.TestCase):
    def test_there_is_at_least_one_adapter_to_check(self):
        # Fail closed: with no adapters these tests would pass vacuously while
        # claiming adapter boundaries are enforced.
        self.assertTrue(adapter_role_files(), "no adapter role files found")


class TestAdaptersPointAtContracts(unittest.TestCase):
    def test_every_role_adapter_names_its_canonical_contract(self):
        for path in adapter_role_files():
            with self.subTest(adapter=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8")
                self.assertRegex(
                    text, CONTRACT_PATH,
                    "an adapter must send the reader to the canonical contract",
                )

    def test_every_role_adapter_says_the_contract_is_authoritative(self):
        for path in adapter_role_files():
            with self.subTest(adapter=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("authoritative", text)
                self.assertIn("does not restate", text)

    def test_the_adapter_matches_the_role_it_names(self):
        for path in adapter_role_files():
            role = path.stem
            with self.subTest(adapter=path.relative_to(ROOT).as_posix()):
                text = path.read_text(encoding="utf-8")
                self.assertIn(f"docs/agents/roles/{role}.md", text,
                              "an adapter pointing at another role's contract")


class TestAdaptersDoNotRestatePolicy(unittest.TestCase):
    def _policy_hits(self, text: str) -> list[str]:
        # adapter_policy_hits ignores prohibitions: an adapter saying "no queue,
        # no gate" is describing its own limits, not defining policy.
        return neutrality.adapter_policy_hits(text) + [
            f.matched for f in authority.scan(text)
        ]

    def test_no_adapter_contains_authority_queue_branch_or_gate_language(self):
        problems = []
        for path in adapter_files():
            if path.suffix not in (".md", ".json"):
                continue
            hits = self._policy_hits(path.read_text(encoding="utf-8"))
            if hits:
                problems.append(
                    f"{path.relative_to(ROOT).as_posix()}: {sorted(set(hits))}"
                )
        self.assertEqual(problems, [], "\n".join(problems))

    def test_no_adapter_prescribes_a_branch(self):
        for path in adapter_files():
            if path.suffix != ".md":
                continue
            with self.subTest(adapter=path.relative_to(ROOT).as_posix()):
                self.assertNotRegex(
                    path.read_text(encoding="utf-8"),
                    neutrality.BRANCH_COMMAND,
                    "branch identity is the contract's, never an adapter's",
                )


class TestTheGuardCanActuallyFail(unittest.TestCase):
    """Red-before-green. Each mutation is a real way an adapter goes wrong."""

    def _hits(self, text: str) -> list[str]:
        return neutrality.adapter_policy_hits(text) + [
            f.matched for f in authority.scan(text)
        ]

    def test_an_adapter_granting_merge_rights_is_rejected(self):
        self.assertTrue(
            self._hits("You may merge once the checks are green."),
            "an adapter granting merge rights was allowed",
        )

    def test_an_adapter_restating_the_approval_gate_is_rejected(self):
        self.assertTrue(
            self._hits("Summarize the change, then offer to merge."),
            "an adapter restating a stale approval gate was allowed",
        )

    def test_an_adapter_granting_self_merge_is_rejected(self):
        self.assertTrue(
            self._hits("In an emergency this seat may self-merge the fix."),
            "an adapter granting self-merge was allowed",
        )

    def test_an_adapter_defining_a_queue_is_rejected(self):
        self.assertTrue(
            self._hits("Read the queue before starting."),
            "an adapter defining queue identity was allowed",
        )

    def test_an_adapter_prescribing_a_branch_is_rejected(self):
        self.assertRegex(
            "Start with: git switch -c someprovider/task origin/main",
            neutrality.BRANCH_COMMAND,
        )

    def test_ordinary_launch_mechanics_are_ACCEPTED(self):
        # The positive half: an adapter must be free to say the tool-specific
        # things it exists to say, or authors will route around the guard.
        for allowed in (
            "Work in this seat's own checkout, detached at the SHA under review.",
            "No model is pinned: this seat inherits whatever was launched.",
            "`/status` runs the contract's rehydration sequence.",
            "Start from the brief and the contract in fresh context.",
        ):
            with self.subTest(text=allowed[:40]):
                self.assertEqual(self._hits(allowed), [], allowed)


if __name__ == "__main__":
    unittest.main()
