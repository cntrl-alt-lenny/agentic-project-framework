"""The Claude Code Stop hook must not go inert when one interpreter name is missing.

THE INCIDENT. `settings.json` invoked a single hardcoded interpreter name
directly. On a fresh macOS machine with only `python3` on PATH, that name was
not found: the operating system never started the process, so neither Claude
Code nor `save_agent_reply.py` ever ran, and the Stop hook completing with
nothing to show read exactly like a session that had nothing to report. The
coordinating role read this as "no hook" and fell back to inspecting the
working tree — the right fallback, reached for the wrong reason: the convenience
was not absent, it was broken.

THE DEFECT CLASS, stated so a fix cannot just move the string: *an optional
provider adapter convenience must not silently become inert merely because the
same repository is used on a supported host where the interpreter command
differs.* Replacing the hardcoded name with `python3` reverses the same defect
on the hosts — real ones, per the report that found this — with only `python`
or only a Windows `py` launcher on PATH.

THE FIX, entirely inside this one adapter, never touching a role contract:
`settings.json` now invokes `hooks/run_python.sh` with the hook script as
an argument. The shim tries the
realistic candidates in order and only falls back to the next one if the
current one fails to complete cleanly — catching not just "not found" but "this
name resolves to something that is not a working Python 3". If nothing works,
it leaves `claude-code-health.md` in the shared inbox: an artifact that exists
*because* the hook ran and could not finish, which is the observable difference
between "broken here" and the ordinary silence of a round run on another tool.

These tests are behavioural per `framework/evidence.md`: they adopt into a real
temporary git repository and execute the actual configured launch path —
`sh .claude/hooks/run_python.sh .claude/hooks/save_agent_reply.py`, exactly
as `settings.json` names it
— under a controlled, restricted PATH, rather than checking that files exist or
reading the script's source for the word "python3".
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adopt  # noqa: E402

IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".pytest_cache")

#: A finished assistant turn, shaped the way Claude Code's own transcript is:
#: JSONL, one entry per turn, final assistant message may be a content-block list.
TRANSCRIPT = "\n".join((
    json.dumps({"role": "user", "message": {"role": "user", "content": "hi"}}),
    json.dumps({
        "role": "assistant",
        "message": {"role": "assistant",
                    "content": [{"type": "text", "text": "Final reply text."}]},
    }),
))


def require_sh() -> str:
    """The absolute path to `sh`, or skip.

    Not resolved through a restricted-PATH subprocess env: Python's own
    subprocess launch looks `sh` up using the *env passed to the child*, so a
    bare `"sh"` would fail to launch at all once the test narrows PATH to the
    candidates it is deliberately testing. The path to `sh` itself is a fact
    about the outer test host, not about the interpreter search under test.
    """
    found = shutil.which("sh")
    if found is None:
        raise unittest.SkipTest(
            "no POSIX sh on this host; the launcher's own coverage boundary "
            "excludes hosts without one, see adapters/claude-code/README.md"
        )
    return found


def init_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=path, check=True)
    (path / "f").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", "add", "f"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=path, check=True)


def adopt_with_claude_code(target: Path) -> None:
    assert adopt.main(
        [str(target), "--project", "Hook Test", "--adapter", "claude-code"]
    ) == 0


def make_interpreter_dir(*, extra_names: tuple[str, ...] = ()) -> Path:
    """A directory containing only the external commands the launcher needs,
    plus whichever Python-shaped names ``extra_names`` asks for.

    Each Python-shaped name is a small wrapper script that ``exec``s the real
    interpreter with a stable argv[0], not a bare symlink: on macOS, the system
    ``/usr/bin/python3`` behaves differently depending on the name it is
    invoked as, which would make a symlinked ``python`` fail for a reason that
    has nothing to do with the mechanism under test.
    """
    real_python3 = sys.executable
    bindir = Path(tempfile.mkdtemp(prefix="claude-code-hook-path-"))
    for tool in ("git", "date", "mkdir", "dirname", "cat"):
        found = shutil.which(tool)
        assert found, f"host is missing {tool}, needed to run this test at all"
        (bindir / tool).symlink_to(found)
    for name in extra_names:
        wrapper = bindir / name
        if name == "py":
            # Mimic the real Windows `py` launcher closely enough for this:
            # it accepts a leading `-3` version selector that a bare Python
            # binary does not understand, so a faithful stand-in has to strip
            # it rather than just forward argv unchanged.
            lines = [
                "#!/bin/sh",
                'if [ "$1" = "-3" ]; then shift; fi',
                f'exec {real_python3} "$@"',
                "",
            ]
        else:
            lines = ["#!/bin/sh", f'exec {real_python3} "$@"', ""]
        wrapper.write_text("\n".join(lines), encoding="utf-8")
        wrapper.chmod(0o755)
    return bindir


def run_launcher(
    target: Path, *, path_dir: Path, session_id: str, sh: str,
) -> subprocess.CompletedProcess:
    transcript = target / f"transcript-{session_id}.jsonl"
    transcript.write_text(TRANSCRIPT, encoding="utf-8")
    payload = json.dumps({
        "transcript_path": str(transcript), "session_id": session_id,
    })
    return subprocess.run(
        [sh, ".claude/hooks/run_python.sh", ".claude/hooks/save_agent_reply.py"],
        cwd=target, input=payload, capture_output=True, text=True,
        env={"PATH": str(path_dir), "HOME": str(target)},
    )


def inbox_dir(target: Path) -> Path:
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=target, capture_output=True, text=True, check=True,
    ).stdout.strip()
    common_path = Path(common)
    if not common_path.is_absolute():
        common_path = (target / common_path).resolve()
    return common_path / "agent-inbox"


class HookHarness(unittest.TestCase):
    """One adopted, git-initialised temporary repository, shared per test."""

    def setUp(self):
        self.sh = require_sh()
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)
        init_repo(self.target)
        adopt_with_claude_code(self.target)
        self.addCleanup(self._tmp.cleanup)


class TestConfiguredLaunchPathFindsAWorkingInterpreter(HookHarness):
    """Behaviour, not installation: actually run what settings.json names."""

    def test_settings_json_names_the_wrapper_not_the_hook_directly(self):
        settings = json.loads(
            (self.target / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        command = settings["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertIn("run_python.sh", command)
        self.assertIn("save_agent_reply.py", command)

    def test_python3_on_path_produces_a_report(self):
        path_dir = make_interpreter_dir(extra_names=("python3",))
        proc = run_launcher(self.target, path_dir=path_dir, session_id="py3", sh=self.sh)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        latest = inbox_dir(self.target) / "coordinator-latest.md"
        self.assertTrue(latest.is_file(), "no report written with python3 present")
        self.assertIn("Final reply text.", latest.read_text(encoding="utf-8"))

    def test_only_bare_python_on_path_still_produces_a_report(self):
        """The actual reported incident's mirror image.

        `python3` missing broke the old hardcoded command; a fix that just
        swapped in `python3` would break equally real hosts that have only
        `python`. This is the guard against reversing the defect rather than
        closing it.
        """
        path_dir = make_interpreter_dir(extra_names=("python",))
        proc = run_launcher(self.target, path_dir=path_dir, session_id="py-only", sh=self.sh)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        latest = inbox_dir(self.target) / "coordinator-latest.md"
        self.assertTrue(
            latest.is_file(),
            "no report written with only `python` on PATH; a fix that only "
            "helps `python3` hosts reverses the same defect elsewhere",
        )
        self.assertIn("Final reply text.", latest.read_text(encoding="utf-8"))

    def test_windows_py_launcher_is_tried(self):
        path_dir = make_interpreter_dir(extra_names=("py",))
        proc = run_launcher(self.target, path_dir=path_dir, session_id="py-launcher", sh=self.sh)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        latest = inbox_dir(self.target) / "coordinator-latest.md"
        self.assertTrue(latest.is_file(), "the `py` launcher candidate was not tried")

    def test_original_hardcoded_command_would_have_failed_here(self):
        """Confirms the restricted PATH actually exercises the defect.

        Without this, `test_only_bare_python...` above could pass vacuously if
        the restricted PATH accidentally still exposed `python3` from
        somewhere.
        """
        path_dir = make_interpreter_dir(extra_names=("python",))
        proc = subprocess.run(
            [self.sh, "-c", "python3 --version"],
            cwd=self.target, capture_output=True, text=True,
            env={"PATH": str(path_dir)},
        )
        self.assertNotEqual(
            proc.returncode, 0,
            "python3 unexpectedly resolved in the restricted PATH; this test's "
            "isolation is not doing what it claims",
        )


class TestNoInterpreterIsDistinctFromNoReport(HookHarness):
    """The health-check path: item 6's actual mechanism."""

    def test_no_interpreter_leaves_a_health_marker_not_a_report(self):
        path_dir = make_interpreter_dir()  # no python-shaped name at all
        proc = run_launcher(self.target, path_dir=path_dir, session_id="none", sh=self.sh)
        self.assertEqual(
            proc.returncode, 0,
            "the launcher must exit 0 even when nothing was found -- a "
            "session must never fail to end over this",
        )
        inbox = inbox_dir(self.target)
        self.assertFalse(
            (inbox / "coordinator-latest.md").exists(),
            "a report was written despite no interpreter being available",
        )
        health = inbox / "claude-code-health.md"
        self.assertTrue(
            health.is_file(),
            "no health marker was left; a broken host now looks identical to "
            "ordinary absence, which is the exact incident this closes",
        )
        self.assertIn("python3", health.read_text(encoding="utf-8"))

    def test_the_health_marker_and_a_role_report_are_never_confused(self):
        """A cold Brain must be able to tell these apart by filename alone."""
        for name in ("coordinator-latest.md", "worker-latest.md", "verifier-latest.md"):
            self.assertNotEqual(name, "claude-code-health.md")

    def test_absence_of_the_health_file_proves_nothing(self):
        """Most hosts work and never write it -- its absence stays UNKNOWN."""
        path_dir = make_interpreter_dir(extra_names=("python3",))
        run_launcher(self.target, path_dir=path_dir, session_id="healthy", sh=self.sh)
        self.assertFalse(
            (inbox_dir(self.target) / "claude-code-health.md").exists(),
            "a healthy run must not write the failure marker",
        )


