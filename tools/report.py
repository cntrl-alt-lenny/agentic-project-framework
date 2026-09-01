#!/usr/bin/env python3
"""Write a role's completion report into the shared, provider-neutral inbox.

THE PROBLEM. Brain can always see what execution left in the repository — a
branch, a diff, commits. It cannot see what execution *said*, because a
completion report is prose, not repository state, and repository state proves
that execution happened, never that a review happened, and never *why* nothing
changed. A round that correctly paused after finding nothing to do and a round
that silently crashed both leave an identical trace: no commit, no diff, a
clean checkout. Without the report, they are indistinguishable.

Claude Code's Stop hook solved this for one tool by mirroring a session's final
reply automatically. That is real, but it is provider-specific by construction
— it fires only for sessions run on that one tool, and a project's Worker or
Verifier seat is routinely run on whichever tool the owner chose *this* round.
A mechanism that only works for one provider is not a fix for the class.

THE MECHANISM THIS FILE IS. Not a hook, not a transcript scraper, not anything
that depends on a provider's internal storage format staying put. It is a
plain command a role's OWN CONTRACT tells it to run, as the last thing it does,
using the one capability every role in this framework already requires:
filesystem and git access. A tool-specific hook is a convenience that captures
a session from the *outside*. This is the role writing its own report from the
*inside*, which works identically whether the model is on Claude Code, Codex,
Antigravity, or a tool that does not exist yet — because it never asks what
tool is running. Provider-specific hooks are welcome to call the functions in
this module as their own writer, so a provider convenience and this baseline
never become two sources of truth for the same fact. See
`../framework/reports.md` for the full mechanism, the header format, and how
Brain reads what this writes.

Guarantees this module is responsible for, and how:

  * **Resolves the shared inbox from any worktree.** `git rev-parse
    --git-common-dir` names the same directory from every worktree of one
    clone, wherever it was cloned. The inbox lives inside it, which git treats
    as private and never version-controls.
  * **Identifies the role without asking anyone.** Never a CLI flag, never a
    provider's session metadata, never something a report could lie about.
    `git-and-isolation.md` puts one role per checkout; a linked worktree's own
    directory name already matches its role, and the primary checkout — where
    `--git-dir` and `--git-common-dir` coincide, which holds regardless of what
    either directory is called — is the coordinating role, tagged
    `coordinator` rather than guessed from a project's own name for that seat.
  * **Writes atomically.** Write to a temp file beside the target, then
    `os.replace`, which is an atomic rename on both POSIX and Windows within one
    filesystem. A reader never observes a half-written report.
  * **Cannot silently overwrite another lane's report.** Two concurrently-active
    roles have two different checkouts by the isolation invariant, so their role
    tags differ by construction and they write to different files. This module
    does not enforce the isolation invariant; it relies on it, the same way
    every other role-per-checkout guarantee in this framework does.
  * **Carries provenance a reader can act on.** Every write is stamped with the
    task/brief this report is for, the exact HEAD SHA of the checkout at write
    time, and a timestamp. `status` compares that SHA against the checkout's
    *current* HEAD, so a reader does not have to parse the header by hand to
    tell a fresh report from a stale one.

What this module deliberately does NOT do: decide whether a report is good,
guess a role's identity from anything self-reported, or make writing it
happen. Nothing here can force an agent to run this command — that remains the
role contract's job, the same as every other MUST in a contract an LLM reads
and decides whether to follow. A missing report is UNKNOWN, never evidence of
failure; see the constitution's *Unknown means unknown*.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

__all__ = [
    "ReportError",
    "Provenance",
    "git_common_dir",
    "role_tag",
    "head_sha",
    "write_report",
    "check_status",
]


class ReportError(Exception):
    """The repository state needed to write or check a report is unavailable.

    Raised, never swallowed, so a caller decides its own failure posture. The
    CLI's ``write`` command fails loudly on this, because the agent invoking it
    directly needs to know a report was not actually recorded. A provider hook
    calling `write_report` is free to catch this and stay silent, matching its
    own "never block a session" contract -- see
    `adapters/claude-code/hooks/save_agent_reply.py` for that shape.
    """


def _git(args: list[str], cwd: str | Path | None = None) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], stderr=subprocess.DEVNULL, text=True, cwd=cwd,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None


def _resolve(raw: str, cwd: str | Path | None) -> Path:
    path = Path(raw)
    if not path.is_absolute():
        base = Path(cwd) if cwd else Path.cwd()
        path = (base / path).resolve()
    return path


def git_common_dir(cwd: str | Path | None = None) -> Path:
    """The repository's shared git directory, resolved from any worktree."""
    raw = _git(["rev-parse", "--git-common-dir"], cwd=cwd)
    if not raw:
        raise ReportError(
            "not inside a git repository, or git is unavailable"
        )
    return _resolve(raw, cwd)


