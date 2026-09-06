#!/usr/bin/env python3
"""Mutation tests for the inherited Route 1 uninitialized-read proof."""

from __future__ import annotations

import unittest
import os
from pathlib import Path

from tools.verify_mesen_route1_uninitialized import (
    CLASSIFICATION,
    ROM_SPECS,
    ROUTINE_FILE_OFFSET,
    ROOT,
    build_report,
    validate_routine_payloads,
    validate_stdout,
)


class Route1UninitializedDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stdout = (
            ROOT
            / "build/runtime-proof-final-1fefecbf-uninitialized-dendy/mesen.stdout.txt"
        ).read_text(encoding="utf-8-sig")
        cls.roms = {
            label: ((ROOT / relative).read_bytes(), expected_hash)
            for label, (relative, expected_hash) in ROM_SPECS.items()
        }

    def test_real_diagnostic_is_explicitly_unresolved_and_passes(self) -> None:
        if os.environ.get("POKEMON_VERIFY_FR_200_ARCHIVE") != "1":
            self.skipTest("diagnostic historique lié à la ROM FR 2.0.0")
        report = build_report(ROOT)
        self.assertEqual(report["result"], "PASS", report["errors"])
        self.assertEqual(report["classification"], CLASSIFICATION)
        self.assertFalse(
            report["claims"][
                "offending_routine_introduced_by_french_translation"
            ]
        )
        self.assertFalse(
            report["claims"]["translation_trigger_regression_excluded"]
        )
        self.assertFalse(report["claims"]["harmlessness_proven"])
        self.assertTrue(report["qualification"]["actual_cpu_reads"])
        self.assertFalse(report["qualification"]["probe_generated_reads"])

    def test_routine_byte_mutation_in_each_rom_is_rejected(self) -> None:
        for label in self.roms:
            mutated = dict(self.roms)
            payload, expected_hash = mutated[label]
            changed = bytearray(payload)
            changed[ROUTINE_FILE_OFFSET + 17] ^= 0x01
            mutated[label] = (bytes(changed), expected_hash)
            _records, errors = validate_routine_payloads(mutated)
            with self.subTest(label=label):
                self.assertTrue(errors)
                self.assertTrue(any(label in error for error in errors))

    def test_runtime_pc_frame_and_memory_type_mutations_are_rejected(self) -> None:
        mutations = (
            ("pc=$689C", "pc=$689D"),
            ("absolute_frame=13142", "absolute_frame=13143"),
            ("mapped_type=nesSaveRam", "mapped_type=nesPrgRom"),
            ("source_pointer=$0105", "source_pointer=$0106"),
        )
        for old, new in mutations:
            _record, errors = validate_stdout(self.stdout.replace(old, new, 1))
            with self.subTest(old=old, new=new):
                self.assertTrue(errors)

    def test_missing_or_extended_warning_range_is_rejected(self) -> None:
        missing = self.stdout.replace(
            "[CPU] Uninitialized memory read: $0161\n", "", 1
        )
        _record, errors = validate_stdout(missing)
        self.assertTrue(errors)

        extended = self.stdout.replace(
            "[CPU] Uninitialized memory read: $01C6\n",
            "[CPU] Uninitialized memory read: $01C6\n"
            "[CPU] Uninitialized memory read: $01C7\n",
            1,
        )
        _record, errors = validate_stdout(extended)
        self.assertTrue(errors)

    def test_terminal_scope_mutation_is_rejected(self) -> None:
        mutated = self.stdout.replace(
            "parcel_route_done=false", "parcel_route_done=true", 1
        )
        _record, errors = validate_stdout(mutated)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
