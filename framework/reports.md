# Completion reports

How a role's completion report reaches Brain, regardless of which tool ran the
role. This document is the baseline; [`adapters.md`](adapters.md) covers
tool-specific conveniences that may sit on top of it.

## The problem this solves

Brain can always see what execution left in the repository — a branch, a
diff, commits. Repository state proves that execution *happened*. It proves
nothing about what execution *said*, and nothing about why nothing changed.

A round that correctly paused after finding there was nothing to do, and a
round that silently crashed mid-task, leave the same trace: no commit, no
diff, a clean checkout. Without the report, Brain cannot tell them apart.

A tool-specific hook that mirrors a session's final reply — Claude Code's
Stop hook is the shipped example — closes this gap for exactly one tool. It
fires only for sessions run there. A project's Worker or Verifier seat is
routinely run on whichever tool the owner chose *that* round, so a
single-tool mechanism is not a fix for the class; it is a fix for one member
of it.

## The baseline mechanism

**Every filesystem-capable Worker or Verifier writes its own completion
report into the repository's shared inbox before ending its turn, in
addition to displaying the same report normally to the owner.**

Not a hook. Not a transcript scraper. Not anything that depends on a
provider's internal storage format staying put — this framework does not
build load-bearing mechanism on undocumented chat databases, and does not
assume one provider's transcript layout survives its next release. This is
the role's own action, taken with the one capability every Worker and
Verifier contract already requires: filesystem and git access. It works
identically on Claude Code, Codex, Antigravity, or a tool that does not
exist yet, because it never asks what tool is running.

### Running it

At the end of your turn, after presenting your report to the owner as
normal, write the same report:

```
python3 tools/report.py write --task <this brief's identifier> <<'REPORT'
<the same report text you just gave the owner>
REPORT
```

`--task` is required — usually the brief's filename. Nothing else needs
supplying: the destination and your role tag are both derived from the
checkout you are in, never from anything you assert. See `tools/report.py`
at the project root for the mechanism and why each guarantee holds; the
essentials:

- The shared inbox is `<git-common-dir>/agent-inbox/`, resolved with
  `git rev-parse --git-common-dir` — the same directory from any worktree of
  one clone, and never version-controlled.
- Your role tag is derived from *which checkout you are in*, per
  [`git-and-isolation.md`](git-and-isolation.md): a linked worktree's own
  name, or `coordinator` for the primary checkout. Two concurrently-active
  roles have two different checkouts, so they write to two different files
  by construction — this relies on the isolation invariant, the same way
  every other role-per-checkout guarantee in this framework does.
- The write is atomic: a reader never sees a half-written report.
- The header records the task, the exact HEAD SHA of your checkout at write
  time, and a timestamp — `python3 tools/report.py status` compares that SHA
  against the checkout's current HEAD and says whether the report is still
  fresh, so a reader does not parse the header by hand.

### This is a contract requirement, not a convenience

Every Worker and Verifier contract already requires "filesystem access,
git, a shell" — see [`roles/worker.md`](roles/worker.md) and
[`roles/verifier.md`](roles/verifier.md). Writing the report costs nothing
beyond that. It is required in the same sense every other MUST in those
contracts is required: stated plainly, and unenforceable against a session
that simply does not follow it, because nothing in a repository can compel
an LLM's next action. That is not a gap unique to this mechanism — it is
true of "never merges" and "never accept your own work" as well, and this
framework's answer has always been the same: make the required action small
and unambiguous, then say plainly what its absence does and does not prove.

## Reading what this produces

**A missing or stale report is UNKNOWN. Never "the task did not happen",
never "the agent failed."** The fallbacks, in order:

1. Check the shared inbox — `<role>-latest.md` for the role you are asking
   about. This now works for every provider, not only ones with a
   convenience hook installed.
2. Ask the owner to paste the report, if nothing automates the handoff.
3. Inspect repository and pull-request state directly. This can confirm
   execution happened — it leaves a branch and a diff whether or not a
   report was ever written. It cannot confirm a review happened, because a
   review leaves only a report.
4. Where none of the above can answer, ask the owner rather than inferring.

**Before trusting a report that is there, check whether it is stale.**
Compare its `head=` field against the checkout's actual current HEAD, or run:

```
python3 tools/report.py status --cwd <the checkout in question>
```

Exit `0` means the report still matches that checkout's current HEAD.
Exit `1` means the checkout has moved on since the report was written —
treat it as describing a superseded state, the same way a stale CI result
would be treated. Exit `2` means no report exists for that checkout's role
at all, which is ordinary and expected whenever a round has not written one
yet, or ran before this mechanism existed in the project.

## How this relates to provider-specific hooks

A tool-specific hook — Claude Code's Stop hook is the shipped example — is
still worth having: it captures a report automatically, without depending on
the model choosing to run a command. Where a tool offers one, an adapter may
wire it. **It should call the functions this file's mechanism provides
rather than reimplementing them**, so a provider convenience and the
baseline never become two sources of truth for the same fact, drifting apart
the way [`adapters.md`](adapters.md) warns any restated policy eventually
does. A project with the Claude Code adapter installed has this at
`.claude/hooks/save_agent_reply.py`: it extracts
Claude Code's own transcript, then hands the text to `tools/report.py`'s
writer for everything after that — the inbox location, the role tag, the
atomic write, the provenance header.

A hook converging onto this mechanism is a convenience layered on top of a
requirement that already holds without it. It changes nothing about what a
missing report means; see [`adapters.md`](adapters.md)'s *Conveniences must
fail loudly* for the general rule this instance follows.

## What was actually investigated, and what remains a limitation

This section is deliberately honest about the boundary, because a project's
own confidence in a mechanism should never exceed what was actually checked
— see [`evidence.md`](evidence.md).

**Claude Code**: has a documented `Stop` hook, invoked with the session's
transcript path on stdin, which is what the shipped adapter uses today —
now refactored to call this file's writer instead of maintaining its own
copy of the inbox logic.

**Codex**: `codex exec --output-last-message <FILE>` is a documented, stable
CLI flag that writes the agent's final message to a file. It is genuinely
useful when a project explicitly dispatches Codex non-interactively — an
adapter is free to wire a wrapper around it that calls this file's writer
the same way Claude Code's hook does. It does **not** cover the ordinary case
this framework centers on: an owner pasting a prompt into an *interactive*
Codex session, which is the ordinary way a role gets launched here. A
first-party hooks system with event names resembling Claude Code's own
(`Stop`, `SubagentStop`, and others) was visible in the installed build
inspected while writing this, but only as internal, unreleased
implementation detail — the CLI shipped no public documentation for it, and
its own version string marked it alpha. That is exactly the kind of surface
this framework declines to build load-bearing mechanism on; if it stabilizes
and documents itself, an adapter can adopt it then. Until it does, the
baseline mechanism in this document is Codex's dependable path, the same as
for any other provider with no adapter.

**Antigravity**: installed but never launched or configured on the machine
this was investigated from, so there was no local session, transcript, or
configuration file to inspect. No claim is made here about its hook or
transcript mechanism, in either direction — an untested claim about a
tool's internals is exactly the failure mode *Guards must actually guard*
warns against. The baseline mechanism does not need that investigation to
succeed: it works for Antigravity the same way it works for any provider
this framework has never specifically adapted to, because it depends only
on the role having a shell and git.
