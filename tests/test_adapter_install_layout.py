"""Where an adapter's files land is declared, never inferred from its name.

THE DEFECT THESE GUARDS CLOSE. Adoption derived a provider's destination
directory by prepending a dot to its adapter name, so the adapter named
`claude-code` installed at `.claude-code/`. The tool reads `.claude/` — which
the adapter's own README said, and which its `settings.json` hardcoded in the
hook command it installs. Nothing failed loudly: the configuration landed where
the tool never looks, and the installed settings referenced a directory
adoption had not created. A test asserting `.claude-code/agents/worker.md`
existed had codified the bug.

The class, not the instance:

    **An adapter's framework identifier is not its filesystem layout.**

So these guards are about the mechanism rather than about one string:

1. Every bundled adapter declares a layout, and adoption refuses one that does
   not. There is no name-derived fallback to fall back *to* — a fallback is
   what let a wrong path look like a working one.
2. Adoption installs at the declared destination even when it differs from the
   adapter's name, proved with a synthetic adapter whose name and root share no
   text at all. A guard that only checked `.claude` would pass on an installer
   that still prepends a dot to the name.
3. An adapter's README and its manifest must agree, because they disagreeing
   silently is the whole incident.
4. Every path an installed adapter file refers to inside its own install root
   must actually exist in the adopted tree. This is the guard that catches the
   dangling hook command directly, whatever the paths happen to be called.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import adapters as adapter_manifests  # noqa: E402
import adopt  # noqa: E402

ADAPTERS = ROOT / "adapters"

#: A path-looking token inside a document. Trailing sentence punctuation is
#: stripped before the path is resolved.
PATHISH = r"[A-Za-z0-9_./-]*"


def adopt_into(target: Path, *extra: str) -> int:
    return adopt.main([str(target), "--project", "Layout Test", *extra])


def referenced_paths(text: str, root: str) -> set[str]:
    """Paths under `root` that this text tells a reader or a tool to use."""
    found = set()
    for raw in re.findall(re.escape(root) + PATHISH, text):
        cleaned = raw.rstrip(".,;:)`\"'").rstrip("/")
        if cleaned:
            found.add(cleaned)
    return found


class TestEveryAdapterDeclaresItsLayout(unittest.TestCase):
    def test_there_is_at_least_one_adapter(self):
        # Fail closed: with no adapters these guards would pass vacuously.
        self.assertTrue(adapter_manifests.available(ADAPTERS))

    def test_every_adapter_has_a_valid_manifest(self):
        for name in adapter_manifests.available(ADAPTERS):
            with self.subTest(adapter=name):
                manifest = adapter_manifests.load(ADAPTERS / name)
                self.assertTrue(manifest.install_root)
                self.assertTrue(manifest.tool)

    def test_the_manifest_is_not_installed_into_the_target(self):
        for manifest in adapter_manifests.load_all(ADAPTERS):
            with self.subTest(adapter=manifest.name):
                self.assertNotIn(
                    adapter_manifests.MANIFEST_NAME,
                    [Path(p).name for p in manifest.installed_paths()],
                    "the manifest describes installation; it is not installed",
                )

    def test_the_readme_states_the_declared_install_root(self):
        """Documentation and behaviour must agree, in the file people read.

        They disagreed, and that is exactly how this shipped: the README said
        one directory and the installer wrote another.
        """
        for manifest in adapter_manifests.load_all(ADAPTERS):
            readme = manifest.root / "README.md"
            with self.subTest(adapter=manifest.name):
                self.assertTrue(readme.is_file(), "an adapter needs a README")
                self.assertIn(
                    manifest.install_root,
                    readme.read_text(encoding="utf-8"),
                    f"{manifest.name}/README.md does not name the destination "
                    f"its manifest declares ({manifest.install_root})",
                )


class TestDestinationIsNeverDerivedFromTheName(unittest.TestCase):
    """The class guard. The name is an identifier; the root is a fact."""

    def test_the_loader_refuses_an_adapter_with_no_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "some-tool"
            (fake / "agents").mkdir(parents=True)
            with self.assertRaises(adapter_manifests.AdapterError) as caught:
                adapter_manifests.load(fake)
            self.assertIn("adapter.json", str(caught.exception))

    def test_adoption_refuses_an_adapter_with_no_manifest(self):
        """No silent guess. Refusing beats installing somewhere plausible."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_adapters = tmp_path / "adapters"
            (fake_adapters / "some-tool").mkdir(parents=True)
            (fake_adapters / "some-tool" / "notes.md").write_text("x\n")
            target = tmp_path / "target"
            target.mkdir()

            original = adopt.ADAPTERS
            adopt.ADAPTERS = fake_adapters
            try:
                with self.assertRaises(SystemExit):
                    adopt_into(target, "--adapter", "some-tool")
            finally:
                adopt.ADAPTERS = original
            self.assertFalse(
                (target / ".some-tool").exists(),
                "adoption invented a destination from the adapter's name",
            )

    def test_a_declared_root_unrelated_to_the_name_is_honoured(self):
        """Name and root share no text, so a name-derived path cannot pass."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_adapters = tmp_path / "adapters"
            src = fake_adapters / "zulu-tool"
            (src / "agents").mkdir(parents=True)
            (src / "adapter.json").write_text(
                json.dumps({
                    "tool": "Zulu",
                    "install_root": "config/quebec",
                    "seats_dir": "agents",
                }),
                encoding="utf-8",
            )
            (src / "README.md").write_text("Installs at config/quebec.\n")
            (src / "agents" / "worker.md").write_text("seat\n")
            target = tmp_path / "target"
            target.mkdir()

            original = adopt.ADAPTERS
            adopt.ADAPTERS = fake_adapters
            try:
                self.assertEqual(adopt_into(target, "--adapter", "zulu-tool"), 0)
            finally:
                adopt.ADAPTERS = original

            self.assertTrue((target / "config/quebec/agents/worker.md").is_file())
            self.assertFalse((target / ".zulu-tool").exists())

    def test_layout_can_place_a_file_outside_the_install_root(self):
        """Some tools want part of their configuration somewhere else.

        Supporting that is the point of a declared layout rather than a single
        derived prefix.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_adapters = tmp_path / "adapters"
            src = fake_adapters / "zulu-tool"
            src.mkdir(parents=True)
            (src / "adapter.json").write_text(
                json.dumps({
                    "tool": "Zulu",
                    "install_root": "config/quebec",
                    "layout": {"toolrc": "toolrc"},
                }),
                encoding="utf-8",
            )
            (src / "README.md").write_text("Installs at config/quebec.\n")
            (src / "toolrc").write_text("k=v\n")
            (src / "other.md").write_text("x\n")
            target = tmp_path / "target"
            target.mkdir()

            original = adopt.ADAPTERS
            adopt.ADAPTERS = fake_adapters
            try:
                self.assertEqual(adopt_into(target, "--adapter", "zulu-tool"), 0)
            finally:
                adopt.ADAPTERS = original

            self.assertTrue((target / "toolrc").is_file())
            self.assertTrue((target / "config/quebec/other.md").is_file())

    def test_a_destination_escaping_the_target_is_refused(self):
        for bad in ("../outside", "/etc", "", "   "):
            with self.subTest(root=bad):
                with tempfile.TemporaryDirectory() as tmp:
                    src = Path(tmp) / "zulu-tool"
                    src.mkdir()
                    (src / "adapter.json").write_text(
                        json.dumps({"tool": "Zulu", "install_root": bad}),
                        encoding="utf-8",
                    )
                    with self.assertRaises(adapter_manifests.AdapterError):
                        adapter_manifests.load(src)


