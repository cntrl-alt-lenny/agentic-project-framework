# Claude Code adapter

An **example** adapter, and the reference for the shape described in
[`../../framework/adapters.md`](../../framework/adapters.md). Nothing in the
framework depends on it. A project with no adapter at all works fine via the
universal launch procedure.

Install with `--adapter claude-code`. Its destination is declared in
[`adapter.json`](adapter.json) — `.claude/` in the target repository, which is
where this tool reads project settings, agents, commands and hooks from.

**The destination is declared, not derived from the adapter's name.** The two
are different things: `claude-code` is how a project asks for this adapter on
the command line, `.claude/` is where the tool looks. Adoption used to build
the second from the first, which put every file in a directory the tool never
reads. See [`../../tools/adapters.py`](../../tools/adapters.py) for the
manifest format and [`../../tests/test_adapter_install_layout.py`](../../tests/test_adapter_install_layout.py)
for the guards that keep the two from drifting apart again.

## What it provides

Installed under `.claude/`:

| File | Provides |
|---|---|
| `agents/brain.md`, `agents/worker.md`, `agents/verifier.md` | One seat per **role contract** — exactly these three, never more. Each is frontmatter plus a pointer to the canonical contract. |
| `commands/status.md` | One command that runs the coordinating role's rehydration sequence. |
| `hooks/save_agent_reply.py` | Mirrors a session's final reply to a shared location, so reports need less manual relaying. |
| `settings.json` | Wires the hook. |

## Specialist executors share the executor seat

A project may declare specialist executor names — `adopt.py --workers
decomper,scaffolder`. **This adapter generates no file for them, deliberately.**
A specialist is the executor contract plus a scope statement, not a second
contract, so there is nothing for a separate seat file to point at: there is no
`docs/agents/roles/decomper.md` to be authoritative.

So a specialist is launched on the generic `agents/worker.md` seat, and its
specialism comes from its scope in `AGENTS.md` and from the brief it is handed.
Adoption says so in its own output when a declared executor has no seat file, so
the adopted layout is never mistaken for offering one file per declared name.

The alternative — generating thin per-name aliases — was rejected: it would make
the tool's file set a function of the project's role vocabulary, which is the
same coupling in the other direction, and each alias would either restate the
contract or point at one that does not exist.

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
