#!/usr/bin/env python3
"""Independent negative tests for the pointer-manifest validator."""

from __future__ import annotations

import hashlib
import copy
import tempfile
import unittest
from pathlib import Path

from tools.rom_builder import cpu_addr_for_offset, pair_for_offset
from tools.pointer_manifest import (
    SCHEMA,
    canonical_inventory_commitment,
    validate_manifest,
)


class PointerManifestTests(unittest.TestCase):
    def _fixture(self) -> tuple[Path, dict, tempfile.TemporaryDirectory]:
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name) / "fixture.nes"
        rom = bytearray(b"NES\x1a" + bytes(0x2000C))
        reference = 0x10010
        target = 0x10100
        payload = b"BONJOUR"
        rom[reference:reference + 2] = cpu_addr_for_offset(target).to_bytes(
            2,
            "little",
        )
        rom[target:target + len(payload) + 1] = payload + b"\x0D"
        path.write_bytes(rom)
        manifest = {
            "schema": SCHEMA,
            "inputs": {"final_rom_sha256": hashlib.sha256(rom).hexdigest()},
            "summary": {
                "pointer_records": 1,
                "unique_references": 1,
                "restorations": 0,
                "pointer_variants": 0,
                "by_provenance": {"detected": 1},
            },
            "records": [
                {
                    "kind": "translation",
                    "reference": f"0x{reference:06X}",
                    "source_row": "0x010100",
                    "source_target": f"0x{target:06X}",
                    "final_target": f"0x{target:06X}",
                    "pair": pair_for_offset(reference),
                    "cpu_address": f"0x{cpu_addr_for_offset(target):04X}",
                    "provenance": "detected",
                    "payload_length": len(payload),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                }
            ],
        }
        manifest["canonical_inventory"] = canonical_inventory_commitment(
            manifest["records"]
        )
        return path, manifest, temporary

    def test_valid_fixture_passes(self) -> None:
        path, manifest, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)
        self.assertEqual(validate_manifest(rom_path=path, manifest=manifest), [])

    def test_mutated_pointer_payload_and_manifest_are_rejected(self) -> None:
        path, manifest, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)
        original = bytearray(path.read_bytes())

        for offset in (0x10010, 0x10100, 0x10107):
            with self.subTest(offset=offset):
                mutated = bytearray(original)
                mutated[offset] ^= 1
                path.write_bytes(mutated)
                errors = validate_manifest(rom_path=path, manifest=manifest)
                self.assertTrue(errors)
        path.write_bytes(original)

        duplicate = {**manifest, "records": manifest["records"] * 2}
        duplicate["summary"] = {
            "pointer_records": 2,
            "unique_references": 2,
            "restorations": 0,
            "pointer_variants": 0,
            "by_provenance": {"detected": 2},
        }
        errors = validate_manifest(rom_path=path, manifest=duplicate)
        self.assertTrue(any("duplicate reference" in item for item in errors))

    def test_semantic_manifest_tampering_is_rejected(self) -> None:
        path, manifest, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)

        for field, value, expected in (
            ("kind", "unknown", "invalid kind"),
            ("provenance", "guessed", "invalid translation provenance"),
            ("payload_length", -1, "negative payload length"),
            ("source_row", None, "source_row is missing"),
        ):
            with self.subTest(field=field):
                changed = {
                    **manifest,
                    "records": [{**manifest["records"][0], field: value}],
                }
                errors = validate_manifest(rom_path=path, manifest=changed)
                self.assertTrue(any(expected in item for item in errors), errors)

    def test_removed_record_and_adjusted_summary_fail_canonical_inventory(self) -> None:
        path, manifest, temporary = self._fixture()
        self.addCleanup(temporary.cleanup)
        expected = copy.deepcopy(manifest)

        changed = copy.deepcopy(manifest)
        changed["records"] = []
        changed["summary"] = {
            "pointer_records": 0,
            "unique_references": 0,
            "restorations": 0,
            "pointer_variants": 0,
            "by_provenance": {},
        }
        # Model a deliberate line+summary edit, including recomputing the
        # self-consistency commitment.  Only the independent canonical
        # regeneration can now reveal the missing pointer.
        changed["canonical_inventory"] = canonical_inventory_commitment([])
        errors = validate_manifest(
            rom_path=path,
            manifest=changed,
            expected_manifest=expected,
        )
        self.assertTrue(
            any("inventory is incomplete" in item for item in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
