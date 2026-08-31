# Failure catalogue

Failure patterns observed in real use of this framework across three projects.
Each entry states the general design lesson, not just the anecdote.

**This is a historical document.** It names tools and quotes broken text
deliberately, so that the guards can be shown rejecting real examples rather than
invented ones. It is out of scope for the provider-neutrality rules that govern
the normative documents — see [`CONSTITUTION.md`](CONSTITUTION.md).

---

## Memory and state

### 1. Stale conversational memory

**What happened.** A long-running coordinating session carried assumptions from
early in a project and kept applying them after the repository had moved on.

**Lesson.** Chat history is not project memory. Durable facts belong in
version-controlled documents; a fresh session must be able to reconstruct the
project from the repository alone. Continuity is a convenience, never a
requirement.

### 2. Durable state pretending to be live state

**What happened.** A state document recorded current counts, the current open
pull request, and whether a hook was configured. All three went stale, and a
later session relayed them forward as established fact.

**Lesson.** Store durable decisions; **derive** live state. A stored value that
can change is worse than an absent one, because it is confidently wrong. If a
value must be recorded, label it explicitly as a historical anchor.

### 3. Giant state files becoming a second database

**What happened.** A state document grew past a thousand lines. Its top was read,
its middle was stale, and its internal contradictions were invisible because
nobody read it end to end.

**Lesson.** The state document is a **pointer document**. Trim per-round detail
back into archived briefs and notes. Every project using this framework has
needed that trim at least once.

### 4. A document asserting a protection that did not exist

**What happened.** A coordination document stated that branch protection was
enabled. It was not. An external review caught it — the exact "unproven claim"
failure that same document defined, committed in the document defining it.

**Lesson.** Documentation is a claim, not a fact, **including the framework's
own**. The fix was not better wording; it was querying the live setting every
session so the claim could not drift again.

---

## Provider leakage

### 5. Provider names leaking into role topology

**What happened.** Role contracts were made model-agnostic, but the machinery
around them was not. Queues were provider-prefixed, dispatch prompts were
addressed to a provider-plus-role compound, and new branches carried a provider
prefix.

<!-- guard:counterexample -->
Concretely: `Claude Decomper` and `Codex Decomper` treated as two lanes;
`codex-scaffolder` as a queue name; `gemini/<task>` as a branch namespace; a
topology described as "2 Claude + 2 Codex workers".
<!-- /guard:counterexample -->

**Lesson.** Fixing the contracts is not enough. Provider identity leaks through
**queues, branches, dispatch and topology** as well. When one instance appears,
sweep the whole class.

### 6. Neutrality defined as a provider blacklist

**What happened.** The first attempt at a guard was a list of known provider
names.

**Lesson.** A blacklist is stale the moment a new provider ships, and it silently
approves the next one. Express neutrality as **positive structural rules** over
the project's declared role set, failing closed on anything unrecognised. Prove
it with a provider name that appears nowhere in the repository. A known-name
check may exist as a secondary layer; it must never be the definition.

### 7. A provider treated as a reason for another lane

**What happened.** Having a second tool available was treated as justification
for a second standing role.

**Lesson.** A provider never creates a lane. Occupying a role with a second tool
runs that role twice. Lanes come from genuinely independent workstreams and
measured bottlenecks.

### 8. Stale provider adapters restating policy

**What happened.** A provider adapter still described a superseded authority
model long after the contracts had moved on. Anyone reading the adapter got the
old rules.

**Lesson.** Adapters **point at** contracts; they never paraphrase them. A
summary is a copy, and copies drift. Test that adapters contain no authority,
queue, branch or gate language.

---

## Authority

### 9. Brain asking the owner for routine merge approval

**What happened.** The framework's first version routed every merge back through
the human: *review locally, summarize, offer to merge, execute on OK.*

**Lesson.** That makes the coordinator a recommender rather than a lead, and puts
the owner back in the seat the framework exists to get them out of. Routine
technical acceptance belongs to Brain. The owner keeps direction, veto and
reversal — and the reserved list of genuinely strategic or destructive actions.

