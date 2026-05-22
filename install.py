#!/usr/bin/env python3

"""install.py — install the decomp-agent-framework into a target project.

Typical use is layering this framework onto an existing decomp project
(often a fork of someone else's upstream that already has its own build
system).

# Usage

    python install.py <target-dir>                       # interactive
    python install.py <target-dir> --yaml config.yaml    # non-interactive
    python install.py <target-dir> --dry-run             # show what'd change
    python install.py <target-dir> --update              # re-sync script
                                                         # files only; don't
                                                         # re-prompt placeholders

# What it copies

From this framework's `framework/` directory:

    .claude/agents/{brain,decomper,scaffolder}.md
    .claude/hooks/{save_agent_reply,post_edit,pre_bash}.py
    .claude/settings.json
    AGENTS.md
    docs/decomp-workflow.md
    docs/state.md
    docs/briefs/README.md

# Placeholder substitution

Files containing `{{NAME}}` tokens get rendered against project
metadata. The placeholder set is:

  {{GAME_NAME}}      e.g. "Yu-Gi-Oh! GX Spirit Caller"
  {{HUMAN_HANDLE}}   e.g. "cntrl_alt_lenny"
  {{TOOLCHAIN_NAME}} e.g. "mwccarm 2.0/sp1p5"
  {{BASEROM_PATH}}   e.g. "orig/baserom_eur.nds"
  {{REGIONS}}        e.g. "EUR / USA / JPN"
  {{PROJECT_DIR}}    e.g. "spirit-caller"  (the parent dir name used in
                     worktree-convention examples)

The `save_agent_reply.py` hook is copied verbatim (no substitution
needed — it's path-agnostic).

# Safety / fork-friendliness

- Detects and merges with an existing `.claude/` directory.
- Detects `.claude/` in `.gitignore` (common in upstream-forked
  projects): default to local-only install; use `--force-track` to
  add a `!.claude/` exception override.
- Skips and warns on collisions for `AGENTS.md`, `docs/state.md`,
  `docs/decomp-workflow.md`, `docs/briefs/README.md`. Writes
  `AGENTS.md.framework` as a sibling when `AGENTS.md` already exists.
- Never touches `CLAUDE.md`, build system files, `src/`, `config/`,
  ROM files, or anything outside the framework's scope.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
FRAMEWORK = THIS_DIR / "framework"

# Files copied verbatim (no placeholder substitution).
VERBATIM_FILES = [
    ".claude/hooks/save_agent_reply.py",
    ".claude/hooks/post_edit.py",
    ".claude/hooks/pre_bash.py",
]

# Files with placeholder substitution.
TEMPLATED_FILES = [
    ".claude/agents/brain.md",
    ".claude/agents/decomper.md",
    ".claude/agents/scaffolder.md",
    ".claude/settings.json",
    "AGENTS.md",
    "docs/decomp-workflow.md",
    "docs/state.md",
    "docs/briefs/README.md",
]

# Files that get a `.framework` sibling instead of clobbering when the
# target already has one.
COLLISION_SIBLING_FILES = {
    "AGENTS.md",
    "docs/state.md",
    "docs/decomp-workflow.md",
    "docs/briefs/README.md",
}

PLACEHOLDERS = [
    ("GAME_NAME", "Game name (e.g. 'Yu-Gi-Oh! GX Spirit Caller')"),
    ("HUMAN_HANDLE", "Your handle (e.g. 'cntrl_alt_lenny')"),
    ("TOOLCHAIN_NAME", "Compiler / toolchain (e.g. 'mwccarm 2.0/sp1p5')"),
    ("BASEROM_PATH", "Baserom path (e.g. 'orig/baserom_eur.nds')"),
    ("REGIONS", "Regions covered (e.g. 'EUR / USA / JPN')"),
    ("PROJECT_DIR", "Project dir basename for worktree examples "
                    "(e.g. 'spirit-caller')"),
]

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")


@dataclass
class Plan:
    """Pending file operations. Materialised in apply()."""
    writes: list[tuple[Path, str, bool]] = field(default_factory=list)
    # (target_path, content, executable_bit)
    skips: list[tuple[Path, str]] = field(default_factory=list)
    # (path, reason)
    warnings: list[str] = field(default_factory=list)
    gitignore_action: str | None = None  # "add-exception" | "local-only" | None


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
    except ImportError:
        print(
            "[install] --yaml requires PyYAML. Install with "
            "`python -m pip install pyyaml`.",
            file=sys.stderr,
        )
        sys.exit(2)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        print(f"[install] {path} must be a YAML mapping.", file=sys.stderr)
        sys.exit(2)
    return data


def _prompt_placeholders(prefill: dict | None = None) -> dict[str, str]:
    """Ask the user for each placeholder; honour values from prefill."""
    out: dict[str, str] = {}
    prefill = prefill or {}
    print("\n[install] Project metadata — fill in each value, blank to skip:")
    for key, desc in PLACEHOLDERS:
        default = prefill.get(key) or prefill.get(key.lower()) or ""
        prompt = f"  {key} — {desc}"
        if default:
            prompt += f" [{default}]"
        prompt += ": "
        try:
            val = input(prompt).strip() or default
        except EOFError:
            val = default
        out[key] = val
    print()
    return out


def _render(text: str, values: dict[str, str]) -> str:
    def sub(match: re.Match[str]) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))
    return PLACEHOLDER_RE.sub(sub, text)


def _is_gitignored(target_root: Path, rel_path: str) -> bool:
    """Return True if `rel_path` (relative to target_root) is ignored
    by the target's git repo. Returns False if the target isn't a git
    repo at all."""
    if not (target_root / ".git").exists():
        return False
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=str(target_root),
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    # check-ignore: 0 = path is ignored; 1 = not ignored; 128 = error.
    return proc.returncode == 0


def _gitignore_path(target_root: Path) -> Path:
    return target_root / ".gitignore"


def _has_exception_for_claude(target_root: Path) -> bool:
    gi = _gitignore_path(target_root)
    if not gi.exists():
        return False
    for line in gi.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s in ("!.claude/", "!.claude"):
            return True
    return False


def plan_install(
    target: Path,
    values: dict[str, str],
    *,
    update_only: bool = False,
    force_track: bool = False,
) -> Plan:
    plan = Plan()

    # Decide which file list applies.
    if update_only:
        # Update mode: only the script-y files (hooks). Don't
        # re-write agent definitions, settings.json, AGENTS.md, or
        # docs templates — those are templated against project
        # metadata and may have been edited per-project after the
        # initial install.
        files_to_process = list(VERBATIM_FILES)
    else:
        files_to_process = list(VERBATIM_FILES) + list(TEMPLATED_FILES)

    # Handle the gitignore-on-.claude/ case before file writes.
    claude_gitignored = _is_gitignored(target, ".claude/")
    if claude_gitignored:
        if force_track:
            if _has_exception_for_claude(target):
                plan.warnings.append(
                    ".claude/ is gitignored but already has a `!.claude/` "
                    "exception in .gitignore. Leaving .gitignore alone."
                )
                plan.gitignore_action = None
            else:
                plan.gitignore_action = "add-exception"
        else:
            plan.gitignore_action = "local-only"
            plan.warnings.append(
                "Detected `.claude/` is gitignored in the target. Installing "
                "LOCAL-ONLY: framework files land on disk but won't be "
                "committed. Re-run with --force-track to add a `!.claude/` "
                "exception override, or keep this mode and back up the "
                "files separately (e.g. sibling repo / syncthing). A "
                "factory-reset wipe of the clone will lose them."
            )

    for rel in files_to_process:
        src = FRAMEWORK / rel
        if not src.is_file():
            plan.warnings.append(
                f"[bug] framework file missing: {src} — skipping."
            )
            continue
        dst = target / rel
        is_executable = src.stat().st_mode & 0o111 != 0

        # Determine the actual destination (collision handling).
        if not update_only and rel in COLLISION_SIBLING_FILES and dst.exists():
            sibling = dst.with_name(dst.name + ".framework")
            plan.warnings.append(
                f"{rel} already exists in target. Writing framework "
                f"version to {sibling.relative_to(target)} instead — "
                f"merge by hand."
            )
            actual_dst = sibling
        else:
            actual_dst = dst

        # Render content.
        raw = src.read_text(encoding="utf-8")
        if rel in VERBATIM_FILES:
            content = raw
        else:
            content = _render(raw, values)

        # In update mode: if the existing file content is identical to
        # what we'd write, skip silently.
        if update_only and actual_dst.exists():
            existing = actual_dst.read_text(encoding="utf-8")
            if existing == content:
                plan.skips.append((actual_dst, "unchanged"))
                continue

        plan.writes.append((actual_dst, content, is_executable))

    return plan


def render_plan(plan: Plan, target: Path) -> str:
    lines: list[str] = []
    if plan.gitignore_action == "add-exception":
        lines.append(
            f"  + append `!.claude/` exception to {target / '.gitignore'}"
        )
    elif plan.gitignore_action == "local-only":
        lines.append(
            "  ! local-only install (.claude/ is gitignored; files land "
            "on disk only)"
        )
    for dst, _, is_exec in plan.writes:
        try:
            rel = dst.relative_to(target)
        except ValueError:
            rel = dst
        marker = " (exec)" if is_exec else ""
        action = "write" if not dst.exists() else "overwrite"
        lines.append(f"  {action:>9} {rel}{marker}")
    for path, reason in plan.skips:
        try:
            rel = path.relative_to(target)
        except ValueError:
            rel = path
        lines.append(f"  {'skip':>9} {rel}  ({reason})")
    for w in plan.warnings:
        lines.append(f"  [warn] {w}")
    if not lines:
        lines.append("  (nothing to do)")
    return "\n".join(lines)


def apply_plan(plan: Plan, target: Path) -> None:
    if plan.gitignore_action == "add-exception":
        gi = _gitignore_path(target)
        prefix = "\n" if gi.exists() and not gi.read_text(
            encoding="utf-8"
        ).endswith("\n") else ""
        with gi.open("a", encoding="utf-8") as f:
            f.write(
                prefix
                + "\n# Allow the decomp-agent-framework's .claude/ files\n"
                + "# (counter-acts the upstream gitignore so the framework\n"
                + "# is version-controlled in this fork).\n"
                + "!.claude/\n"
            )

    for dst, content, is_exec in plan.writes:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        if is_exec:
            mode = dst.stat().st_mode
            dst.chmod(mode | 0o111)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Install the decomp-agent-framework into a target "
        "project."
    )
    ap.add_argument("target", help="Target project directory.")
    ap.add_argument(
        "--yaml",
        type=Path,
        help="YAML config with placeholder values "
        "(non-interactive mode).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the plan without writing anything.",
    )
    ap.add_argument(
        "--update",
        action="store_true",
        help="Re-sync just the script files (e.g. updated "
        "save_agent_reply.py); don't re-prompt for placeholders or "
        "touch the AGENTS.md / docs/ templates.",
    )
    ap.add_argument(
        "--force-track",
        action="store_true",
        help="If `.claude/` is gitignored in the target, add a "
        "`!.claude/` exception to .gitignore so the framework gets "
        "version-controlled in this fork.",
    )
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(
            f"[install] target directory does not exist: {target}",
            file=sys.stderr,
        )
        return 2

    # Placeholder values.
    values: dict[str, str]
    if args.update:
        values = {}  # not used in update mode
    elif args.yaml:
        prefill = _load_yaml(args.yaml)
        # Normalise keys to UPPER for the renderer.
        prefill_upper = {
            k.upper(): str(v) for k, v in prefill.items()
            if isinstance(v, (str, int, float))
        }
        # In yaml mode, don't prompt — use given values + leave others
        # as placeholders.
        values = {k: prefill_upper.get(k, "") for k, _ in PLACEHOLDERS}
        # Render `{{KEY}}` for any blank values so the user sees what's
        # left to fill in by hand.
        values = {k: (v or f"{{{{{k}}}}}") for k, v in values.items()}
    elif args.dry_run:
        # Dry-run interactive would block; supply empty values.
        values = {k: f"{{{{{k}}}}}" for k, _ in PLACEHOLDERS}
    else:
        values = _prompt_placeholders()
        # Leave un-filled placeholders as `{{KEY}}` for clarity.
        values = {k: (v or f"{{{{{k}}}}}") for k, v in values.items()}

    plan = plan_install(
        target,
        values,
        update_only=args.update,
        force_track=args.force_track,
    )

    print(f"[install] plan for {target}:")
    print(render_plan(plan, target))

    if args.dry_run:
        print("\n[install] --dry-run; no files written.")
        return 0

    if not plan.writes and plan.gitignore_action != "add-exception":
        print("\n[install] nothing to do.")
        return 0

    apply_plan(plan, target)
    print("\n[install] done.")
    if plan.gitignore_action == "local-only":
        print(
            "\n[install] Reminder: .claude/ is gitignored in the "
            "target. Framework files are on disk but won't be "
            "committed. Re-run with --force-track to override, or "
            "back the files up separately."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
