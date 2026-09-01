#!/usr/bin/env python3
"""Mirror a session's final reply to a shared location.

A CONVENIENCE, NOT A CONTROL. Read this part before relying on anything it
writes:

  * It fires only for sessions run on this one tool. A round run on any other
    tool writes nothing here, and that is normal.
  * Therefore **a missing or stale file means UNKNOWN** — never "the task did
    not happen", "the agent failed", or "the review did not run". The fallbacks,
    in order, are: the owner pastes the report; inspect repository and pull
    request state directly; and where that genuinely cannot answer, ask the
    owner. Repository state can confirm that execution happened, because
    execution leaves a branch and a diff. It cannot confirm that a review
    happened, because a review leaves only a report.
  * Check the timestamp before trusting a file that is there.

Why these path choices:

  * ``git rev-parse --git-common-dir`` gives the repository's shared git
    directory — the same value from every worktree of the same clone, wherever
    it was cloned.
  * The inbox lives inside that directory, which git treats as private and never
    version-controls. No ignore entry needed, and it disappears with the clone.
  * The role tag is the basename of the current worktree, matching the isolation
    convention of one checkout per concurrently-active role — with one
    exception: ``git-and-isolation.md`` puts the coordinating role in the
    project's own primary checkout, named after the *project*, not the role.
    Tagging that with its basename would mislabel every one of the
    coordinating role's own reports as a project-named executor. See
    ``_role_tag`` for how the primary checkout is told apart from a linked
    worktree — the git-native way, not by guessing what a project calls its
    coordinating role.

Requirements: python and git — reached through ``run_save_agent_reply.sh``'s
wrapper, which tries the Python 3 this host actually has rather than one
hardcoded name. Non-blocking by design — any error exits 0, since a session
must never fail to end because of this.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _git(args: list[str]) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _last_assistant_text(transcript_path: Path) -> str | None:
    """Final assistant turn from a JSONL transcript, or None."""
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None

    last = None
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = entry.get("role") or entry.get("message", {}).get("role")
        if role == "assistant":
            last = entry
    if last is None:
        return None

    content = last.get("content") or last.get("message", {}).get("content")
    if isinstance(content, str):
        return content.strip() or None
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip() or None


README = """# agent-inbox

Auto-populated by the provider adapter's session-end hook. Each
`<role>-latest.md` holds the final reply of the most recent session that ran in
the matching checkout. `coordinator-latest.md` is the coordinating role's own
report, from the project's primary checkout — tagged `coordinator` rather than
the project's name, and rather than whatever this project calls that role,
because the hook has no way to read that decision out of `AGENTS.md`.

**A missing or stale file means UNKNOWN, never that a task did not happen.** The
hook fires only for one tool; a round run on any other tool writes nothing here.
Check timestamps. Fall back to a pasted report, then to repository and pull
request state, then ask the owner.

**A `claude-code-health.md` file means something different: this hook DID run,
on this host, and could not find a Python 3 to finish with.** That is not
UNKNOWN in the same sense — it is a configuration defect on this particular
clone, not silence from a session that used a different tool. Fix the host (a
`python3`, or a Windows `py` with Python 3 registered, needs to be on PATH) and
expect the next session on it to write a normal report. Its absence proves
nothing either way: most hosts never write it, because most hosts have a
working interpreter.

Not under version control: this lives inside git's own directory.
"""


def _seed_readme(inbox: Path) -> None:
    readme = inbox / "README.md"
    if not readme.exists():
        readme.write_text(README, encoding="utf-8")


def _role_tag(worktree_root: str | None) -> str:
    """The role this checkout belongs to, or ``coordinator`` for the primary one.

    A linked worktree (``git worktree add``) is created *as* the checkout for
    one role, so its own basename already matches the isolation convention in
    ``git-and-isolation.md`` — whatever a project names that directory is the
    role, which generalises to any layout the convention allows, not only
    ``.worktrees/<role>``.

    The **primary** checkout is different. ``git-and-isolation.md`` puts the
    coordinating role there, in a directory named after the *project*. Using
    that basename tagged every one of the coordinating role's own reports as
    if it were a project-named executor — indistinguishable from a role that
    happens to share the project's name. Detected the git-native way instead:
    ``git rev-parse --git-dir`` and ``--git-common-dir`` coincide only in the
    primary working tree; a linked worktree's git-dir lives inside the common
    one. That holds regardless of what either directory is called, and
    regardless of what a project has named its coordinating role — this file
    has no way to know that without reading the project's own ``AGENTS.md``,
    so it does not guess it.
    """
    if not worktree_root:
        return "unknown"

    git_dir = _git(["rev-parse", "--git-dir"])
    common_dir = _git(["rev-parse", "--git-common-dir"])
    is_primary = (
        git_dir is not None
        and common_dir is not None
        and Path(git_dir).resolve() == Path(common_dir).resolve()
    )
    role = "coordinator" if is_primary else Path(worktree_root).name
    return "".join(c for c in role if c.isalnum() or c in "-_") or "unknown"


def main() -> int:
    try:
        raw = sys.stdin.read()
    except (OSError, KeyboardInterrupt):
        return 0
    if not raw.strip():
        return 0
    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        return 0

    transcript = event.get("transcript_path")
    if not transcript:
        return 0
    transcript_path = Path(transcript)
    if not transcript_path.exists():
        return 0

    text = _last_assistant_text(transcript_path)
    if not text:
        return 0

    common_dir = _git(["rev-parse", "--git-common-dir"])
    if not common_dir:
        return 0
    common = Path(common_dir)
    if not common.is_absolute():
        common = (Path.cwd() / common).resolve()
    inbox = common / "agent-inbox"
    try:
        inbox.mkdir(parents=True, exist_ok=True)
        _seed_readme(inbox)
    except OSError:
        return 0

    worktree_root = _git(["rev-parse", "--show-toplevel"])
    role = _role_tag(worktree_root)

    session_id = event.get("session_id", "")
    stamp = datetime.now().isoformat(timespec="seconds")
    header = (
        f"<!-- captured {stamp} from checkout role={role}"
        f"{f' session={session_id}' if session_id else ''} -->\n\n"
    )

    try:
        (inbox / f"{role}-latest.md").write_text(header + text + "\n", encoding="utf-8")
    except OSError:
        return 0

    try:
        with (inbox / f"{role}-log.md").open("a", encoding="utf-8") as f:
            f.write(f"\n\n---\n\n{header}{text}\n")
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
