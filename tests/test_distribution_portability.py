"""What this repository ships has to survive arriving somewhere else.

This repository's product is files that get copied into other people's
checkouts — hook scripts, templates, tools. Two properties of the *committed*
form decide whether they work there, and neither is visible by reading the
file's contents:

**Line endings.** A `#!/bin/sh` script that arrives with CRLF does not run: the
interpreter takes the carriage return as part of the command and fails with
``$'\\r': command not found``. Git for Windows defaults to
``core.autocrlf=true``, so without a `.gitattributes` that pins `eol=lf`, that
is the ordinary outcome there rather than an edge case.

**The executable bit.** Git records mode 100755 or 100644, and a POSIX clone
honours it. Git refuses to run a `pre-push` hook that is not executable, so a
hook committed 100644 is inert in every clone that receives it — silently,
which is the failure mode this framework spends most of its guards on.

Both were wrong here at once: no `.gitattributes` at all, and not one
executable file in the whole repository, including the two shell scripts
adoption installs as hooks. Three downstream projects that were checked all
had their own `.githooks/pre-push` at 100755, so the defect was this
repository's alone — the one place it propagates from.

These guards read git's own index rather than the filesystem. The working
tree can disagree with what is committed, and what is committed is what
someone else receives.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tracked_files() -> list[tuple[str, str]]:
    """(mode, path) for every tracked file, straight from git's index."""
    out = subprocess.run(
        ["git", "ls-files", "-s"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    entries = []
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        entries.append((meta.split()[0], path))
    return entries


def has_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.readline().startswith(b"#!")
    except OSError:
        return False


class TestLineEndingsArePinned(unittest.TestCase):
    """`text=auto` alone is not enough; it still checks out CRLF on Windows."""

    def test_gitattributes_exists_and_is_tracked(self):
        self.assertIn(
            ".gitattributes", [p for _, p in tracked_files()],
            "without a tracked .gitattributes, every shell script this "
            "repository distributes arrives CRLF on a default Git for Windows "
            "clone and fails to execute",
        )

    def test_line_endings_are_forced_to_lf_not_merely_normalised(self):
        text = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        rules = [
            line.strip() for line in text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertTrue(rules, "fail closed: .gitattributes declares no rules")

        catch_all = [r for r in rules if r.split()[0] == "*"]
        self.assertTrue(catch_all, "no catch-all rule; some files stay unpinned")
        self.assertTrue(
            any("eol=lf" in r for r in catch_all),
            "the catch-all rule must say `eol=lf`. `* text=auto` on its own "
            "normalises to LF in the repository but still checks out CRLF on "
            "Windows, which is exactly the case that breaks a #!/bin/sh hook",
        )

    def test_no_committed_file_contains_a_carriage_return(self):
        """The property `.gitattributes` exists to produce, checked directly."""
        offenders = []
        for mode, path in tracked_files():
            if mode == "120000":  # symlink
                continue
            full = ROOT / path
            try:
                blob = full.read_bytes()
            except OSError:
                continue
            if b"\r\n" in blob:
                offenders.append(path)
        self.assertEqual(offenders, [], f"CRLF in committed files: {offenders}")


class TestShippedScriptsAreExecutable(unittest.TestCase):
    """A shebang is a claim that the file can be run. Mode 100644 denies it."""

    def test_every_shebang_file_is_committed_executable(self):
        wrong = [
            path for mode, path in tracked_files()
            if has_shebang(ROOT / path) and mode != "100755"
        ]
        self.assertEqual(
            wrong, [],
            f"these declare a shebang but are committed non-executable, so a "
            f"POSIX clone receives them inert: {wrong}. Fix with "
            f"`git update-index --chmod=+x <path>`",
        )

    def test_the_scan_is_not_vacuous(self):
        shebangs = [p for _, p in tracked_files() if has_shebang(ROOT / p)]
        self.assertGreaterEqual(
            len(shebangs), 5,
            "fail closed: almost no shebang files were found, so the guard "
            "above would pass having checked nothing",
        )

    def test_the_hook_git_itself_executes_is_executable(self):
        """Called out separately because its failure mode is the worst.

        The adapter's wrapper and the Python hook are always invoked through an
        explicit interpreter (`sh …`, `python3 …`), so their mode is a
        consistency matter. `pre-push` is different: git executes it directly
        and skips it when it is not executable, so a 100644 pre-push is a gate
        that reports nothing and blocks nothing.
        """
        modes = dict((p, m) for m, p in tracked_files())
        self.assertEqual(modes.get("templates/githooks/pre-push"), "100755")


class TestScannersAreRunnableWithoutGlue(unittest.TestCase):
    """A guard a consuming repo cannot invoke is a guard it will not use.

    `neutrality.py` and `authority.py` are copied into every adopted project,
    but had no entrypoint: importing them and assembling a scan was the only
    way to run them, so a project wanting a CI check had to write that glue
    first. None of the three downstream projects checked had. An argparse
    entrypoint is the difference between a tool that ships and a tool that
    ships and gets used.

    Tested by running them as subprocesses -- the way a consuming repo's CI
    would -- not by importing `main` and trusting it.
    """

    def _run(self, script: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            # `sys.executable`, not a hardcoded name: the interpreter this
            # suite is already running under is the one that certainly
            # exists here. Hardcoding "python3" is the exact defect
            # `adapters/claude-code/hooks/run_python.sh` exists to avoid.
            [sys.executable, str(ROOT / "tools" / script), *args],
            cwd=ROOT, capture_output=True, text=True,
        )

    def test_authority_scans_a_clean_document_and_exits_zero(self):
        proc = self._run("authority.py", "framework/roles/worker.md")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_authority_finds_the_known_bad_fixture_and_exits_one(self):
        proc = self._run("authority.py", "tests/fixtures/v1_stale_authority.md")
        self.assertEqual(
            proc.returncode, 1,
            "the CLI must report a non-zero status on findings, or CI cannot "
            "use it as a gate",
        )
        self.assertIn("routine-approval", proc.stdout)

    def test_neutrality_scans_clean_and_exits_zero(self):
        proc = self._run(
            "neutrality.py", "framework/roles/", "--roles", "worker,verifier",
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_neutrality_finds_a_provider_shaped_lane_and_exits_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.md"
            bad.write_text(
                "Hand the brief to the Acme Worker this round.\n", encoding="utf-8"
            )
            proc = self._run("neutrality.py", str(bad), "--roles", "worker")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("compound-lane", proc.stdout)

    def test_neutrality_refuses_to_guess_the_role_set(self):
        """Fail closed: every rule is expressed over the declared roles."""
        proc = self._run("neutrality.py", "framework/roles/")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("--roles", proc.stderr)

    def test_both_refuse_to_report_success_having_scanned_nothing(self):
        for script in ("authority.py", "neutrality.py"):
            with self.subTest(script=script):
                args = ["no/such/path"]
                if script == "neutrality.py":
                    args += ["--roles", "worker"]
                proc = self._run(script, *args)
                self.assertEqual(
                    proc.returncode, 2,
                    "a scan that matched no files must not exit 0; "
                    "'nothing was checked' is the unsafe case",
                )


if __name__ == "__main__":
    unittest.main()
