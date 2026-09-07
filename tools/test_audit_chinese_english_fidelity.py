#!/usr/bin/env python3
"""Regressions for the NJ046 Chinese text extractor."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    FINAL_ROM,
    TRANSLATION_BASE_ROM,
    find_structured_glyph_records,
)
from tools.chinese_dialogue_restorations import (  # noqa: E402
    COLLAPSED_ENGLISH_POINTER_REFERENCES,
    RESTORED_DIALOGUES,
)
from tools.audit_chinese_english_fidelity import (  # noqa: E402
    SOURCE_GLYPH_CODE_COUNT,
    SOURCE_PAYLOAD_SIZE,
    SOURCE_RECORD_COUNT,
    decode_source_record,
    decoded_pointer_target,
    dialogue_reference,
    pointer_index,
    source_glyph_bitmap,
)
from tools.dialogue_layout import (  # noqa: E402
    DIALOGUE_LAYOUT,
    format_game_text,
)


class ChineseEnglishFidelityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = (ROM_DIR / CHINESE_ROM).read_bytes()

    def test_source_inventory_fingerprint_counts(self) -> None:
        records = find_structured_glyph_records(self.rom)
        self.assertEqual(len(records), SOURCE_RECORD_COUNT)
        self.assertEqual(
            sum(record[3] for record in records),
            SOURCE_GLYPH_CODE_COUNT,
        )
        self.assertEqual(
            sum(end - start for start, end, _, _ in records),
            SOURCE_PAYLOAD_SIZE,
        )

    def test_even_and_odd_codes_select_distinct_bitplanes(self) -> None:
        even = source_glyph_bitmap(self.rom, 6)
        odd = source_glyph_bitmap(self.rom, 7)
        self.assertEqual(
            hashlib.sha256(even).hexdigest(),
            "6145406b055ad3783469e4e793cb52f6f"
            "472420549b749db1b756b850a545458",
        )
        self.assertEqual(
            hashlib.sha256(odd).hexdigest(),
            "4f10c6850f6f6b4c002afce6f827c8c"
            "48f0f8c4b46d5575adea69fc787fe5881",
        )
        self.assertNotEqual(even, odd)

    def test_copyright_record_decodes_as_sequential_characters(self) -> None:
        mapping = {
            6: "南",
            7: "晶",
            8: "公",
            9: "司",
            10: "版",
            11: "权",
            12: "所",
            13: "有",
        }
        text, unresolved = decode_source_record(
            self.rom,
            0x0301C4,
            0x0301D5,
            mapping,
        )
        self.assertEqual(text, "\n南晶公司版权所有")
        self.assertEqual(unresolved, ())

    def test_eighty_source_dialogue_pointers_are_restored_in_french(
        self,
    ) -> None:
        records = find_structured_glyph_records(self.rom)
        pointers = pointer_index(
            self.rom,
            (
                (start, end - start)
                for start, end, _, _ in records
            ),
        )
        english = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        french = (ROM_DIR / FINAL_ROM).read_bytes()
        invalid_english = [
            reference
            for reference in pointers
            if (
                dialogue_reference(reference)
                and decoded_pointer_target(english, reference) is None
            )
        ]
        self.assertEqual(len(invalid_english), 80)
        self.assertEqual(
            set(invalid_english),
            (
                set(RESTORED_DIALOGUES)
                - COLLAPSED_ENGLISH_POINTER_REFERENCES
                - {
                    0x038347,
                    0x03834B,
                    0x03834F,
                    0x038353,
                }
            ),
        )
        for reference in invalid_english:
            target = decoded_pointer_target(french, reference)
            self.assertIsNotNone(
                target,
                f"slot not restored: 0x{reference:06X}",
            )
            expected = format_game_text(
                RESTORED_DIALOGUES[reference],
                DIALOGUE_LAYOUT,
            )
            assert target is not None
            self.assertEqual(french[target:target + len(expected)], expected)
            self.assertEqual(french[target + len(expected)], 0x0D)

    def test_all_restored_dialogues_match_their_french_payload(self) -> None:
        french = (ROM_DIR / FINAL_ROM).read_bytes()
        self.assertEqual(len(RESTORED_DIALOGUES), 85)
        for reference, text in RESTORED_DIALOGUES.items():
            target = decoded_pointer_target(french, reference)
            self.assertIsNotNone(
                target,
                f"slot not restored: 0x{reference:06X}",
            )
            expected = format_game_text(text, DIALOGUE_LAYOUT)
            assert target is not None
            self.assertEqual(french[target:target + len(expected)], expected)
            self.assertEqual(french[target + len(expected)], 0x0D)


if __name__ == "__main__":
    unittest.main()
