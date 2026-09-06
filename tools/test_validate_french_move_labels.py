#!/usr/bin/env python3
"""Strict validation tests for the reviewed French two-line move labels."""

from __future__ import annotations

import unittest
from pathlib import Path

from rom_traduction_assistant import verified_dialogue_restoration_payloads
from tools.move_label_graphics import read_move_records
from tools.validate_mapper163 import (
    MoveLabelCertificationError,
    PAIR8_END,
    certify_move_label_graphics,
)
from tools.validate_repacked import (
    EXPECTED_FRENCH_MOVE_LABEL_COUNT,
    apply_expected_move_label_graphics,
    build_parser,
    compute_plan,
    load_french_move_label_specs,
    reconstruct_expected_text_banks,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
CATALOGUE = ROOT / "locales" / "fr-FR" / "move_labels_two_line.csv"
TRANSLATIONS = ROOT / "traduction_base.csv"


@unittest.skipUnless(
    BASE.is_file() and CATALOGUE.is_file() and TRANSLATIONS.is_file(),
    "French release inputs absent",
)
class FrenchMoveLabelValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        args = build_parser().parse_args(
            [
                "--csv",
                str(TRANSLATIONS),
                "--input-rom",
                str(BASE),
                "--move-labels-csv",
                str(CATALOGUE),
            ]
        )
        (
            original,
            row_info,
            row_pointer_refs,
            allocations,
            failures,
            _free_spans,
            _unsafe,
        ) = compute_plan(args)
        if failures:
            raise AssertionError(f"unexpected allocation failures: {failures}")
        catalogue, specs = load_french_move_label_specs(args)
        expected_text, errors = reconstruct_expected_text_banks(
            original,
            row_info,
            row_pointer_refs,
            verified_dialogue_restoration_payloads(original),
            allocations,
        )
        if errors:
            raise AssertionError(f"unexpected reconstruction errors: {errors}")
        result = apply_expected_move_label_graphics(
            original,
            expected_text,
            specs,
        )
        cls.original = original
        cls.candidate = result.rom
        cls.catalogue = catalogue
        first_index = specs[0].move_index
        cls.first_graphical_target = read_move_records(result.rom)[
            first_index
        ].target

    def test_reviewed_94_payloads_and_pair8_cells_are_certified(self) -> None:
        report = certify_move_label_graphics(
            base=self.original,
            candidate=self.candidate,
            profile="fr-FR",
            catalogue=self.catalogue,
        )
        self.assertEqual(
            report.requested_count,
            EXPECTED_FRENCH_MOVE_LABEL_COUNT,
        )
        self.assertEqual(len(report.used_even_slots), 304)
        self.assertTrue(report.changed_pair8_offsets)
        self.assertLessEqual(
            report.changed_pair8_offsets,
            report.allowed_pair8_offsets,
        )

    def test_unreviewed_pair8_byte_is_rejected(self) -> None:
        damaged = bytearray(self.candidate)
        damaged[PAIR8_END - 1] ^= 0x01
        with self.assertRaisesRegex(
            MoveLabelCertificationError,
            "hors cellules d'attaques certifiées",
        ):
            certify_move_label_graphics(
                base=self.original,
                candidate=bytes(damaged),
                profile="fr-FR",
                catalogue=self.catalogue,
            )

    def test_damaged_live_graphical_payload_is_rejected(self) -> None:
        damaged = bytearray(self.candidate)
        damaged[self.first_graphical_target] ^= 0x01
        with self.assertRaisesRegex(
            MoveLabelCertificationError,
            "non idempotents",
        ):
            certify_move_label_graphics(
                base=self.original,
                candidate=bytes(damaged),
                profile="fr-FR",
                catalogue=self.catalogue,
            )


if __name__ == "__main__":
    unittest.main()