def role_tag(cwd: str | Path | None = None) -> str:
    """This checkout's role, derived structurally -- see the module docstring."""
    toplevel = _git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if not toplevel:
        raise ReportError(
            "not inside a git repository, or git is unavailable"
        )
    git_dir = _git(["rev-parse", "--git-dir"], cwd=cwd)
    common_dir = _git(["rev-parse", "--git-common-dir"], cwd=cwd)
    is_primary = (
        git_dir is not None
        and common_dir is not None
        and _resolve(git_dir, cwd) == _resolve(common_dir, cwd)
    )
    role = "coordinator" if is_primary else Path(toplevel).name
    return "".join(c for c in role if c.isalnum() or c in "-_") or "unknown"


def head_sha(cwd: str | Path | None = None) -> str | None:
    """The exact HEAD SHA of this checkout, or None if it cannot be read.

    Meaningful even for a round that made no commit: it names the state the
    checkout was actually at when the report was written, which is exactly what
    a later staleness check needs -- not "what changed", but "has this checkout
    moved since".
    """
    return _git(["rev-parse", "HEAD"], cwd=cwd)


#: The auto-seeded inbox README. Generalised from the Claude Code adapter's own
#: copy: this is now the canonical wording, and that adapter's hook reuses it
#: via `_seed_readme` rather than keeping a second copy that could drift.
README = """# agent-inbox

Auto-populated by `tools/report.py`, called either directly by a role's own
contract or by a provider-specific convenience hook that calls the same
writer. Each `<role>-latest.md` holds the most recent completion report from
the matching checkout. `coordinator-latest.md` is the coordinating role's own
report, from the project's primary checkout -- tagged `coordinator` rather
than the project's name, and rather than whatever this project calls that
role, because the role tag is derived from checkout structure, never
self-reported or read from `AGENTS.md`.

**A missing or stale file means UNKNOWN, never that a task did not happen or
that a review did not run.** Not every role runs this command every round --
see `framework/reports.md` for when it is expected and what its absence does
and does not prove. Check the `head=` field in a report's header against the
checkout's current `git rev-parse HEAD`, or run
`python tools/report.py status --cwd <checkout>`, before trusting a report
whose checkout may have moved on since it was written.

Not under version control: this lives inside git's own directory.
"""


