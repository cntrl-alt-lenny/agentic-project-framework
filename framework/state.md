# State and memory

**The repository is the memory. Chat history is not.**

A fresh Brain, in a new conversation, must be able to inspect the repository and
reconstruct what is going on. Continuity of a conversation is a convenience,
never a requirement.

## The split

| | Durable state | Live state |
|---|---|---|
| Examples | architectural decisions, settled conclusions, rejected alternatives worth remembering, project invariants, why something is parked, owner preferences | current SHA, open pull requests, CI status, current branch, whether a worktree exists, queue contents |
| Where it lives | version-controlled documents | derived from git, the host, the filesystem |
| How it is obtained | read it | re-derive it, every session |

**Live state is never stored.** A stored SHA, a stored count, a stored "the
current open pull request is #12" is stale the moment the next thing happens, and
it is worse than absent because it is confidently wrong.

The single exception is a **historical anchor** — a value being recorded
*because* it was true at a particular moment, clearly labelled as historical. "As
of round 14 the dataset held 3,812 records" is a historical anchor. "The dataset
holds 3,812 records" is stale live state pretending to be durable.

## The state document

Keep one short state document. Its job is to let a cold session catch up in
about a minute, then get out of the way.

It should contain:

- what the project is currently working toward;
- decisions that are settled, and would otherwise be re-litigated;
- what is parked, and **why** — this is the highest-value content, because it is
  the thing a fresh session cannot derive;
- owner preferences and standing constraints;
- pointers to the detailed documents.

It should **not** contain:

- anything derivable from git or the host;
- a running log of every round;
- detail that already exists in another document.

**It is a pointer document.** When a section starts accumulating per-round
detail, trim it back rather than letting it grow. Every project that has used
this framework has needed that trim at least once.

## Why giant state files fail

An append-only state file becomes a second database that nobody maintains and
everybody half-trusts. Its top is read, its middle is stale, and its
contradictions are invisible because no one reads it end to end.

Symptoms, in order of appearance: it stops being read cold; it starts
contradicting the repository; a session relays a stale fact forward as
established; and eventually nobody can tell which half is current.

Archive historical round logs into a separate, clearly historical location. Do
not let history and current context share a file.

## Model notes are a log, not a ranking

Recording what actually happened when a particular model held a particular seat
is useful. Recording it as a ranking is not: it ages badly, it invites treating
model choice as a correctness primitive, and it drifts into the role contracts.

Keep such notes:

- **out of the role contracts**, always;
- phrased as observations from specific rounds, not as requirements;
- explicit that they are preferences.

## Documents are claims

Everything in this section applies to the framework's own documents too. A
document asserting that a protection exists, that a check runs, or that something
was verified is a **claim to re-check**, not a fact to relay forward.

One real instance: a coordination document asserted that branch protection was
enabled when it was not, and an external review caught it — the exact failure
that document itself defined, committed in the document defining it. The fix was
not better wording; it was querying the live setting every session so the claim
could not drift again.