### 10. Merge authority framed around the human's availability

**What happened.** An earlier rule let the coordinator self-merge "when the owner
is away", flagging it in the pull-request body.

**Lesson.** Authority is not a function of who happens to be at the keyboard. If
the decision is routine, it is Brain's whether or not the owner is present. If it
is reserved, it stays reserved even when waiting is inconvenient. Absence-based
authority produces different outcomes for identical changes.

### 11. An executor granted emergency self-merge rights

**What happened.** An executor role held "production-fire self-merge authority"
for cases where a baseline check was red and blocking everything.

**Lesson.** The one boundary that must never bend is that an executor does not
accept its own work. Urgency is exactly when it bends and exactly when it should
not. Escalate to Brain; if Brain is unavailable, escalate to the owner.

### 12. An executor effectively self-accepting

**What happened.** An executor's report was detailed and confident enough that
the coordinator accepted it without independent inspection. The executor had, in
practice, accepted its own work.

**Lesson.** A report is evidence, not a verdict. Independent inspection is
mandatory, not optional when time is short. Re-derive at least one load-bearing
claim.

---

## Verification

### 13. Verifying a branch rather than an exact SHA

**What happened.** A review was carried out against "the branch", which moved.

**Lesson.** Review against a literal base and head. Confirm ancestry. If the
SHAs do not match the branch or the pull request, stop.

### 14. Verification silently invalidated by a new head

**What happened.** A branch was updated after review — including by the entirely
correct mechanism of bringing it up to date with the base — producing a new head.
The earlier review was still treated as covering it.

**Lesson.** Fresh head, fresh review of what changed. This is correct behaviour
of the protection, not friction to route around.

### 15. Losing track of what actually landed

**What happened.** Work moved between branches by rebase and cherry-pick, and
what merged was assumed to be what was reviewed.

**Lesson.** Establish that what landed is what was reviewed, by patch identity or
by re-reading the resulting diff. Do not assume the operation was faithful.

### 16. Review anchored by the author's narrative

**What happened.** A reviewer given the executor's report first restated its
reasoning rather than forming an independent view.

**Lesson.** Blind first pass. Form a verdict from the diff and the sources, then
read the report and note conflicts. The order is the entire anti-anchoring
mechanism.

---

## Guards that did not guard

### 17. Hooks installed but never executed in tests

**What happened.** Tests asserted that hook files existed and were wired up. None
of them ran a hook and checked what it did.

**Lesson.** Test behaviour, not installation. A hook existing is not proof it
blocks anything.

### 18. A guard at the wrong layer, defeated seven ways

**What happened.** A push guard was implemented as a tool-level hook that matched
the shape of the shell command. It was defeated by invoking git from another
directory, by wrapping the push in a subshell or a command substitution, by
several refspec spellings, and by a differently-named executable — seven ways in
total. It also blocked one harmless command whose *commit message* mentioned
pushing.

**Lesson.** Put the guard where the intent is unambiguous. At git's `pre-push`
layer there is no command text to interpret: git has already resolved the refspec
and hands the hook exactly what will be written. It also fires for every client
rather than one tool. **Fix the class — change the mechanism — rather than
patching the spellings you found.**

### 19. Proxy guards that test the easier property

**What happened.** A check verified that a configuration file listed a check
name, and was treated as proof that the property was actually enforced.

**Lesson.** A guard that tests something easier than the real invariant passes
while the invariant is broken. Where a proxy is genuinely all that is available,
say so where the guard is defined.

### 20. Guards that pass silently when nothing was checked

**What happened.** Several tests skipped when their input artifact was missing.
The artifacts were committed repository inputs, so absence meant something was
wrong — but the tests reported success.

**Lesson.** Fail closed. Assert the scan set was non-empty. A guard that finds
nothing must not claim success when "nothing was checked" is the unsafe case.
A deliberate audit of every such guard — deliberately breaking each one to
confirm it fires — found six of them.

### 21. A list of tried cases presented as coverage