def _atomic_write(path: Path, content: str) -> None:
    """Write-then-rename, so a reader never observes a partially-written file."""
    tmp = path.with_name(f"{path.name}.tmp-{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _seed_readme(inbox: Path) -> None:
    readme = inbox / "README.md"
    if not readme.exists():
        _atomic_write(readme, README)


def _header(*, role: str, task: str, sha: str, source: str, stamp: str) -> str:
    return (
        f"<!-- captured {stamp} role={role} task={task} head={sha} "
        f"source={source} -->\n\n"
    )


def write_report(
    text: str,
    *,
    task: str,
    cwd: str | Path | None = None,
    source: str = "report.py",
) -> Path:
    """Atomically write this checkout's completion report to the shared inbox.

    ``task`` is required: without it, two reports from the same role that left
    HEAD unchanged -- two consecutive investigative rounds, say -- would be
    indistinguishable by SHA alone. A brief's own filename (see
    `framework/lifecycle.md`'s naming convention) is the natural value.

    Returns the path written. Raises `ReportError` rather than writing a
    partial or misattributed report -- see that class's docstring for why
    callers should not swallow it uniformly.
    """
    body_text = text.strip()
    if not body_text:
        raise ReportError("report text is empty")
    if not task or not task.strip():
        raise ReportError("a task/brief identifier is required")

    inbox = git_common_dir(cwd) / "agent-inbox"
    role = role_tag(cwd)
    sha = head_sha(cwd) or "unknown"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    inbox.mkdir(parents=True, exist_ok=True)
    _seed_readme(inbox)

    header = _header(role=role, task=task.strip(), sha=sha, source=source, stamp=stamp)
    body = header + body_text + "\n"

    latest = inbox / f"{role}-latest.md"
    _atomic_write(latest, body)

    log = inbox / f"{role}-log.md"
    with log.open("a", encoding="utf-8") as f:
        f.write(f"\n\n---\n\n{header}{body_text}\n")

    return latest


@dataclass(frozen=True)
class Provenance:
    """What a report's header claims, read back."""

    role: str
    task: str | None
    head: str | None
    source: str | None
    stamp: str | None


def _parse_header(text: str) -> Provenance | None:
    first_line = text.splitlines()[0] if text else ""
    if not first_line.startswith("<!-- captured "):
        return None
    fields: dict[str, str] = {}
    inner = first_line[len("<!-- captured ") : -len(" -->")] if first_line.endswith(" -->") else first_line
    parts = inner.split(" ")
    stamp = parts[0] if parts else None
    for part in parts[1:]:
        if "=" in part:
            key, _, value = part.partition("=")
            fields[key] = value
    return Provenance(
        role=fields.get("role", ""),
        task=fields.get("task"),
        head=fields.get("head"),
        source=fields.get("source"),
        stamp=stamp,
    )


def check_status(cwd: str | Path | None = None) -> tuple[int, str]:
    """Is the latest report for THIS checkout's role still fresh?

    "This checkout's role" -- the same auto-derivation `write_report` uses, so
    a reader compares against the correct file without ever naming a role by
    hand. Returns (exit_code, message): 0 fresh, 1 stale (checkout has moved
    since the report was written), 2 no report found for this role.
    """
    role = role_tag(cwd)
    inbox = git_common_dir(cwd) / "agent-inbox"
    latest = inbox / f"{role}-latest.md"
    if not latest.is_file():
        return 2, f"no report found for role '{role}' at {latest}"

    provenance = _parse_header(latest.read_text(encoding="utf-8"))
    current = head_sha(cwd)
    if provenance is None or provenance.head is None:
        return 1, f"{latest} has no readable provenance header; treat as stale"
    if current is None:
        return 1, f"could not read this checkout's current HEAD to compare against {latest}"
    if provenance.head != current:
        return 1, (
            f"stale: {latest} was written at head={provenance.head}, "
            f"this checkout is now at {current}"
        )
    return 0, (
        f"fresh: {latest} (task={provenance.task}, written {provenance.stamp}) "
        f"matches current head {current}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser(
        "write", help="write this checkout's completion report to the shared inbox"
    )
    write_p.add_argument(
        "--task", required=True,
        help="the brief/round this report is for (e.g. its filename)",
    )
    write_p.add_argument(
        "--file", help="read the report from this file instead of stdin"
    )
    write_p.add_argument(
        "--source", default="cli",
        help="who invoked this -- informational only, never role identity",
    )

    status_p = sub.add_parser(
        "status",
        help="check whether the latest report for this checkout's role is fresh",
    )
    status_p.add_argument(
        "--cwd", default=None,
        help="checkout to check from (default: the current directory)",
    )

    args = ap.parse_args(argv)

    if args.command == "write":
        text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
        try:
            path = write_report(text, task=args.task, source=args.source)
        except ReportError as exc:
            print(f"report: {exc}", file=sys.stderr)
            return 1
        print(f"report: wrote {path}")
        return 0

    if args.command == "status":
        try:
            code, message = check_status(args.cwd)
        except ReportError as exc:
            print(f"report: {exc}", file=sys.stderr)
            return 3
        print(message)
        return code

    return 2  # pragma: no cover - argparse enforces a valid subcommand


if __name__ == "__main__":
    sys.exit(main())
