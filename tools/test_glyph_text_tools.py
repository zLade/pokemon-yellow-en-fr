#!/usr/bin/env python3
"""Regressions for mapper-163 graphical-text parsing and font mapping."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    LEADING_SEPARATOR_POINTER_OFFSETS,
    STRUCTURED_GLYPH_PAIR_COUNT,
    STRUCTURED_GLYPH_PAYLOAD_SIZE,
    STRUCTURED_GLYPH_RECORD_COUNT,
    TRANSLATION_BASE_ROM,
    graphical_pointer_target_conflicts,
    relocated_text_target,
)
from tools.glyph_text_tools import (  # noqa: E402
    FONT_BASE_OFFSET,
    Raster,
    glyph_slot,
    records,
    slot_raster,
    validate_sources,
)


class GlyphTextToolsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.english = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        cls.chinese = (ROM_DIR / CHINESE_ROM).read_bytes()

    def test_canonical_font_patch_and_index_routine(self) -> None:
        validate_sources(self.english, self.chinese)

    def test_6502_slot_formula_examples(self) -> None:
        self.assertEqual(glyph_slot(0xB0, 0xC7), 38)
        self.assertEqual(glyph_slot(0xB5, 0x61), 662)
        self.assertEqual(glyph_slot(0xB1, 0x0D), 202)

    def test_inventory_and_low_byte_0d_boundary(self) -> None:
        inventory = records(self.english)
        self.assertEqual(len(inventory), STRUCTURED_GLYPH_RECORD_COUNT)
        self.assertEqual(
            sum(len(record.codes) for record in inventory),
            STRUCTURED_GLYPH_PAIR_COUNT,
        )
        self.assertEqual(
            sum(record.end - record.start for record in inventory),
            STRUCTURED_GLYPH_PAYLOAD_SIZE,
        )
        powder_snow = inventory[99]
        self.assertEqual(powder_snow.inventory_index, 100)
        self.assertEqual(powder_snow.start, 0x031231)
        self.assertEqual(powder_snow.end, 0x031237)
        self.assertIn(
            (0xB1, 0x0D),
            {(code.high, code.low) for code in powder_snow.codes},
        )

    def test_english_and_source_font_classification(self) -> None:
        inventory = records(self.english)
        fully_english = sum(
            all(code.english_graphic for code in record.codes)
            for record in inventory
        )
        mixed = sum(
            any(not code.english_graphic for code in record.codes)
            and any(code.english_graphic for code in record.codes)
            for record in inventory
        )
        source_occurrences = sum(
            not code.english_graphic
            for record in inventory
            for code in record.codes
        )

        self.assertEqual(fully_english, 246)
        self.assertEqual(mixed, 71)
        self.assertEqual(source_occurrences, 153)

    def test_bitplanes_are_rendered_separately_and_png_is_valid(self) -> None:
        data = bytearray(FONT_BASE_OFFSET + 32)
        data[FONT_BASE_OFFSET] = 0x80
        data[FONT_BASE_OFFSET + 8] = 0x40

        combined = slot_raster(bytes(data), 0, (0, 0, 0))
        plane_zero = slot_raster(bytes(data), 0, (0, 0, 0), 0)
        plane_one = slot_raster(bytes(data), 0, (0, 0, 0), 1)

        def inked(raster: Raster, x: int, y: int) -> bool:
            start = (y * raster.width + x) * 3
            return raster.pixels[start:start + 3] != b"\xFF\xFF\xFF"

        self.assertTrue(inked(combined, 0, 0))
        self.assertTrue(inked(combined, 1, 0))
        self.assertTrue(inked(plane_zero, 0, 0))
        self.assertFalse(inked(plane_zero, 1, 0))
        self.assertFalse(inked(plane_one, 0, 0))
        self.assertTrue(inked(plane_one, 1, 0))

        with tempfile.TemporaryDirectory(
            prefix="pokemon-glyph-png-"
        ) as temporary:
            output = Path(temporary) / "plane.png"
            combined.save_png(output)
            self.assertTrue(
                output.read_bytes().startswith(b"\x89PNG\r\n\x1A\n")
            )

    def test_relocated_pointer_drops_source_only_control_prefix(self) -> None:
        source = b"\0" * 10 + b"\x0AChinese"
        self.assertEqual(
            relocated_text_target(
                source,
                10,
                8,
                b"Francais",
                11,
                100,
            ),
            100,
        )
        self.assertEqual(
            relocated_text_target(
                source,
                10,
                8,
                b"Francais",
                10,
                100,
            ),
            100,
        )

    def test_relocated_pointer_preserves_explicit_translation_padding(self) -> None:
        source = b"\0" * 10 + b"0000Move"
        self.assertEqual(
            relocated_text_target(
                source,
                10,
                8,
                b"0000Attaque",
                14,
                100,
            ),
            104,
        )

    def test_graphical_interior_pointer_targets_translated_text_start(self) -> None:
        source = b"\0" * 10 + b"\xB0\xA1" * 80
        self.assertEqual(
            relocated_text_target(
                source,
                10,
                160,
                b"Texte francais",
                129,
                1000,
                collapse_graphical_interior=True,
            ),
            1000,
        )

    def test_battle_suffix_pointers_preserve_their_french_separator(self) -> None:
        self.assertTrue(
            {
                0x0301D7,
                0x03024E,
                0x030262,
                0x0306EC,
                0x0306F5,
            }.issubset(LEADING_SEPARATOR_POINTER_OFFSETS)
        )
        for source_offset in (0x0301D7, 0x03024E, 0x030262):
            source = b"\0" * source_offset + b"0English"
            self.assertEqual(
                relocated_text_target(
                    source,
                    source_offset,
                    len(b"0English"),
                    b" suffixe",
                    source_offset + 1,
                    100,
                ),
                100,
            )

        for source_offset in (0x0306EC, 0x0306F5):
            graphical_source = (
                b"\0" * source_offset + b"\x0A\xB0\xA1"
            )
            self.assertEqual(
                relocated_text_target(
                    graphical_source,
                    source_offset,
                    len(b"\x0A\xB0\xA1"),
                    b" suffixe",
                    source_offset + 1,
                    100,
                    collapse_graphical_interior=True,
                ),
                100,
            )

    def test_distinct_live_targets_in_one_graphic_are_rejected(self) -> None:
        refs = {
            100: [(112, [10]), (112, [20])],
            200: [(208, [30]), (216, [40])],
        }
        self.assertEqual(
            graphical_pointer_target_conflicts(refs, {100}),
            [],
        )
        conflicts = graphical_pointer_target_conflicts(refs, {100, 200})
        self.assertEqual(len(conflicts), 1)
        self.assertIn("0x0000C8", conflicts[0])
        self.assertIn("0x0000D0", conflicts[0])
        self.assertIn("0x0000D8", conflicts[0])


if __name__ == "__main__":
    unittest.main()
