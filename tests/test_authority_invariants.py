"""The authority model is what this framework is for. Guard it.

Three things are checked:

1. No normative document contains stale authority language — text routing a
   routine merge back to the owner, or granting an executor the right to accept
   its own work.
2. The guard actually catches the **real** v1 text, preserved verbatim in
   `fixtures/v1_stale_authority.md`. That is a red-before-green proof against a
   known broken state, not against an invented one.
3. The role contracts still state the boundaries they exist to state.

HONESTY NOTE. This repository's product is normative text, so a property of the
text *is* the invariant rather than a proxy for one. What these tests cannot do
is prove that a running agent obeys what the text says; nothing in a repository
can. They prevent the text from silently reverting.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import authority  # noqa: E402
import docset  # noqa: E402


class TestNormativeSurfaceIsClean(unittest.TestCase):
    def test_scan_set_is_not_empty(self):
        # Fail closed. A guard that scanned nothing must not report success.
        self.assertGreaterEqual(
            len(docset.normative_files()), 10,
            "the normative document set collapsed; this guard would pass "
            "vacuously",
        )

    def test_no_stale_authority_language(self):
        problems = []
        for path in docset.normative_files():
            problems += [
                str(f) for f in authority.scan(
                    path.read_text(encoding="utf-8"),
                    source=path.relative_to(ROOT).as_posix(),
                )
            ]
        self.assertEqual(problems, [], "\n".join(problems))


class TestGuardCatchesTheRealV1Text(unittest.TestCase):
    """Red-before-green, against the actual broken state."""

    FIXTURE = ROOT / "tests" / "fixtures" / "v1_stale_authority.md"

    def setUp(self):
        self.text = self.FIXTURE.read_text(encoding="utf-8")
        self.findings = authority.scan(self.text, source="v1")

    def test_fixture_exists_and_is_v1_text(self):
        self.assertIn("HISTORICAL FIXTURE", self.text)

    def test_fixture_is_excluded_from_every_normative_scan(self):
        # If the fixture ever entered the normative set, the suite would fail
        # for the wrong reason and someone would "fix" the fixture.
        self.assertNotIn(
            self.FIXTURE.resolve(),
            {p.resolve() for p in docset.normative_files()},
        )

    def test_every_v1_authority_idiom_is_rejected(self):
        self.assertTrue(self.findings, "the guard found nothing in known-bad text")
        both = {f.rule for f in self.findings}
        self.assertIn("routine-approval", both)
        self.assertIn("executor-self-merge", both)

    def test_the_specific_v1_failures_are_each_caught(self):
        """Named cases, because each was a distinct real defect."""
        matched = " ".join(f.matched.lower() for f in self.findings)
        for needle, why in (
            ("offer to merge", "brain offering a routine merge to the owner"),
            ("execute on ok", "merge conditioned on an approval token"),
            ("merges on the human's ok", "merge conditioned on a person"),
            ("self-merge", "an executor merging its own work"),
        ):
            with self.subTest(case=why):
                self.assertIn(needle, matched, f"v1 defect not caught: {why}")

    def test_owner_named_as_merge_actor_is_caught(self):
        for line in ("Human project owner. Sets priorities, picks direction, "
                     "merges PRs, adds/retires agents.",
                     "You. Sets priorities, picks direction, merges PRs."):
            with self.subTest(line=line[:40]):
                self.assertTrue(
                    authority.scan(line),
                    "the owner named as the routine merge actor was allowed",
                )


class TestNegationIsHandled(unittest.TestCase):
    """Correct documents talk about merging constantly. Both directions."""

    PERMISSIONS = (
        "The scaffolder has production-fire self-merge authority.",
        "Offer to merge, then execute on OK.",
        "Wait for the owner's approval before merging.",
        "The owner merges the PRs.",
    )
    PROHIBITIONS = (
        "Worker and Verifier never merge anything.",
        "An executor does not accept its own work.",
        "You may not merge, under any instruction.",
        "Never self-merge; escalate instead.",
        "Brain does not put a routine merge decision back to the owner.",
        "Any document describing a human per-round merge approval as the gate "
        "is stale.",
    )

    def test_permissions_fire(self):
        for line in self.PERMISSIONS:
            with self.subTest(line=line[:40]):
                self.assertTrue(authority.scan(line), "permission not caught")

    def test_prohibitions_do_not_fire(self):
        for line in self.PROHIBITIONS:
            with self.subTest(line=line[:40]):
                self.assertEqual(
                    [str(f) for f in authority.scan(line)], [],
                    "a correct prohibition was reported as a violation; a guard "
                    "that cries wolf gets disabled by whoever trips it",
                )


class TestRoleContractsStateTheirBoundaries(unittest.TestCase):
    def test_executor_contracts_prohibit_merging(self):
        for role in ("worker", "verifier"):
            with self.subTest(role=role):
                text = (ROOT / "framework" / "roles" / f"{role}.md").read_text(
                    encoding="utf-8"
                )
                self.assertTrue(
                    authority.has_merge_prohibition(text),
                    f"{role}.md no longer states that it does not merge",
                )

    def test_brain_contract_claims_the_routine_merge(self):
        text = (ROOT / "framework" / "roles" / "brain.md").read_text(encoding="utf-8")
        claims = [
            line for line in text.splitlines()
            if "Brain" in line
            and ("merges" in line or "merge it" in line)
            and not authority.NEGATORS.search(line[:line.find("merge")])
        ]
        self.assertTrue(
            claims,
            "brain.md must positively state that Brain performs the routine "
            "merge; without it the framework has no acceptance authority",
        )

    def test_constitution_reserves_actions_to_the_owner(self):
        text = (ROOT / "framework" / "CONSTITUTION.md").read_text(encoding="utf-8")
        self.assertIn(
            "Owner-reserved actions", text,
            "delegated merge authority without a reserved list is unbounded",
        )
        for reserved in ("force-push", "branch protection", "licensing"):
            with self.subTest(item=reserved):
                self.assertIn(reserved, text)


if __name__ == "__main__":
    unittest.main()