**What happened.** A pull-request body said a guard had been "exercised against
nine allow/block cases". That reads as *the guard is safe*. Seven bypasses
survived it.

**Lesson.** A list of cases is not coverage. If a claim matters, back it with a
mechanism that can fail.

### 22. Local working state producing a false green

**What happened.** A check passed locally against uncommitted state and failed in
CI against the committed tree.

**Lesson.** Verify against what is actually committed wherever local state could
manufacture a green. Related: a build check that regenerates its output before
comparing will silently overwrite an uncommitted hand-edit rather than reporting
it.

### 23. Tests present but not collected

**What happened.** Test files existed and were assumed to be running. Discovery
did not pick all of them up.

**Lesson.** Assert that every test file is actually collected by the command CI
runs. A test that does not run is worse than absent.

### 24. Assuming a check name means the check is required

**What happened.** A check name appearing in a workflow was treated as evidence
that it gated merging. It did not.

**Lesson.** Query live settings. Use the endpoint that reports the thing you are
claiming — a related endpoint returning an empty result is not the same as the
protection being absent.

### 25. Verifying a hook with a no-op push

**What happened.** A `pre-push` hook was tested by pushing an already-current
branch. Git does not invoke `pre-push` when there are no ref updates, so the hook
never ran and the test reported a pass.

**Lesson.** Understand the conditions under which a guard is invoked before
concluding anything from watching it not fire.

---

## Process

### 26. Dispatching a brief before it exists where the executor will look

**What happened.** A brief was handed out before it had landed on the branch the
executor would read it from.

**Lesson.** Sequence integration before dispatch. The executor sees the
repository, not the coordinator's working copy.

### 27. Building on an unadjudicated round

**What happened.** A follow-up task was queued that depended on a finding a
review had not yet confirmed.

**Lesson.** Never queue a brief whose correctness depends on an unadjudicated
round. Rescope, or wait. This is the constraint that concurrency introduces, and
it is why the brief lifecycle has a `delivered` state distinct from `accepted`.

### 28. `archive` meaning two incompatible things

**What happened.** A delivered-but-unreviewed brief was parked in the archive to
free the active slot. A cold session listing the archive would have counted an
unreviewed round as finished.

**Lesson.** State names must mean one thing. The lifecycle has to model the
pipeline's real concurrency rather than pretending it is linear.

### 29. Over-fragmented briefs

**What happened.** Tasks were split so finely that dispatch, review and
adjudication overhead exceeded the work.

**Lesson.** Combine tightly related tasks that one review can sensibly accept or
reject together. Bounded does not mean tiny.

### 30. Briefs that specified the solution

**What happened.** Briefs became detailed enough that the executor was
transcribing rather than designing.

**Lesson.** Describe the problem, not the solution. If a constraint genuinely
must be preserved, state it as an invariant with its source. Otherwise the
coordinator has become the implementer and there is no independent work left to
review.

### 31. Premature parallelism

**What happened.** Roles were added because capability was available rather than
because execution was measurably the bottleneck.

**Lesson.** Start with the simplest topology. Add a lane on throughput evidence.

### 32. Provider-specific conveniences treated as ground truth

**What happened.** A mechanism mirroring session replies to a shared location was
absent for a round run on a different tool. Its absence was read as the round not
having happened.

**Lesson.** Missing evidence means UNKNOWN. Fall back to a pasted report, then to
repository state, then — where repository state genuinely cannot answer, which is
always the case for a review — **ask the owner.**

### 33. Two agents in one checkout

**What happened.** An executor round ran in the coordinating session's checkout,
left it on the work branch, and a later session committed unrelated work on top
without noticing.

**Lesson.** Concurrently-active agents never share a working directory. Re-check
branch and status at the start of every discrete task, not only at session start
— this happened mid-session.

### 34. Spending more time on the framework than the product

**What happened.** Framework improvement became the work.

**Lesson.** The purpose is to build the project. Change the framework when real
work exposes real friction, then run several real rounds before changing it
again. This catalogue is subject to its own rule.
