#!/usr/bin/env python3
"""Which documents in this repository are normative, and which record history.

The split matters: normative documents define policy and must be
provider-neutral and free of stale authority language. Historical documents —
the failure catalogue and the case studies — deliberately quote broken forms and
name the tools that actually ran, because that is the evidence.

**The normative set is derived from the tree, never enumerated.** A new document
under `framework/` is therefore scanned by default. Escaping the scan requires
adding the file to `HISTORICAL` *and* writing "historical document" inside it —
a visible act, not an omission.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: This repository's own role vocabulary, declared once. Its normative documents
#: use Brain plus these executor names -- including the specialist names that
#: appear as topology examples, so those examples are held to the same rules as
#: everything else.
ROLES: tuple[str, ...] = (
    "worker", "builder", "verifier", "decomper", "scaffolder", "researcher",
)
COORDINATOR = "brain"

#: Documents that record what happened rather than defining policy. Each must
#: declare itself as such in its own text; `tests/test_provider_neutrality.py`
#: enforces that, so this list cannot be used to quietly exempt a policy file.
HISTORICAL: tuple[str, ...] = (
    "framework/failure-catalogue.md",
    "framework/case-studies.md",
    "CHANGELOG.md",
)

#: Not policy and not history: a test fixture preserving known-bad text on
#: purpose. Named explicitly so it cannot become an unnoticed third category.
FIXTURES: tuple[str, ...] = (
    "tests/fixtures/v1_stale_authority.md",
)

HISTORICAL_MARKER = "historical document"


def historical_files() -> list[Path]:
    return [ROOT / rel for rel in HISTORICAL]


def normative_files() -> list[Path]:
    """Every policy-defining document, derived from the tree."""
    excluded = {(ROOT / rel).resolve() for rel in HISTORICAL}
    paths: list[Path] = []
    for base in (ROOT / "framework", ROOT / "templates", ROOT / "adapters"):
        if base.is_dir():
            paths += sorted(base.rglob("*.md"))
    paths.append(ROOT / "README.md")
    return [
        p for p in paths
        if p.is_file() and p.resolve() not in excluded
    ]


def all_documents() -> list[Path]:
    return normative_files() + [p for p in historical_files() if p.is_file()]


def classified() -> set[Path]:
    """Every document this repository has made a deliberate decision about."""
    return (
        {p.resolve() for p in normative_files()}
        | {p.resolve() for p in historical_files()}
        | {(ROOT / rel).resolve() for rel in FIXTURES}
    )


def unclassified() -> list[Path]:
    """Markdown that is neither normative, historical, nor a declared fixture.

    Fails closed: a new document is normative by default, so this should only
    ever be non-empty when one lands outside every scanned directory.
    """
    known = classified()
    out = []
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts or path.name.startswith("."):
            continue
        if path.resolve() not in known:
            out.append(path)
    return out
