# agentic-project-framework

An operating model for running a repository-based project where a human product
owner directs the work and autonomous agents execute it — without the owner
having to adjudicate whether a change is technically correct.

It works for software engineering, research, reverse engineering, data and
schema work, documentation projects and audits. It is not tied to any provider,
model or tool, and not to any fixed number of agents.

## The idea in one picture

```
Owner    decides what and why. Veto and reversal. Does not read diffs.
  |
Brain    holds context, writes briefs, adjudicates, MERGES what it accepts.
  |
Worker   executes one bounded brief. Never accepts or merges its own work.
  |
Verifier (optional) independently reviews an exact SHA. Never merges.
```

The owner's loop is: **ask what's next → paste one prompt into whichever tool
they like → say it finished → read a plain-English outcome.**

The thing that makes it work is that **routine technical acceptance belongs to
Brain**, not to the owner. A framework where the coordinator asks "looks good,
shall I merge?" has just moved the problem back to the human.

## What this repository contains

| | |
|---|---|
| [`framework/CONSTITUTION.md`](framework/CONSTITUTION.md) | The normative core: authority, neutrality, evidence, memory. Everything else expands one section of it. |
| [`framework/roles/`](framework/roles/) | The three role contracts — [Brain](framework/roles/brain.md), [Worker](framework/roles/worker.md), [Verifier](framework/roles/verifier.md). Provider-neutral, written to be read cold. |
| [`framework/topologies.md`](framework/topologies.md) | Choosing how many executors, and what they are called. |
| [`framework/lifecycle.md`](framework/lifecycle.md) | The round, the brief states, the handoff protocol. |
| [`framework/briefs.md`](framework/briefs.md) | Brief template and design rules. |
| [`framework/evidence.md`](framework/evidence.md) | Exact-SHA discipline, re-derivation, what makes a guard real. |
| [`framework/git-and-isolation.md`](framework/git-and-isolation.md) | Branches, isolated checkouts, push gates, and what is actually enforced. |
| [`framework/state.md`](framework/state.md) | Durable versus live state. |
| [`framework/adapters.md`](framework/adapters.md) | How a tool plugs in without touching policy. |
| [`framework/adoption.md`](framework/adoption.md) | How to apply this to a repository. |
| [`framework/failure-catalogue.md`](framework/failure-catalogue.md) | 34 real failure patterns, with the general lesson behind each. |
| [`framework/case-studies.md`](framework/case-studies.md) | Three projects, three topologies, one authority model. |
| [`adapters/claude-code/`](adapters/claude-code/) | An example provider adapter. |
| [`templates/`](templates/) | What an adopting project receives. |
| [`tools/`](tools/) | The adoption script and the invariant scanners. |
| [`tests/`](tests/) | This repository's guards on its own invariants. |

## Adopting it

**The intended path is to tell an agent:** *"Apply the framework at `<path or
URL>` to this repository."* Then point it at
[`framework/adoption.md`](framework/adoption.md), which is written for exactly
that.

The mechanical half — copying the contracts, the brief scaffolding, the guard
— is one command:

```bash
python tools/adopt.py <target-repo> --project "My Project" --workers worker
```

Add `--verifier` for the reviewer seat, `--workers a,b` for parallel
specialists, `--hooks` for a sample pre-push gate, `--adapter claude-code` for
the example adapter, `--dry-run` to see the plan. Existing files are never
overwritten.

The judgement half — choosing the topology, writing the project's invariants and
its evidence table — is not automatable, and `adoption.md` says what to think
about.

## Three ideas worth reading even if you adopt nothing

**Role is not model, provider or tool.** A role is a contract. A provider is
whatever happens to be executing it this round. Branch namespaces, queues,
topology and merge semantics all derive from roles, so switching provider
requires zero change to any of them. This is enforced by **positive structural
rules**, not a list of banned vendor names — a blacklist is stale the moment a
new provider ships. The test suite proves the guard rejects a provider name that
appears nowhere else in this repository.

**Evidence outranks narrative.** An agent report is evidence; repository, source
and CI state are ground truth. Review against a literal SHA. If the head moves,
the review does not transfer. Re-derive at least one load-bearing claim yourself.
Passing tests prove the code agrees with itself and nothing else.

**Guards must actually guard.** A hook existing is not proof it blocks anything.
A check's name is not proof of what it checks. Prove a guard red before you trust
it green, and never let a guard that checked nothing report success.

## What this repository guards about itself

Run `python -m unittest discover -s tests -t .`

- **Provider neutrality**, structurally, over every normative document — with a
  novel-provider mutation test proving the rules are not vendor-name matching.
- **Authority**, proved red-before-green against the **actual v1 text**, kept
  verbatim as a fixture. The phrases it must reject:

<!-- guard:counterexample -->
  > "offer to merge" · "execute on OK" · "merges on the human's OK" ·
  > "production-fire self-merge authority" · the owner named as the merge actor
<!-- /guard:counterexample -->

- **Adapter boundaries** — an adapter that restates policy fails.
- **Adoption behaviour** — the script is exercised end to end against a real
  temporary repository, and the guard it installs is run there.
- **The scope split itself** — a policy document cannot be exempted from the
  scans by adding it to a list.
- **That every test file is actually collected** by the command CI runs.

Honest limit: this repository's product is normative text, so text properties are
the invariant rather than a proxy for one. Nothing here can prove a running agent
obeys what the text says.

## History

**v1** was `decomp-agent-framework`: three fixed agents, decompilation-specific,
built around one vendor's tooling, and it routed every merge back through the
human. It was generalized after production use across three projects — see
[`CHANGELOG.md`](CHANGELOG.md) for what changed and why, and
[`framework/failure-catalogue.md`](framework/failure-catalogue.md) for what went
wrong along the way.

## License

MIT. See [LICENSE](LICENSE).
