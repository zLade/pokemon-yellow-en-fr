#!/usr/bin/env python3
"""Reproducibility and atomic-publication tests for the release wrapper."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = TOOLS_DIR.parent
WRAPPER = TOOLS_DIR / "build_release.py"
ASSISTANT = ROOT / "rom_traduction_assistant.py"
SCRIPT = ROOT / "script.py"
TRANSLATION_BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
CANONICAL_CSV = ROOT / "traduction_base.csv"
CANONICAL_OVERFLOW = ROOT / "traductions_trop_longues.csv"

REPRODUCED_ARTIFACTS = (
    "Pokemon_Jaune_FR_repacked.nes",
    "Pokemon_Jaune_FR_repacked.ips",
    "Pokemon_Jaune_FR_repacked_title.nes",
    "Pokemon_Jaune_FR_repacked_title.ips",
    "textes_fixes_trop_longs.csv",
)

DETERMINISTIC_ARTIFACTS = (
    *REPRODUCED_ARTIFACTS,
    "Pokemon_Jaune_FR_repacked_title_from_chinese.bps",
    "Pokemon_Jaune_FR_repacked_title_from_english.bps",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CanonicalSourceTests(unittest.TestCase):
    def test_script_dump_is_the_checked_in_canonical_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            generated_csv = temporary_path / "traduction_base.csv"
            generated_overflow = (
                temporary_path / "traductions_trop_longues.csv"
            )
            process = subprocess.run(
                (
                    sys.executable,
                    str(ASSISTANT),
                    "dump-script",
                    "--script",
                    str(SCRIPT),
                    "--english-rom",
                    str(TRANSLATION_BASE),
                    "--output",
                    str(generated_csv),
                    "--overflow-output",
                    str(generated_overflow),
                ),
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout)
            self.assertEqual(generated_csv.read_bytes(), CANONICAL_CSV.read_bytes())
            self.assertEqual(
                generated_overflow.read_bytes(),
                CANONICAL_OVERFLOW.read_bytes(),
            )

    def test_stale_csv_never_publishes_a_partial_release(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            stale_csv = temporary_path / "stale.csv"
            stale_csv.write_bytes(CANONICAL_CSV.read_bytes() + b"\n")
            output = temporary_path / "release"
            process = subprocess.run(
                (
                    sys.executable,
                    str(WRAPPER),
                    "--output-dir",
                    str(output),
                    "--canonical-csv",
                    str(stale_csv),
                    "--canonical-overflow-csv",
                    str(CANONICAL_OVERFLOW),
                    "--skip-tests",
                ),
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertNotEqual(process.returncode, 0, process.stdout)
            self.assertFalse(output.exists())
            self.assertIn("SHA-256 canonical_csv inattendu", process.stdout)
            self.assertEqual(
                list(temporary_path.glob(".release.staging-*")), []
            )

    @unittest.skipIf(
        os.environ.get("POKEMON_RELEASE_ACTIVE") == "1",
        "le wrapper parent execute deja le double build",
    )
    def test_release_rebuilds_artifacts_in_a_tempdir(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "release"
            process = subprocess.run(
                (
                    sys.executable,
                    str(WRAPPER),
                    "--output-dir",
                    str(output),
                    "--skip-tests",
                ),
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            self.assertEqual(process.returncode, 0, process.stdout)

            for filename in DETERMINISTIC_ARTIFACTS:
                self.assertTrue((output / filename).is_file(), filename)

            manifest = json.loads(
                (output / "release_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(manifest["result"], "PASS")
            self.assertTrue(manifest["canonical_csv_regenerated"])
            self.assertTrue(manifest["double_build_deterministic"])
            self.assertFalse(manifest["current_artifacts_reproduced"])
            traced_sources = {
                record["path"]
                for label, record in manifest["inputs"].items()
                if label.startswith("tool_source:")
            }
            expected_sources = {
                str(path.relative_to(ROOT)).replace("\\", "/")
                for path in (ROOT / "tools").rglob("*")
                if path.is_file()
                and path.suffix.lower()
                in {".csv", ".json", ".lua", ".md", ".mjs", ".ps1", ".py"}
            }
            self.assertEqual(traced_sources, expected_sources)
            self.assertEqual(
                manifest["tool_source_count"], len(expected_sources)
            )
            self.assertIn("tools/build_release.py", traced_sources)
            self.assertIn(
                "tools/pokedex_description_table.py", traced_sources
            )
            traced_documentation = {
                record["path"]
                for label, record in manifest["inputs"].items()
                if label.startswith("project_documentation:")
            }
            expected_documentation = {
                path.name for path in ROOT.glob("*.md") if path.is_file()
            }
            self.assertEqual(
                traced_documentation,
                expected_documentation,
            )
            self.assertEqual(
                manifest["test_module_count"],
                len(list((ROOT / "tools").glob("test_*.py"))),
            )
            self.assertEqual(
                set(manifest["deterministic_artifacts"]),
                set(DETERMINISTIC_ARTIFACTS),
            )
            budget = json.loads(
                (output / "audits" / "text_bank_budget.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(budget["status"], "PASS")
            self.assertEqual(
                budget["release_policy"]["floors"]["6"],
                {"free_bytes": 40, "largest_block": 4},
            )
            self.assertEqual(
                budget["release_policy"]["pair6_capacity_proof"][
                    "theoretical_free_bytes"
                ],
                51,
            )
            self.assertEqual(
                budget["release_policy"]["pair6_capacity_proof"][
                    "maximum_possible_largest_block"
                ],
                11,
            )
            self.assertTrue(
                (output / "audits" / "pointer_manifest.json").is_file()
            )
            pointer_manifest = json.loads(
                (
                    output / "audits" / "pointer_manifest.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                pointer_manifest["schema"],
                "pokemon-yellow-nes-pointer-manifest/v2",
            )
            inventory_entries = [
                {
                    "kind": record.get("kind"),
                    "reference": record.get("reference"),
                    "source_row": record.get("source_row"),
                    "source_target": record.get("source_target"),
                    "provenance": record.get("provenance"),
                }
                for record in pointer_manifest["records"]
            ]
            inventory_payload = json.dumps(
                inventory_entries,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            self.assertEqual(
                pointer_manifest["canonical_inventory"],
                {
                    "derivation": (
                        "translation_csv_and_canonical_base_rom"
                    ),
                    "entries": len(inventory_entries),
                    "sha256": hashlib.sha256(
                        inventory_payload
                    ).hexdigest(),
                },
            )
            self.assertEqual(
                manifest["inputs"]["core_dialogue_boundary_inventory"][
                    "sha256"
                ],
                sha256_file(
                    ROOT / "tools/data/dialogue_boundary_inventory.json"
                ),
            )
            self.assertEqual(
                manifest["inputs"]["restoration_naturalization_overrides"][
                    "sha256"
                ],
                sha256_file(
                    ROOT
                    / "tools/data/french_restoration_naturalization_overrides.json"
                ),
            )
            self.assertEqual(
                manifest["inputs"]["main_naturalization_overrides"]["sha256"],
                sha256_file(
                    ROOT / "tools/data/french_naturalization_overrides.json"
                ),
            )
            self.assertEqual(
                manifest["inputs"]["chinese_fidelity_overrides"]["sha256"],
                sha256_file(
                    ROOT / "tools/data/chinese_fidelity_dialogue_overrides.json"
                ),
            )
            self.assertEqual(
                manifest["inputs"]["external_patcher_proof"]["sha256"],
                sha256_file(ROOT / "build/external-patcher-proof.json"),
            )
            self.assertEqual(
                sha256_file(output / "external-patcher-proof.json"),
                sha256_file(ROOT / "build/external-patcher-proof.json"),
            )

            checksum_path = output / "SHA256SUMS"
            checked_paths: set[str] = set()
            for line in checksum_path.read_text(encoding="utf-8").splitlines():
                expected, relative = line.split("  ", 1)
                checked_paths.add(relative)
                self.assertEqual(
                    sha256_file(output / relative), expected, relative
                )
            self.assertIn("release_manifest.json", checked_paths)
            self.assertIn(
                "Pokemon_Jaune_FR_repacked_title.nes", checked_paths
            )
            self.assertIn("external-patcher-proof.json", checked_paths)


if __name__ == "__main__":
    unittest.main()
