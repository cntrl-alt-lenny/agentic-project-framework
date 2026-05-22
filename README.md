# decomp-agent-framework

A three-agent Claude Code framework for matching decompilation
projects (Nintendo DS, Wii, GameCube, anything where a byte-identical
ROM rebuild is the goal).

## What it is

A small, opinionated coordination layer that splits decomp work
across three specialised LLM sessions:

- **brain** — local coordinator with the toolchain installed.
  Reviews PRs, runs the build, summarises in plain English, merges
  on the human's OK.
- **decomper** — local matcher. Iterates C source against the
  baserom one function at a time.
- **scaffolder** — toolchain-free session. Writes `tools/`, library
  headers, research docs, CI; cannot run the build, so delegates
  verification to brain via PR review.

The framework ships:

- Three Claude Code subagent definitions under `.claude/agents/`.
- Three Claude Code hooks under `.claude/hooks/` —
  - `save_agent_reply.py` (Stop) — captures each session's final
    assistant turn to a shared inbox inside `.git/agent-inbox/` so
    the brain can read what the other agents said without manual
    copy-paste.
  - `post_edit.py` (PostToolUse) — opt-in `ruff` + `unittest`
    after each edit to `tools/` / `tests/`.
  - `pre_bash.py` (PreToolUse) — opt-in project pre-push check;
    blocks `git push` if the check errors.
- `AGENTS.md` — the role manifest: active-agents table, scope
  columns, branch naming, worktree convention (Mac sibling +
  Windows automatic-sandbox, both documented).
- `docs/decomp-workflow.md` — plain-English workflow walkthrough
  for new vibe coders.
- `docs/state.md` skeleton — churn-heavy brain log.
- `docs/briefs/README.md` skeleton — task brief index.

## Use this when…

- You're matching a console game byte-for-byte (DS, Wii, GameCube,
  GBA, PS1, etc.) and the loop is "write C → build → diff →
  iterate".
- You want more than one LLM session working at once, without them
  clobbering each other's branches or scope.
- You're working from a human handle and want PR review to go
  through plain-English summaries rather than reading diffs raw.

## Don't use this if…

- You're a single-agent workflow — the three-role split adds
  coordination overhead that only pays off once you have two
  parallel sessions.
- Matching isn't the goal. (If you just want "decompiled C" rather
  than a byte-identical rebuild, the scaffolder/brain split is
  overkill.)
- Your project doesn't have a toolchain that brain can run
  locally to verify PRs — the model assumes one local session can
  prove the build.

## Installation

Two flows depending on whether you're starting fresh or layering on
a fork.

### Fresh decomp project

```bash
git clone https://github.com/cntrl-alt-lenny/decomp-agent-framework \
  ~/Dev/decomp-agent-framework
cd ~/Dev/<new-project>
python ~/Dev/decomp-agent-framework/install.py .
```

You'll be prompted for the placeholder values (game name, your
handle, toolchain, baserom path, regions, project dir basename).

### Forked upstream (most common)

You've cloned someone else's upstream decomp project and want to
layer the framework on top of it without disturbing the upstream's
files.

```bash
git clone https://github.com/cntrl-alt-lenny/decomp-agent-framework \
  ~/Dev/decomp-agent-framework
cd ~/Dev/<fork-clone>

# Default: detects .claude/ gitignore and offers local-only install
# (files land on disk but won't be committed).
python ~/Dev/decomp-agent-framework/install.py .

# Or: override the upstream's gitignore so .claude/ ships with the
# fork (recommended if the fork is yours and won't get upstream PRs
# read against it).
python ~/Dev/decomp-agent-framework/install.py . --force-track
```

The installer:

- Detects and merges with an existing `.claude/` directory.
- Detects `.claude/` in `.gitignore` and offers local-only or
  `--force-track` paths.
- Writes `AGENTS.md.framework` as a sibling instead of clobbering
  an existing `AGENTS.md`. Same for `docs/state.md`,
  `docs/decomp-workflow.md`, `docs/briefs/README.md`.
- Never touches `CLAUDE.md`, the upstream's build system, `src/`,
  `config/`, or ROM files.

### Non-interactive install

```yaml
# example-config.yaml
GAME_NAME: "Xenoblade Chronicles"
HUMAN_HANDLE: "cntrl_alt_lenny"
TOOLCHAIN_NAME: "GC/Wii CodeWarrior 2.7"
BASEROM_PATH: "orig/main.dol"
REGIONS: "USA"
PROJECT_DIR: "xenoblade"
```

```bash
python install.py <target-dir> --yaml example-config.yaml
```

### Dry-run

```bash
python install.py <target-dir> --dry-run
```

Shows the plan without writing anything. Useful before committing
to a `--force-track` decision.

## Worktree setup

Once installed, the brain / decomper / scaffolder roles need
separate git worktrees so they don't fight over branch state. On
Mac / Linux:

```bash
cd ~/Dev/<project>/brain
git worktree add ../decomper   main
git worktree add ../scaffolder main
```

On Windows, Claude Code creates per-session sandbox worktrees
automatically under `.claude/worktrees/` — no manual setup needed.

See `AGENTS.md` § *Worktree convention* in the installed project for
the full picture.

## Customisation

After install, fill in the project-specific bits:

- **`CLAUDE.md`** — you write this. Toolchain version, baserom
  hashes, build commands, region matrix, project conventions. The
  framework leaves it alone because every project's `CLAUDE.md` is
  meaningfully different.
- **Pre-push check** — set `DECOMP_HOOK_PREPUSH_CMD` in your
  `.claude/settings.json` env (or shell) to a project-specific
  pre-push validator. The framework hook is a no-op until you
  configure it.
- **Lint / test paths** — `post_edit.py` defaults to `tools/` and
  `tests/`. Override with `DECOMP_HOOK_LINT_DIRS` /
  `DECOMP_HOOK_TEST_DIR` env vars if your project uses different
  paths.

### Placeholder list

The installer substitutes these tokens in `AGENTS.md`,
`.claude/agents/*.md`, `docs/state.md`, `docs/decomp-workflow.md`,
and `docs/briefs/README.md`:

| Placeholder         | Meaning                                          |
|---------------------|--------------------------------------------------|
| `{{GAME_NAME}}`     | Human-readable game name.                        |
| `{{HUMAN_HANDLE}}`  | Your handle / nickname.                          |
| `{{TOOLCHAIN_NAME}}`| Compiler + version (e.g. `mwccarm 2.0/sp1p5`).   |
| `{{BASEROM_PATH}}`  | Where the baserom lives in-tree.                 |
| `{{REGIONS}}`       | Region matrix (e.g. `EUR / USA / JPN`).          |
| `{{PROJECT_DIR}}`   | Parent dir basename for worktree examples.       |

Anything you don't fill in stays as `{{NAME}}` so you can spot what's
outstanding with `grep -r '{{' .claude/ AGENTS.md docs/`.

## Updating

When the framework ships new hook logic, pull the framework repo
and re-run install with `--update` to re-sync only the script-y
files. Your `AGENTS.md` / `docs/state.md` etc. won't be touched.

```bash
cd ~/Dev/decomp-agent-framework && git pull
cd ~/Dev/<project>/brain
python ~/Dev/decomp-agent-framework/install.py . --update
```

## License

MIT. See [LICENSE](LICENSE).
