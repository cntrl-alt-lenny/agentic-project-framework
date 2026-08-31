# HISTORICAL FIXTURE — do not copy, do not fix

Verbatim text from **v1** of this framework, preserved so the authority guard
can be proved against the real broken state rather than an invented one. Every
line below is a genuine v1 string.

This file is a test fixture. It is deliberately excluded from every normative
scan, and `tests/test_authority_invariants.py` asserts that exclusion, so it
cannot quietly become policy again.

Each line is prefixed with its v1 origin.

---

README: Reviews PRs, runs the build, summarises in plain English, merges on the human's OK.

AGENTS table (owner row): Human project owner. Sets priorities, picks direction, merges PRs, adds/retires agents, final authority.

AGENTS table (brain row): Default on every PR: review locally → summarize in plain English to the owner → offer to merge → execute on OK.

AGENTS table (brain row): Self-merges autonomously when the owner is AFK, flagging in the PR body.

AGENTS rules item 2: The brain reviews locally, summarizes in plain English, and merges on OK.

AGENTS PR workflow item 5: Brain offers to merge. On the owner's OK (explicit "merge it" or a thumbs-up), merge with the squash flag.

AGENTS PR workflow item 5: When the owner is AFK, the brain self-merges and notes so in the PR body.

AGENTS adding agents item 3: Opens a PR with the change. The owner merges.

brain.md loop step 3c: Offer to merge. On OK, merge the PR.

brain.md production-fire: When the project's baseline check goes red, self-merge the fix without waiting.

scaffolder.md: Production-fire self-merge authority. Same rule brain has: when the baseline goes red and blocks every PR, self-merge the fix without waiting.

scaffolder.md: Normal tool/docs PRs go through brain's review, never self-merged.

workflow doc: You (the owner) get a summary from brain and the final say on controversial ones.

workflow doc cast table: You. Sets priorities, picks direction, merges PRs.
