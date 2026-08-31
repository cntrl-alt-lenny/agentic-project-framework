# Case studies

Three projects this framework was derived from. They are **evidence, not
templates**: nothing in the framework depends on them, and none of them is the
"right" shape.

**This is a historical document.** It names the tools that actually ran, because
that is what happened. It is out of scope for the provider-neutrality rules that
govern the normative documents.

---

## A. Parallel specialists — a decompilation project

**Topology**

```
Owner
└── Brain
    ├── Decomper      (matches functions against the original binary)
    └── Scaffolder    (tooling, headers, research, review)
```

**Why this shape.** The two workstreams are genuinely different jobs with
different inputs. Matching is a focused, highly iterative loop against a build.
Tooling and research are parallel work that mostly does not need the build at
all. Splitting them kept both unblocked.

**What it demonstrated.** Parallelism can materially increase throughput **when
responsibilities are genuinely distinct**. It was not adopted because two tools
were available; it was adopted because two kinds of work existed.

**What it cost.** The largest state document of the three, and the most drift.
This is where provider names leaked into queues, branches and dispatch — and
where the structural neutrality guard was first built, together with a deliberate
audit that broke every repository-invariant test in turn to confirm it actually
fired. Six of them did not, and were fixed.

**Lesson carried into the framework.** Specialist lanes are legitimate, and they
raise the cost of coordination — so they need a bottleneck to justify them, and
they need a guard that keeps the lane definition role-based.

---

## B. Sequential — a historical data reconstruction project

**Topology**

```
Owner
└── Brain
    └── Worker
```

**Why this shape.** The work is sequential and research-heavy. The hard part is
adjudicating evidence, not producing volume. A second executor would have spent
most of its time waiting for a judgement.

**What it demonstrated.** A small topology can be extremely effective. Specialist
behaviour was handled as a **mode** the single executor adopts per brief —
research, source verification, adversarial audit, data and schema work — rather
than as separate standing roles.

**Notable.** This project has no pull-request gate, so Brain's independent review
*is* the acceptance action; the merge is what accepting looks like. It also has
the clearest statement of the owner's interface: their loop is conversation, and
if a step would require them to open a repository file, that is a framework
defect.

**Lesson carried into the framework.** Modes, not roles. And: the authority model
must work whether or not the hosting provides a merge gate.

---

## C. High assurance — a client rebuild over an authoritative engine

**Topology**

```
Owner
└── Brain
    ├── Builder
    └── Verifier
```

**Why this shape.** The project layers new code over an upstream engine it must
not disturb. Its real defects were **semantic mismatches with upstream that
compiled and tested clean** — every one of them passed every local check. That is
precisely the defect class an independent reviewer catches and a test suite does
not.

**What it demonstrated.** Independent exact-SHA review paid for itself
immediately: on the first round, a fresh-context reviewer surfaced defects the
author had missed — with all three seats on the same model family, which showed
that **context** diversity alone does the work. Model-family diversity is a
preference layered on top, not the mechanism.

**Notable.** This project produced the `UNPROVEN CLAIM` finding class, which
turned out to be the highest-value output of the reviewer seat: the change is
often fine, but a specific stated claim is not supported by the evidence offered.

**Lesson carried into the framework.** Where defects pass local checks,
independent review is not ceremony — it is the only thing that catches them.

---

## What the three have in common

Everything in the [constitution](CONSTITUTION.md) that is not topology:

- the owner as product owner, not reviewer;
- routine technical acceptance delegated to Brain;
- executors that never self-accept;
- exact-SHA discipline;
- repository as memory, live state derived;
- roles as contracts, providers as adapters;
- fresh context per assignment.

**Three different topologies, one authority model.** That is the whole design
claim, and it is why the framework standardizes the second and leaves the first
to the project.
