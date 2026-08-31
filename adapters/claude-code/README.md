# Claude Code adapter

An **example** adapter, and the reference for the shape described in
[`../../framework/adapters.md`](../../framework/adapters.md). Nothing in the
framework depends on it. A project with no adapter at all works fine via the
universal launch procedure.

Install with `--adapter claude-code`, which places these files at `.claude/` in
the target repository.

## What it provides

| File | Provides |
|---|---|
| `agents/<role>.md` | Named seats. Each is frontmatter plus a pointer to the canonical contract. |
| `commands/status.md` | One command that runs the coordinating role's rehydration sequence. |
| `hooks/save_agent_reply.py` | Mirrors a session's final reply to a shared location, so reports need less manual relaying. |
| `settings.json` | Wires the hook. |

## What it deliberately does not provide

No authority statement, no role definitions, no branch convention, no queue, no
gate. Those are the contract's, and an adapter that restated them would become a
second source of truth that drifts. A test enforces this.

## The inbox is not load-bearing

`hooks/save_agent_reply.py` only fires for this tool. A round run on any other
tool writes nothing there — and a project may well *prefer* a different tool for
the reviewer seat, which makes an empty file the expected case, not a signal.

**A missing or stale file means UNKNOWN.** Never "the task did not happen". The
fallbacks are in the constitution under *Unknown means unknown*. Check the
timestamp before trusting a file that is there.
