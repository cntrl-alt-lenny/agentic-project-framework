#!/usr/bin/env python3
"""Adapter manifests: where an adapter's files actually go.

THE DEFECT THIS MODULE CLOSES. Adoption used to derive a provider's destination
directory by prepending a dot to its adapter name, so the adapter named
``claude-code`` installed at ``.claude-code/``. The tool it adapts reads
``.claude/``, which is what the adapter's own README and its ``settings.json``
both said. Nothing crashed: the files landed in a directory the tool never
reads, and the hook path inside the installed settings pointed at a directory
adoption had not created.

The class, stated once so it stays fixed:

    **An adapter's framework identifier is not its filesystem layout.**

An adapter's name is how a project asks for it on the command line. Where its
files belong, and under what names, is a property of the tool -- and tools do
not agree about it. Some want a dotted directory, some a plain one, some a file
at the repository root, some several places at once. None of that is derivable
from a name, so none of it is derived here: every adapter declares its own
layout in ``adapter.json``, and an adapter without one is a hard error rather
than a guess.

Manifest fields:

``tool``          Required. Human name of the tool this adapts. Documentation
                  only -- nothing keys off it.
``install_root``  Required. Destination directory, relative to the target
                  repository root. Every source file lands under it unless
                  ``layout`` says otherwise.
``seats_dir``     Optional. Source subdirectory holding this adapter's role
                  seat files, so callers can find them without assuming a
                  layout. Omit if the adapter ships none.
``layout``        Optional. Source path (a file, or a directory prefix) mapped
                  to a destination relative to the **target repository root**,
                  for tools that want part of their configuration somewhere
                  else entirely. Longest matching prefix wins.
``exclude``       Optional. Source paths never installed. The manifest itself
                  is always excluded.

Destinations are validated: relative, non-empty, no ``..``, no drive or root.
A manifest that fails validation stops adoption rather than installing files
somewhere unintended.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

MANIFEST_NAME = "adapter.json"


class AdapterError(Exception):
    """A manifest is missing, unreadable, or would install somewhere unsafe."""


def _check_destination(value: object, *, field: str, source: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AdapterError(f"{source}: '{field}' must be a non-empty string")
    raw = value.strip()
    # Absoluteness is rejected, never normalised away: silently turning "/etc"
    # into "etc" would install somewhere the author did not ask for and did not
    # expect, which is the same failure mode in a different costume.
    if raw.startswith(("/", "\\", "~")) or ":" in raw:
        raise AdapterError(
            f"{source}: '{field}' must be relative to the target repository"
        )
    cleaned = raw.rstrip("/")
    if not cleaned:
        raise AdapterError(f"{source}: '{field}' must not be the repository root")
    path = PurePosixPath(cleaned)
    if ".." in path.parts:
        raise AdapterError(f"{source}: '{field}' must not escape the target with '..'")
    return cleaned


@dataclass(frozen=True)
class Adapter:
    """One provider adapter, and the layout it declares for itself."""

    name: str
    root: Path
    tool: str
    install_root: str
    seats_dir: str | None
    layout: tuple[tuple[str, str], ...]
    exclude: frozenset

    def source_files(self) -> list[Path]:
        """Every file this adapter installs, manifest and exclusions removed."""
        return [
            p for p in sorted(self.root.rglob("*"))
            if p.is_file()
            and p.relative_to(self.root).as_posix() not in self.exclude
        ]

    def destination(self, rel: str) -> str:
        """Where one source-relative path lands in the target repository.

        Longest declared prefix wins; anything unmatched goes under
        ``install_root``. The name of the adapter is never consulted.
        """
        for prefix, dest in self.layout:
            if rel == prefix:
                return dest
            if rel.startswith(prefix + "/"):
                return f"{dest}/{rel[len(prefix) + 1:]}"
        return f"{self.install_root}/{rel}"

    def installed_paths(self) -> list[str]:
        return [
            self.destination(p.relative_to(self.root).as_posix())
            for p in self.source_files()
        ]

    def seat_files(self) -> list[Path]:
        """This adapter's role seat files, per its declared ``seats_dir``."""
        if self.seats_dir is None:
            return []
        return sorted((self.root / self.seats_dir).glob("*.md"))

    def seat_roles(self) -> list[str]:
        return [p.stem for p in self.seat_files()]


def load(root: Path) -> Adapter:
    """Read and validate one adapter directory's manifest."""
    manifest = root / MANIFEST_NAME
    source = f"{root.name}/{MANIFEST_NAME}"
    if not manifest.is_file():
        raise AdapterError(
            f"adapter '{root.name}' has no {MANIFEST_NAME}. An adapter must "
            f"declare where its files belong; the destination is never derived "
            f"from the adapter's name."
        )
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdapterError(f"{source}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise AdapterError(f"{source}: manifest must be a JSON object")

    unknown = sorted(
        set(data) - {"tool", "install_root", "seats_dir", "layout", "exclude"}
    )
    if unknown:
        raise AdapterError(f"{source}: unknown manifest field(s): {unknown}")

    tool = data.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        raise AdapterError(f"{source}: 'tool' must be a non-empty string")

    install_root = _check_destination(
        data.get("install_root"), field="install_root", source=source
    )

    seats_dir = data.get("seats_dir")
    if seats_dir is not None:
        seats_dir = _check_destination(seats_dir, field="seats_dir", source=source)
        if not (root / seats_dir).is_dir():
            raise AdapterError(
                f"{source}: 'seats_dir' names '{seats_dir}', which is not a "
                f"directory in this adapter"
            )

    raw_layout = data.get("layout", {})
    if not isinstance(raw_layout, dict):
        raise AdapterError(f"{source}: 'layout' must be an object")
    layout: list[tuple[str, str]] = []
    for src, dest in raw_layout.items():
        src_clean = _check_destination(src, field=f"layout['{src}']", source=source)
        if not (root / src_clean).exists():
            raise AdapterError(
                f"{source}: layout maps '{src_clean}', which this adapter does "
                f"not contain"
            )
        layout.append(
            (src_clean, _check_destination(
                dest, field=f"layout['{src}']", source=source))
        )
    # Longest prefix first, so a specific file beats the directory holding it.
    layout.sort(key=lambda pair: len(pair[0]), reverse=True)

    raw_exclude = data.get("exclude", [])
    if not isinstance(raw_exclude, list) or any(
        not isinstance(x, str) for x in raw_exclude
    ):
        raise AdapterError(f"{source}: 'exclude' must be a list of strings")
    exclude = {x.strip().strip("/") for x in raw_exclude if x.strip()}
    exclude.add(MANIFEST_NAME)

    return Adapter(
        name=root.name,
        root=root,
        tool=tool.strip(),
        install_root=install_root,
        seats_dir=seats_dir,
        layout=tuple(layout),
        exclude=frozenset(exclude),
    )


def available(adapters_dir: Path) -> list[str]:
    return sorted(p.name for p in adapters_dir.iterdir() if p.is_dir())


def load_all(adapters_dir: Path) -> list[Adapter]:
    return [load(adapters_dir / name) for name in available(adapters_dir)]