class TestAdoptedAdapterTreeIsUsable(unittest.TestCase):
    """Behavioural: adopt for real, then inspect the tree that was produced."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name)
        assert adopt_into(cls.target, "--adapter", "claude-code") == 0

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_claude_code_adapter_installs_the_intended_structure(self):
        for rel in (
            ".claude/settings.json",
            ".claude/README.md",
            ".claude/agents/brain.md",
            ".claude/agents/worker.md",
            ".claude/agents/verifier.md",
            ".claude/commands/status.md",
            ".claude/hooks/save_agent_reply.py",
        ):
            with self.subTest(path=rel):
                self.assertTrue((self.target / rel).is_file(), rel)

    def test_nothing_is_installed_at_the_name_derived_path(self):
        self.assertFalse(
            (self.target / ".claude-code").exists(),
            "the adapter name was used as a filesystem path again",
        )

    def test_every_installed_file_is_where_the_manifest_says(self):
        manifest = adapter_manifests.load(ADAPTERS / "claude-code")
        for rel in manifest.installed_paths():
            with self.subTest(path=rel):
                self.assertTrue((self.target / rel).is_file(), rel)

    def test_paths_referenced_inside_installed_files_resolve(self):
        """The guard that catches a dangling reference whatever it is called.

        `settings.json` names the hook it wires by path. If the files land
        anywhere other than where that path points, the hook is inert and
        nothing says so.
        """
        manifest = adapter_manifests.load(ADAPTERS / "claude-code")
        checked, broken = 0, []
        for rel in manifest.installed_paths():
            text = (self.target / rel).read_text(encoding="utf-8")
            for ref in sorted(referenced_paths(text, manifest.install_root)):
                checked += 1
                if not (self.target / ref).exists():
                    broken.append(f"{rel} -> {ref}")
        self.assertGreater(
            checked, 0,
            "no internal path references were checked; this guard would pass "
            "vacuously",
        )
        self.assertEqual(broken, [], "\n".join(broken))

    def test_the_reference_check_can_fail(self):
        """Red before green: the extractor must find a real broken reference."""
        found = referenced_paths(
            'command": "python .claude/hooks/save_agent_reply.py"', ".claude"
        )
        self.assertEqual(found, {".claude/hooks/save_agent_reply.py"})
        self.assertFalse((self.target / ".claude/hooks/nope.py").exists())

    def test_the_adapter_contract_pointers_resolve_from_where_they_land(self):
        """A relative pointer is only correct at the depth it was installed to."""
        for role in ("brain", "worker", "verifier"):
            seat = self.target / ".claude" / "agents" / f"{role}.md"
            with self.subTest(role=role):
                targets = re.findall(
                    r"\]\((\.\./[^)\s]+)\)", seat.read_text(encoding="utf-8")
                )
                self.assertTrue(targets, f"{role}.md has no relative pointer")
                for rel in targets:
                    self.assertTrue(
                        (seat.parent / rel).resolve().is_file(),
                        f"{role}.md points at {rel}, which does not exist "
                        f"relative to where the seat was installed",
                    )


class TestSpecialistTopologyWithAnAdapter(unittest.TestCase):
    """`--workers decomper,scaffolder --adapter claude-code`.

    The decision, made explicitly and provider-neutrally: an adapter ships one
    seat per **role contract**. A project-declared specialist is the executor
    contract plus a scope statement, so it shares the `worker` seat and gets no
    file of its own. These guards stop the layout being described as offering a
    per-declared-role file it does not contain.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name)
        assert adopt_into(
            cls.target, "--adapter", "claude-code",
            "--workers", "decomper,scaffolder", "--verifier",
        ) == 0

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_generic_executor_seat_is_installed(self):
        seat = self.target / ".claude" / "agents" / "worker.md"
        self.assertTrue(seat.is_file())
        self.assertIn(
            "docs/agents/roles/worker.md", seat.read_text(encoding="utf-8")
        )

    def test_no_specialist_seat_file_is_invented(self):
        for role in ("decomper", "scaffolder"):
            with self.subTest(role=role):
                self.assertFalse(
                    (self.target / ".claude" / "agents" / f"{role}.md").exists(),
                    "a seat was generated for a specialist with no contract of "
                    "its own; it would point at a contract that does not exist",
                )

    def test_the_specialism_is_carried_by_scope_not_by_a_seat(self):
        agents = (self.target / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Decomper", agents)
        self.assertIn("Scaffolder", agents)

    def test_the_adopted_tree_still_passes_its_own_guard(self):
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=self.target, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


class TestAdoptionReportsWhatItInstalled(unittest.TestCase):
    """The plan must not imply a file per declared role when there is not one."""

    def _plan_notes(self, *extra: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            plan = adopt.build_plan(
                Path(tmp), project="P", coordinator="brain",
                workers=list(extra) or ["worker"], verifier=True,
                hooks=False, adapters=["claude-code"],
            )
            return plan.notes

    def test_the_declared_destination_is_reported(self):
        self.assertTrue(
            any(".claude/" in note for note in self._plan_notes()),
            "adoption must say where an adapter's files went",
        )

    def test_specialists_are_reported_as_sharing_the_executor_seat(self):
        notes = " ".join(self._plan_notes("decomper", "scaffolder"))
        self.assertIn("decomper", notes)
        self.assertIn("scaffolder", notes)
        self.assertIn("no seat file is generated", notes)

    def test_no_such_note_when_every_declared_role_has_a_seat(self):
        notes = " ".join(self._plan_notes("worker"))
        self.assertNotIn("no seat file is generated", notes)


if __name__ == "__main__":
    unittest.main()
