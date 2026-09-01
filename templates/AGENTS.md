# AGENTS.md — coordination model for {{PROJECT}}

**This file says who does the work and how a change earns its way in.** Where
this project has its own specification document, that document says what the
project is and what may not be broken; where the two disagree, that one wins.

The normative framework this project runs on lives in
[`docs/agents/`](docs/agents/). This file is the project-specific part: the
topology, the invariants, and the evidence each kind of change must produce.

## Authority

The human project owner is the final authority over direction and scope, and
retains veto and reversal over everything below.

**The merge gate is Brain's independent review, not a per-round human
approval.** The owner sets direction and can reverse any decision afterwards;
they do not sign off on each round before it lands, and they are not expected to
read a diff. Any document describing a human per-round merge approval as the
gate is stale.

The full authority model, including the list of actions still reserved to the
owner, is in [`docs/agents/CONSTITUTION.md`](docs/agents/CONSTITUTION.md). It is
stated once there rather than restated — and drifted — here.

**The owner's interface is conversation, not the repository.** Their loop is:
ask what's next → receive one ready-to-paste prompt → paste it into whichever
tool they choose → say it finished → receive the outcome and the next prompt. If
a step would require them to open a repository file or run a git command, that is
a defect in this setup, not a task for them.

## Topology

{{TOPOLOGY_DIAGRAM}}

{{ROLE_TABLE}}

**Roles are contracts, not vendors.** Any capable tool may hold any seat, and
doing so changes nothing about the topology, the branch namespace, the queue, the
authority model or the review standard. Contracts are in
[`docs/agents/roles/`](docs/agents/roles/); anything tool-specific is an adapter
and may never restate policy — see
[`docs/agents/adapters.md`](docs/agents/adapters.md).

Adding or retiring a role is a strategic decision and goes to the owner. A
provider never creates a lane.

## Non-negotiable project invariants

<!-- Replace this block. These outrank any process below, and they are what an
     executor most often needs at hand. Be specific and cite where each one
     comes from, so it can be checked rather than trusted. Delete the examples.

- What this project must never do, and why.
- Which parts of the tree are authoritative and not ours to modify.
- Licensing constraints.
- Honesty: never describe planned functionality as shipped.
-->

## Evidence discipline

Agent reports are evidence, not ground truth. The standard is in
[`docs/agents/evidence.md`](docs/agents/evidence.md); the project-specific part
is what "run the relevant checks" actually means here.

Run what is relevant to what you touched, paste real output with exit status,
and say what you did **not** run.

| Changed | Required evidence |
|---|---|
| <!-- path or layer --> | <!-- the exact commands whose real output must appear in the report --> |

<!-- Be concrete. "Run the tests" is not an evidence requirement; a command is.
     If a suite structurally cannot fail for some class of change, say so here —
     citing it for that class is then a blocking finding, not a style note. -->

CI is the backstop, not the primary evidence: it runs after the claim has
already been made.

## Working discipline

- **One coherent task at a time.** Do not fan a brief out into unrelated work.
  If the real fix is bigger than the brief's scope, stop and report that rather
  than expanding unilaterally.
- **One branch per task**, named `<role>/<kebab-scope>`.
- **Separate checkouts, never a shared one**, for concurrently-active roles —
  [`docs/agents/git-and-isolation.md`](docs/agents/git-and-isolation.md).
  Re-check branch and status at the start of *every* discrete task, not only at
  session start.
- **Protect unrelated work.** Before anything destructive, check whether another
  session has work in flight. Stash or branch; do not clobber.
- **Never push to the default branch.**
- **Focused commits**, not one giant commit.
- **Repository and source state outrank agent narrative.** A prior report —
  including this repository's own documents — describing something as "verified"
  is a claim to re-check at the current state, not a fact to relay forward.
- **Exact-SHA verification.** When a claim depends on CI or a specific commit,
  check it at that literal SHA, not "the branch generally".
- **Fix the defect class, not the first example.**
- **Prefer a mechanism over a list.** "I tried these cases and they were fine"
  decays the moment the code changes; an executable check does not.
- **State handoff.** Durable facts go in [`docs/state.md`](docs/state.md), kept
  short — never only in chat history.

## What is actually enforced

<!-- Replace this block with the truth, and keep it true. Never claim stronger
     enforcement than exists.

| Layer | Strength | Status |
|---|---|---|
| Server-side branch protection | the guarantee | <!-- verified how, and when --> |
| Local pre-push hook | convenience, early feedback | <!-- opt-in per clone --> |

     Note honestly whether every agent authenticates with the same credentials.
     If so, the host cannot tell one role from another: it enforces the *path*
     (a change arrived through a reviewed, green pull request), never the role.
     That executors do not merge is a contract property. Do not describe it as
     server-enforced. -->

## The round

The lifecycle, the brief states and the handoff protocol are in
[`docs/agents/lifecycle.md`](docs/agents/lifecycle.md). In short: Brain
rehydrates, writes one brief, hands the owner a ready-to-paste prompt, the work
comes back, Brain independently inspects the exact SHA, adjudicates, merges what
it accepts, and reports in plain English.

**The owner's involvement in a routine round is pasting one prompt and reading
one summary.**

## Where to look

- Authority model and core principles:
  [`docs/agents/CONSTITUTION.md`](docs/agents/CONSTITUTION.md)
- What each role must actually do:
  [`docs/agents/roles/`](docs/agents/roles/)
- The round, brief lifecycle, handoff:
  [`docs/agents/lifecycle.md`](docs/agents/lifecycle.md)
- Evidence standards: [`docs/agents/evidence.md`](docs/agents/evidence.md)
- Branches, isolation, push gates:
  [`docs/agents/git-and-isolation.md`](docs/agents/git-and-isolation.md)
- How a role's completion report reaches Brain regardless of which tool ran
  it: [`docs/agents/reports.md`](docs/agents/reports.md)
- Launching a role on any tool:
  [`docs/agents/adapters.md`](docs/agents/adapters.md)
- Durable project context: [`docs/state.md`](docs/state.md) — it stores no live
  state; derive current branch, SHA, open work and CI status from git
- Active brief: [`docs/briefs/active.md`](docs/briefs/active.md); lifecycle in
  [`docs/briefs/README.md`](docs/briefs/README.md)
