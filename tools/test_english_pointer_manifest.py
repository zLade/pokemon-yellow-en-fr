#!/usr/bin/env python3
"""Tests for English pointer manifest catalogue ownership."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from tools.english_pointer_manifest import (
    EnglishPointerManifestError,
    expected_payload_for_reference,
    final_payload_for_reference,
    expected_payloads,
    validate_graphical_move_payload,
)


CATALOG_FIELDS = ("stable_key", "layout", "english_v2", "review_status")
VARIANT_FIELDS = (
    "variant_key",
    "stable_key",
    "pointer_reference_hex",
    "english_v2",
    "review_status",
)


class EnglishPointerManifestTests(unittest.TestCase):
    def _fixtures(self, root: Path) -> tuple[Path, Path]:
        catalogue = root / "catalog.csv"
        variants = root / "variants.csv"
        with catalogue.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CATALOG_FIELDS)
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "stable_key": "MAIN:0x0302FA",
                        "layout": "",
                        "english_v2": " is badly poisoned",
                        "review_status": "ai_source_reviewed",
                    },
                    {
                        "stable_key": "MAIN:0x031A15",
                        "layout": "",
                        "english_v2": "Catches Pokémon",
                        "review_status": "ai_source_reviewed",
                    },
                    {
                        "stable_key": "MAIN:0x0318F5",
                        "layout": "",
                        "english_v2": "Curse",
                        "review_status": "ai_source_reviewed",
                    },
                ]
            )
        with variants.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=VARIANT_FIELDS)
            writer.writeheader()
            writer.writerows(
                [
                    {"variant_key": "v1", "stable_key": "MAIN:0x0302FA", "pointer_reference_hex": "0x03006B", "english_v2": " is badly poisoned", "review_status": "ai_source_reviewed"},
                    {"variant_key": "v2", "stable_key": "MAIN:0x0302FA", "pointer_reference_hex": "0x03006D", "english_v2": " flinched", "review_status": "ai_source_reviewed"},
                    {"variant_key": "v3", "stable_key": "MAIN:0x031A15", "pointer_reference_hex": "0x031971", "english_v2": "Catches Pokémon", "review_status": "ai_source_reviewed"},
                    {"variant_key": "v4", "stable_key": "MAIN:0x031A15", "pointer_reference_hex": "0x031973", "english_v2": "Better Poké Ball", "review_status": "ai_source_reviewed"},
                    {"variant_key": "v5", "stable_key": "MAIN:0x031A15", "pointer_reference_hex": "0x031975", "english_v2": "Better Great Ball", "review_status": "ai_source_reviewed"},
                    {"variant_key": "v6", "stable_key": "MAIN:0x0318F5", "pointer_reference_hex": "0x0310F5", "english_v2": "Curse", "review_status": "ai_source_reviewed"},
                    {"variant_key": "v7", "stable_key": "MAIN:0x0318F5", "pointer_reference_hex": "0x0310F7", "english_v2": "Strength", "review_status": "ai_source_reviewed"},
                ]
            )
        return catalogue, variants

    def test_secondary_variant_map_contains_exactly_four_refs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalogue, variants = self._fixtures(Path(temporary))
            payloads, secondary = expected_payloads(catalogue, variants)
        self.assertEqual(
            secondary,
            {
                0x03006D: "v2",
                0x031973: "v4",
                0x031975: "v5",
                0x0310F7: "v7",
            },
        )
        self.assertEqual(payloads["v3"], b"Catches Pok@mon")

    def test_primary_variant_mismatch_is_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            catalogue, variants = self._fixtures(Path(temporary))
            text = variants.read_text(encoding="utf-8")
            variants.write_text(
                text.replace(" is badly poisoned", " Poisoned", 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                EnglishPointerManifestError, "primary variant"
            ):
                expected_payloads(catalogue, variants)

    def test_interior_and_padding_targets_compare_the_visible_suffix(self) -> None:
        payloads = {"MAIN:0x030000": b"0  Hello world"}
        prefix = {
            "kind": "translation",
            "reference": "0x030100",
            "source_row": "0x030000",
            "source_target": "0x030002",
        }
        interior = dict(prefix, source_target="0x030008")
        self.assertEqual(
            expected_payload_for_reference(
                stable_key="MAIN:0x030000",
                structural=prefix,
                payloads=payloads,
            ),
            b"Hello world",
        )
        self.assertEqual(
            expected_payload_for_reference(
                stable_key="MAIN:0x030000",
                structural=interior,
                payloads=payloads,
            ),
            b"Hello world",
        )

    def test_ascii_padding_collapse_preserves_join_space(self) -> None:
        structural = {
            "kind": "translation",
            "reference": "0x030085",
            "source_row": "0x0303BC",
            "source_target": "0x0303C2",
        }
        self.assertEqual(
            expected_payload_for_reference(
                stable_key="MAIN:0x0303BC",
                structural=structural,
                payloads={"MAIN:0x0303BC": b" fell!"},
            ),
            b" fell!",
        )

    def test_poison_primary_variant_preserves_join_space(self) -> None:
        structural = {
            "kind": "translation",
            "reference": "0x03006B",
            "source_row": "0x0302FA",
            "source_target": "0x0302FB",
        }
        self.assertEqual(
            expected_payload_for_reference(
                stable_key="MAIN:0x0302FA",
                structural=structural,
                payloads={"MAIN:0x0302FA": b" was badly poisoned!"},
            ),
            b" was badly poisoned!",
        )

    def test_reviewed_fixed_payload_is_bounded_before_zero_padding(self) -> None:
        rom = b"\0" * 10 + b"HELLO\0NEXT\r"
        self.assertEqual(
            final_payload_for_reference(
                rom=rom,
                reference=0x03CFBC,
                target=10,
                expected=b"HELLO",
            ),
            b"HELLO",
        )

    def test_graphical_move_payload_requires_complete_two_byte_codes(self) -> None:
        validate_graphical_move_payload(0x030F9B, bytes.fromhex("B0A1B0A3"))
        for malformed in (b"", bytes.fromhex("B0"), bytes.fromhex("A0A1"), bytes.fromhex("B0A0")):
            with self.subTest(malformed=malformed):
                with self.assertRaises(EnglishPointerManifestError):
                    validate_graphical_move_payload(0x030F9B, malformed)


if __name__ == "__main__":
    unittest.main()
