# Adopting this framework

Written for an **agent** applying this framework to a repository. The owner's
side of this is one sentence: *"Apply the framework at `<path or URL>` to this
project."*

## What adoption produces

| In the target repository | What it is |
|---|---|
| `AGENTS.md` | The project's coordination document: its declared topology, its authority statement, its own invariants, and pointers. **This is the only file that needs real thought.** |
| `docs/agents/roles/*.md` | The role contracts, copied verbatim. Generic by design — do not edit them per project. |
| `docs/agents/lifecycle.md`, `evidence.md`, `git-and-isolation.md`, `adapters.md`, `reports.md` | Copied verbatim. |
| `docs/state.md` | The durable state document, starting nearly empty. |
| `docs/briefs/` | `README.md` (lifecycle), `active.md`, `delivered/`, `archive/`. |
| `tests/test_role_neutrality.py` | The neutrality guard, pointed at the project's declared role set. |
| `tools/neutrality.py` | The scanner the test uses. |
| `tools/report.py` | The provider-neutral completion-report writer every Worker and Verifier contract requires — installed unconditionally, with no `--adapter` needed. See `reports.md`. |
| `.githooks/pre-push` *(optional)* | A client-side gate, if the project has validation worth running early. |
| A provider adapter's files *(optional)* | Installed **where that adapter declares**, which is a property of the tool and not of the adapter's name — see [`adapters.md`](adapters.md). `adopt.py` prints the destination and the seats it installed. |

The mechanical copy can be done by [`../tools/adopt.py`](../tools/adopt.py). The
judgement cannot.

## Procedure

### 1. Read the framework first

At minimum [`CONSTITUTION.md`](CONSTITUTION.md), [`topologies.md`](topologies.md)
and [`roles/README.md`](roles/README.md). The rest can be consulted as needed.

### 2. Establish what the project actually is

Before choosing anything, work out from the repository:

- what the project is trying to produce;
- what must never break — its real invariants;
- what its **defects actually look like**. This drives the topology more than
  anything else. If defects are caught by the test suite, a reviewer seat is
  overhead. If defects pass every local check, a reviewer seat is the only thing
  that will find them;
- what validation exists, and what evidence a change should therefore produce;
- whether the hosting provides a merge gate.

### 3. Choose the smallest topology that works

Default to `Owner → Brain → Worker`. Justify anything larger with a reason from
step 2, and write the reason down. See [`topologies.md`](topologies.md).

Do not create a role because a capability exists.

### 4. Run the copy

```bash
python tools/adopt.py <target-repo> \
    --project "<Project Name>" \
    --workers worker \
    [--verifier] \
    [--hooks] \
    [--dry-run]
```

`--workers` takes the executor role names, comma-separated. `worker` for the
default topology; `decomper,scaffolder` or similar for specialists. Brain is
always present. `--verifier` adds the reviewer seat.

Add `--adapter <name>` only if a bundled adapter earns its place. Read the plan
it prints: it names the destination and the seats installed. An adapter ships
one seat per role contract, so a specialist executor is normally launched on the
generic executor seat and scoped by `AGENTS.md` — do not expect a file named
after each declared role.

The script never overwrites an existing file: it writes a `.framework` sibling
and reports the collision instead. Re-running it is safe.

### 5. Write `AGENTS.md` properly

The template gives the structure. The project-specific parts are yours to write:

- **The topology table** — roles and their scopes. Scopes must not overlap.
- **Non-negotiable project invariants** — the things that outrank process.
  Restate them here because they are what an executor most often needs at hand.
- **Evidence per layer** — what validation a change to each part of the
  repository must produce. Be concrete: exact commands, not "run the tests".
- **Where to look** — the project's own map.

Do **not** rewrite the authority model. It is stated once, in the constitution,
and pointed at from here.

### 6. Set up isolation

One isolated checkout per concurrently-active role. See
[`git-and-isolation.md`](git-and-isolation.md).

### 7. Make the guard real

Run the test suite and confirm the neutrality test passes against the project's
declared roles. Then **prove it fails** on a mutation — add a provider-shaped
branch example to a normative document, watch it go red, and remove it. A guard
nobody has watched fail is not yet a guard.

### 8. Configure protections honestly

Where the hosting supports it, require pull requests, require the checks that
actually matter, enforce for administrators, and constrain force-push and
deletion.

**Do not require a human approval count.** That reinstates the owner as the merge
button, which is the thing this framework exists to remove.

Then write down what is actually enforced — and, explicitly, what is not. If
every agent authenticates with the same credentials, say so.

### 9. Hand over

Brain's first output to the owner is a plain-English statement of what the
project is set up to do and the first ready-to-paste prompt. Not a tour of the
files.

## Adapting an existing project that already has agent conventions

Migrate, do not bulldoze.

- **Keep the project's existing branch convention** if it already derives from
  roles or project structure. A milestone prefix is fine. Only a
  provider-derived namespace is a defect.
- **Do not rename active branches.** Preserve in-flight work; apply the
  convention to new branches.
- **Retire, do not delete.** Move superseded queues and roles to a clearly
  read-only archive so nobody mistakes history for current policy.
- **Sweep the class.** If one provider-shaped identifier turns up, check
  queues, branches, dispatch prompts, adapters and topology statements before
  concluding it was isolated.
- **Check for stale authority language**, which is the most common thing an older
  setup carries: any text routing routine merge approval back to the human.

## What not to do

- Do not copy the case studies or the failure catalogue into the target. They are
  this repository's history, not the project's.
- Do not edit the role contracts per project. If a contract genuinely does not
  fit, that is a framework finding — raise it here.
- Do not add a provider adapter unless it earns its place. The universal launch
  procedure works without one.
- Do not build project-specific process before the project has produced a real
  problem that needs it.
