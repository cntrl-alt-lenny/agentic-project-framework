#!/usr/bin/env python3
"""Copy this framework into a target repository.

This does the **mechanical** half of adoption. The judgement half — choosing a
topology, writing the project's invariants and its evidence table — is described
in `framework/adoption.md` and is not automatable.

    python tools/adopt.py <target> --project "Name" [options]

Options:
    --project NAME     Human-readable project name. Required.
    --workers a,b      Executor role names (default: worker). Brain is always
                       present; a specialist is the Worker contract plus a scope
                       statement, not a new contract.
    --verifier         Include the independent reviewer seat.
    --coordinator NAME Name of the coordinating role (default: brain).
    --hooks            Install the sample git pre-push hook.
    --adapter NAME     Install a bundled provider adapter (repeatable).
    --dry-run          Print the plan; write nothing.

Safety: an existing file is never overwritten. The framework version is written
alongside it as `<name>.framework` and reported as a collision to merge by hand.
Re-running is therefore safe and idempotent.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMEWORK = ROOT / "framework"
TEMPLATES = ROOT / "templates"
ADAPTERS = ROOT / "adapters"

#: Framework documents copied verbatim into the target. Generic by design: a
#: project does not edit them, so they cannot drift from this repository.
VERBATIM_DOCS = (
    "CONSTITUTION.md",
    "adapters.md",
    "briefs.md",
    "evidence.md",
    "git-and-isolation.md",
    "lifecycle.md",
    "state.md",
    "topologies.md",
    "roles/README.md",
    "roles/brain.md",
    "roles/worker.md",
    "roles/verifier.md",
)

#: Historical to this repository, never copied: they are its evidence, not the
#: adopting project's.
NOT_COPIED = ("failure-catalogue.md", "case-studies.md", "adoption.md")

DOCS_DEST = "docs/agents"


@dataclass
class Plan:
    writes: list[tuple[Path, str, bool]] = field(default_factory=list)
    collisions: list[tuple[Path, Path]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def topology_diagram(coordinator: str, workers: list[str], verifier: bool) -> str:
    seats = list(workers) + (["verifier"] if verifier else [])
    lines = ["```", "Owner", f"└── {coordinator.capitalize()}"]
    for i, seat in enumerate(seats):
        connector = "└──" if i == len(seats) - 1 else "├──"
        lines.append(f"    {connector} {seat.capitalize()}")
    lines.append("```")
    return "\n".join(lines)


def role_table(coordinator: str, workers: list[str], verifier: bool) -> str:
    rows = [
        "| Role | Holds | Scope |",
        "|---|---|---|",
        "| **Owner** | Direction, priorities, scope. Veto and reversal. | — |",
        f"| **{coordinator.capitalize()}** | Project context, sequencing, briefs, "
        f"adjudication, and the routine merge. "
        f"([contract](docs/agents/roles/brain.md)) | <!-- what it owns --> |",
    ]
    for w in workers:
        rows.append(
            f"| **{w.capitalize()}** | One bounded brief at a time. Never "
            f"self-accepts, never merges. "
            f"([contract](docs/agents/roles/worker.md)) | <!-- disjoint scope --> |"
        )
    if verifier:
        rows.append(
            "| **Verifier** | Independent review of an exact SHA. Writes "
            "findings, never merges. "
            "([contract](docs/agents/roles/verifier.md)) | Read-only. |"
        )
    if len(workers) > 1:
        rows.append("")
        rows.append(
            "Executor scopes must not overlap. Each concurrently-active role "
            "gets its own checkout."
        )
    return "\n".join(rows)


def render(text: str, values: dict[str, str]) -> str:
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", val)
    return text


def build_plan(
    target: Path,
    *,
    project: str,
    coordinator: str,
    workers: list[str],
    verifier: bool,
    hooks: bool,
    adapters: list[str],
) -> Plan:
    plan = Plan()

    def add(rel: str, content: str, executable: bool = False) -> None:
        dst = target / rel
        if dst.exists():
            sibling = dst.with_name(dst.name + ".framework")
            plan.collisions.append((dst, sibling))
            plan.writes.append((sibling, content, executable))
        else:
            plan.writes.append((dst, content, executable))

    for rel in VERBATIM_DOCS:
        src = FRAMEWORK / rel
        if not src.is_file():
            raise SystemExit(f"framework file missing: {src}")
        add(f"{DOCS_DEST}/{rel}", src.read_text(encoding="utf-8"))

    values = {
        "PROJECT": project,
        "TOPOLOGY_DIAGRAM": topology_diagram(coordinator, workers, verifier),
        "ROLE_TABLE": role_table(coordinator, workers, verifier),
        "ROLES": repr(tuple(workers + (["verifier"] if verifier else []))),
        "COORDINATOR": coordinator,
    }

    add("AGENTS.md", render((TEMPLATES / "AGENTS.md").read_text(encoding="utf-8"), values))
    add("docs/state.md", (TEMPLATES / "docs/state.md").read_text(encoding="utf-8"))
    add("docs/briefs/README.md",
        (TEMPLATES / "docs/briefs/README.md").read_text(encoding="utf-8"))
    add("docs/briefs/active.md",
        (TEMPLATES / "docs/briefs/active.md").read_text(encoding="utf-8"))
    for sub in ("delivered", "archive"):
        add(f"docs/briefs/{sub}/.gitkeep",
            (TEMPLATES / f"docs/briefs/{sub}/.gitkeep").read_text(encoding="utf-8"))

    # Every module the installed test imports, or it fails on import in the
    # target rather than guarding anything there.
    for module in ("neutrality.py", "authority.py", "textblocks.py"):
        add(f"tools/{module}", (ROOT / "tools" / module).read_text(encoding="utf-8"))
    # Without this, `unittest discover -s tests` refuses the directory and the
    # installed guard never runs at all. Caught by tests/test_adopt.py, which
    # runs the guard in the adopted tree rather than checking it exists.
    add("tests/__init__.py", "")
    add("tests/test_role_neutrality.py",
        render((TEMPLATES / "tests/test_role_neutrality.py").read_text(encoding="utf-8"),
               values))

    if hooks:
        add(".githooks/pre-push",
            (TEMPLATES / "githooks/pre-push").read_text(encoding="utf-8"),
            executable=True)
        plan.notes.append(
            "The pre-push hook is opt-in per clone and fails silently until "
            "`git config core.hooksPath .githooks` is run. It is early "
            "feedback, never a control."
        )

    for name in adapters:
        src_dir = ADAPTERS / name
        if not src_dir.is_dir():
            raise SystemExit(
                f"unknown adapter '{name}'; available: "
                f"{', '.join(sorted(p.name for p in ADAPTERS.iterdir() if p.is_dir()))}"
            )
        for src in sorted(p for p in src_dir.rglob("*") if p.is_file()):
            rel = src.relative_to(src_dir).as_posix()
            add(f".{name}/{rel}", src.read_text(encoding="utf-8"),
                executable=src.suffix == ".py")

    plan.notes.append(
        "Now do the judgement half: write AGENTS.md's invariants, evidence "
        "table and enforcement section. See framework/adoption.md."
    )
    return plan


def render_plan(plan: Plan, target: Path) -> str:
    out = []
    for dst, _, executable in plan.writes:
        rel = dst.relative_to(target)
        out.append(f"  write  {rel}{' (exec)' if executable else ''}")
    for existing, sibling in plan.collisions:
        out.append(
            f"  KEEP   {existing.relative_to(target)} (exists) — framework "
            f"version written to {sibling.name}, merge by hand"
        )
    for note in plan.notes:
        out.append(f"  note   {note}")
    return "\n".join(out) or "  (nothing to do)"


def apply_plan(plan: Plan) -> None:
    for dst, content, executable in plan.writes:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content, encoding="utf-8")
        if executable:
            dst.chmod(dst.stat().st_mode | 0o111)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target")
    ap.add_argument("--project", required=True)
    ap.add_argument("--workers", default="worker")
    ap.add_argument("--verifier", action="store_true")
    ap.add_argument("--coordinator", default="brain")
    ap.add_argument("--hooks", action="store_true")
    ap.add_argument("--adapter", action="append", default=[])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        print(f"adopt: target is not a directory: {target}", file=sys.stderr)
        return 2

    workers = [w.strip() for w in args.workers.split(",") if w.strip()]
    if not workers:
        print("adopt: --workers needs at least one role", file=sys.stderr)
        return 2
    reserved = {args.coordinator, "verifier", "owner"}
    clash = sorted(set(workers) & reserved)
    if clash:
        print(f"adopt: executor role name(s) clash with a reserved role: {clash}",
              file=sys.stderr)
        return 2

    plan = build_plan(
        target,
        project=args.project,
        coordinator=args.coordinator,
        workers=workers,
        verifier=args.verifier,
        hooks=args.hooks,
        adapters=args.adapter,
    )

    print(f"adopt: plan for {target}")
    print(render_plan(plan, target))
    if args.dry_run:
        print("\nadopt: --dry-run; nothing written.")
        return 0
    apply_plan(plan)
    print("\nadopt: done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
