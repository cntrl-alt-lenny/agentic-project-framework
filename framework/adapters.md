# Adapter specification

An **adapter** describes how to start a role on one particular tool. That is
all it does.

Adapters are optional. A project with no adapter at all is fully functional: the
[universal launch procedure](#the-universal-launch-procedure) works on every
tool, including one that does not exist yet.

## What an adapter may contain

- How to start a session on that tool, and where.
- That tool's configuration format — frontmatter, config files, manifests.
- Tool-specific conveniences: named agents, slash commands, hooks, transcript or
  inbox mechanisms, session APIs.
- Model and reasoning-effort settings, clearly marked as that tool's mechanics.
- A pointer to the canonical role contract.

## What an adapter may never contain

An adapter may not restate or redefine:

- **authority** — who may accept, reject, or merge;
- **role identity** — what the roles are and what they are called;
- **queue identity** — where work is tracked;
- **branch identity** — the branch namespace;
- **gates** — what must pass before work is accepted;
- **merge rights**.

Those live in the [constitution](CONSTITUTION.md) and the
[role contracts](roles/). **If an adapter and a contract disagree, the contract
wins.**

This is not a style rule. Every one of those, restated in an adapter, becomes a
second source of truth that drifts — and drifted silently in a real project until
a test caught a provider adapter still describing a superseded authority model
long after the contracts had moved on.

## Adapters point, they do not paraphrase

The correct shape of an adapter file is short:

```markdown
---
<whatever frontmatter this tool requires>
---

# <Role> — <tool> adapter

**Your role contract is [`<path to contract>`](<path>). Read it now, in full,
and follow it. It is authoritative.** This file exists only to start you on this
particular tool; it deliberately does not restate the contract, so the two
cannot drift apart.

Then read <the project's coordination document>.

## <Tool> specifics for this seat

- where to work
- how this seat is normally launched
- which of this tool's features apply, and which do not
```

Deliberately not restating the contract is the mechanism. A summary is a copy,
and copies drift.

## Conveniences must fail loudly

A convenience is anything the adapter provides that the framework does not
require: a hook mirroring a session's final reply somewhere Brain can read it, a
transcript API, an automatic worktree manager, a session registry.

Every convenience needs:

1. **A stated fallback** for when it is unavailable.
2. **An explicit statement that its absence means UNKNOWN.**

A round run on a different tool produces nothing from that convenience, and that
is *normal, not a signal*. Never interpret a missing artifact as "the task did
not happen", "the agent failed", or "the review did not run". Check the
timestamp before trusting an artifact that is there, too.

## Prompts: neutral core, optional tail

The prompt Brain hands the owner is built from **role + task + project state**.
It must paste cleanly into any capable tool.

Tool-specific mechanics — restarting a session after a config change, a
particular flag, a slash command — go **after** the neutral core, in a clearly
marked optional block naming the tool:

```
OPTIONAL — <tool> only. Ignore if you are using something else.
<the mechanic>
```

An optional block may add launch mechanics and nothing else. It may not touch
the role, the queue, the branch, the gate, the authority, or the merge. A test
can enforce that; see
[`../templates/tests/test_role_neutrality.py`](../templates/tests/test_role_neutrality.py).

If the tool is unknown, the neutral core is still sufficient. That is the test of
whether the prompt was written correctly.

## The universal launch procedure

This works on every tool, including one this project has never seen. It is the
fallback whenever no adapter exists — which is the expected case for most tools.

1. **Put the session in the right checkout.** Brain in the primary checkout;
   every other concurrently-active role in its own — see
   [`git-and-isolation.md`](git-and-isolation.md).
2. **Give it the contract, in full**: the relevant file from
   [`roles/`](roles/). Paste it if the tool has no file access; the contracts are
   written to survive that.
3. **Give it the project's coordination and specification documents.**
4. **Give it its inputs.**
   - Worker: the brief and its branch.
   - Verifier: the brief, the literal base SHA, the literal head SHA — and
     **not** the executor's report.
   - Brain: nothing extra; it rehydrates from the repository.
5. **Take its report back as text.** Every role's output is prose in a defined
   shape. If nothing automates the handoff, the owner pastes it.

Nothing above depends on a provider. Everything an adapter adds is convenience on
top.

## Adding support for a new tool

1. Create a directory for that tool's configuration.
2. Add one thin adapter file per role, in the shape above.
3. Add a row to the project's adapter table.
4. Change **nothing** in the role contracts, the branch convention, the queue, or
   the authority model. If supporting the tool seems to require that, the change
   belongs in the contract for a reason that has nothing to do with the tool —
   or it does not belong at all.

An example adapter for one tool ships in
[`../adapters/claude-code/`](../adapters/claude-code/). It is an illustration of
the shape, not a dependency.
