# Changelog

## v2 — general-purpose agentic project framework

v1 was `decomp-agent-framework`: a three-agent, decompilation-specific,
single-vendor coordination layer. v2 keeps the mechanisms that survived
production use across three projects, and replaces the architecture around them.

**This is a historical document.** It quotes v1's text, which the current guards
reject.

### What changed, and why

| v1 | v2 | Why |
|---|---|---|
| Brain reviewed, summarized, then asked the owner to authorise the merge | **Brain merges what it accepts** | v1 made the coordinator a recommender and the owner a merge button. The owner keeps direction, veto, reversal and a reserved list; routine technical acceptance is delegated. |
| Owner listed as merging pull requests and adding agents | Owner sets direction; is not expected to read a diff | The whole point of the framework. |
| Coordinator could self-merge "when the owner is away" | Authority does not depend on who is at the keyboard | Absence-based authority gives different outcomes for identical changes. |
| An executor role held emergency self-merge rights | **No executor ever accepts or merges its own work** | Urgency is exactly when that boundary bends, and exactly when it must not. |
| Exactly three agents, named for one problem domain | **Three role *contracts*; topology is a project decision** | Three real projects settled on three different topologies. What must not vary is authority. |
| Roles defined partly by what tooling a session had | Roles defined by **capabilities** | "Runs locally with the toolchain" is a capability requirement, not a role. |
| Vendor mechanics mixed into the role definitions | **Contract / adapter split**, with adapters that point rather than paraphrase | A vendor adapter in a real project kept describing a superseded authority model after the contracts moved on. |
| Neutrality asserted in prose | **Neutrality enforced structurally**, proved against a novel provider name | Prose drifts; a blacklist is stale on the next provider's launch day. |
| Push guard as a tool-level command-text hook | **Git `pre-push` layer**, with honest limits documented | The tool-level guard was defeated seven ways in one project and fired for one vendor only. |
| Churn-heavy state log | **Durable state only; live state derived** | A state document grew past a thousand lines and started contradicting the repository. |
| Interactive installer with six domain placeholders | **Adoption is a documented procedure for an agent**, plus a small non-interactive copy script | Telling an agent "apply this framework here" is simpler and more robust than an installer for a human. |

### Removed

- `framework/docs/decomp-workflow.md` — the byte-matching walkthrough. Entirely
  domain-specific.
- `decomper` and `scaffolder` as *the* role set. They survive as topology
  examples in [`framework/case-studies.md`](framework/case-studies.md).
- `pre_bash.py` — the tool-level push guard. Wrong layer; replaced by a sample
  git `pre-push` hook with its limits stated.
- `post_edit.py` — a lint-and-test-on-edit hook with domain-named configuration.
  Project-specific, and it was configuration surface rather than framework.
- The six domain placeholders (`GAME_NAME`, `TOOLCHAIN_NAME`, `BASEROM_PATH`,
  `REGIONS`, and the rest). Role contracts now have **no placeholders at all**,
  so they cannot drift per project.
- `install.py`'s interactive prompting, YAML config and update mode.

### Kept, generalized

- `AGENTS.md` as the project's coordination document.
- `<role>/<scope>` branch naming — now enforced structurally.
- The brief directory and the separation of stable manifest from churning state.
- Isolated checkouts per concurrently-active role.
- "Slugs are roles, not providers" — v1 said this in prose. v2 makes it a rule
  with a test.
- The session-reply inbox hook, demoted to an explicitly optional adapter
  convenience whose absence means **unknown**.
- The installer's fork-safety instinct: never overwrite, write a sibling,
  support a dry run.

### Added

- A [constitution](framework/CONSTITUTION.md) as the single normative root.
- Three provider-neutral [role contracts](framework/roles/).
- [Topology guidance](framework/topologies.md) with three worked shapes.
- [Evidence standards](framework/evidence.md) — exact-SHA discipline,
  re-derivation, what makes a guard real.
- A [failure catalogue](framework/failure-catalogue.md) of 34 patterns observed
  in production, each with its general lesson.
- [Case studies](framework/case-studies.md) of the three projects this was
  derived from.
- An invariant suite: provider neutrality, authority, adapter boundaries,
  adoption behaviour, guard honesty, repository integrity.
- `tools/neutrality.py`, `tools/authority.py` and `tools/textblocks.py` —
  shipped to adopting projects so the guards travel with the framework.

### Migration from v1

There are no known external consumers, so no compatibility shims were kept.

For a project on v1:

1. Run `tools/adopt.py` against it. Existing files are never overwritten; the
   framework version lands beside them as `.framework` siblings.
2. Merge each collision by hand, then delete the sibling.
3. Delete `.claude/hooks/pre_bash.py` and `post_edit.py`, and their `settings.json`
   entries. Replace with a git `pre-push` hook if the project has validation
   worth running early.
4. Sweep for stale authority language. The installed guard finds it: any text
   routing a routine merge back to the owner, or granting an executor
   self-merge rights.
5. Keep active branches as they are. Apply the role-based convention to new ones.
6. Move round-by-round history out of the state document into archived briefs.

### Repository name

`decomp-agent-framework` describes a domain the framework no longer has. See
the README for the current name and the reasoning.