class TestRoleTaggingFollowsTheIsolationConvention(HookHarness):
    """Item 8: the primary checkout is not named after a role."""

    def test_the_primary_checkout_is_tagged_coordinator(self):
        path_dir = make_interpreter_dir(extra_names=("python3",))
        run_launcher(self.target, path_dir=path_dir, session_id="primary", sh=self.sh)
        inbox = inbox_dir(self.target)
        self.assertTrue((inbox / "coordinator-latest.md").is_file())
        # The defect this replaces: tagged with the project's own directory
        # name, which is `self.target.name` here.
        self.assertFalse(
            (inbox / f"{self.target.name}-latest.md").exists(),
            "the primary checkout was tagged with the project's name instead "
            "of the coordinating role",
        )

    def test_a_linked_worktree_is_tagged_with_its_own_name(self):
        subprocess.run(
            ["git", "worktree", "add", "--detach", ".worktrees/worker", "HEAD"],
            cwd=self.target, check=True, capture_output=True,
        )
        worker_dir = self.target / ".worktrees" / "worker"
        path_dir = make_interpreter_dir(extra_names=("python3",))
        transcript = self.target / "transcript-worker.jsonl"
        transcript.write_text(TRANSCRIPT, encoding="utf-8")
        payload = json.dumps({
            "transcript_path": str(transcript), "session_id": "worker-session",
        })
        proc = subprocess.run(
            [self.sh, "../../.claude/hooks/run_python.sh",
             "../../.claude/hooks/save_agent_reply.py"],
            cwd=worker_dir, input=payload, capture_output=True, text=True,
            env={"PATH": str(path_dir), "HOME": str(self.target)},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inbox = inbox_dir(worker_dir)
        self.assertTrue(
            (inbox / "worker-latest.md").is_file(),
            "a linked worktree named 'worker' must produce worker-latest.md",
        )
        self.assertFalse((inbox / "coordinator-latest.md").exists())


class TestTheDefectReproducesAgainstTheReportedShape(unittest.TestCase):
    """Red-before-green: the exact incident, and the exact stale role tag.

    Copies the repository, reverts `settings.json` to the single hardcoded
    invocation this incident actually shipped with, and reverts the role-tag
    fix to the plain worktree-basename it replaced -- then proves both fail
    the way the report described.
    """

    def setUp(self):
        self.sh = require_sh()
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name) / "repo"
        shutil.copytree(ROOT, self.repo, ignore=IGNORE)
        self.addCleanup(self._tmp.cleanup)

    def _adopted_target(self) -> Path:
        target = Path(self._tmp.name) / "target"
        target.mkdir()
        init_repo(target)
        proc = subprocess.run(
            [sys.executable, str(self.repo / "tools" / "adopt.py"),
             str(target), "--project", "Hook Test", "--adapter", "claude-code"],
            cwd=self.repo, capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return target

    def test_the_old_hardcoded_command_goes_inert_on_a_python3_only_host(self):
        settings_path = self.repo / "adapters" / "claude-code" / "settings.json"
        settings_path.write_text(
            settings_path.read_text(encoding="utf-8").replace(
                "sh .claude/hooks/run_python.sh .claude/hooks/save_agent_reply.py",
                "python .claude/hooks/save_agent_reply.py",
            ),
            encoding="utf-8",
        )
        target = self._adopted_target()

        # A host with a real Python 3 available only as `python3` -- exactly
        # the machine the incident was reported on.
        path_dir = make_interpreter_dir(extra_names=("python3",))
        transcript = target / "transcript-regress.jsonl"
        transcript.write_text(TRANSCRIPT, encoding="utf-8")
        payload = json.dumps({
            "transcript_path": str(transcript), "session_id": "regress",
        })
        proc = subprocess.run(
            [self.sh, "-c", "python .claude/hooks/save_agent_reply.py"],
            cwd=target, input=payload, capture_output=True, text=True,
            env={"PATH": str(path_dir), "HOME": str(target)},
        )
        self.assertNotEqual(
            proc.returncode, 0,
            "the pre-fix hardcoded `python` command unexpectedly succeeded on "
            "a python3-only PATH; this does not reproduce the incident",
        )
        self.assertFalse(
            (inbox_dir(target) / "coordinator-latest.md").exists(),
            "the pre-fix command produced a report despite naming an "
            "interpreter absent from PATH; the reproduction is not faithful",
        )

    def test_the_old_role_tag_names_the_project_not_the_role(self):
        """The role-tag fix now lives in `tools/report.py`, not this hook.

        `save_agent_reply.py` has been converged onto that shared writer -- see
        `framework/reports.md` -- so reproducing the original defect means
        mutating the mechanism it now delegates to, not the hook itself. This
        is also the strongest proof the convergence is real: a regression in
        the shared module breaks the Claude Code path too, exactly because
        there is no longer a second implementation to be independently
        correct.
        """
        report_path = self.repo / "tools" / "report.py"
        text = report_path.read_text(encoding="utf-8")
        # Restore the exact pre-fix derivation this replaced.
        marker = (
            'role = "coordinator" if is_primary else Path(toplevel).name'
        )
        self.assertIn(marker, text, "fixture out of sync with tools/report.py")
        text = text.replace(marker, "role = Path(toplevel).name")
        report_path.write_text(text, encoding="utf-8")

        target = self._adopted_target()
        path_dir = make_interpreter_dir(extra_names=("python3",))
        proc = run_launcher(target, path_dir=path_dir, session_id="stale-tag", sh=self.sh)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        inbox = inbox_dir(target)
        self.assertTrue(
            (inbox / f"{target.name}-latest.md").is_file(),
            "reverting the role-tag fix should reproduce project-named "
            "reports from the primary checkout",
        )
        self.assertFalse((inbox / "coordinator-latest.md").exists())


if __name__ == "__main__":
    unittest.main()
