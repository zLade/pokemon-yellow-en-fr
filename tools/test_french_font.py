#!/usr/bin/env python3
"""Regressions for the French one-byte charset and editable font patch."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
import unicodedata
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    TRANSLATION_BASE_ROM,
    parse_patch_entries,
)
from tools.audit_translation_coverage import (  # noqa: E402
    REVIEWED_ASCII_REMAINDERS,
)
from tools.french_font import (  # noqa: E402
    ASCII_FONT_OFFSET,
    ASCII_FONT_SIZE,
    FRENCH_CHAR_MAP,
    FRENCH_GLYPH_LABELS,
    FRENCH_NATIVE_GLYPH_CODES,
    FRENCH_PATCHED_ASCII_CODES,
    REPURPOSED_ASCII_CODES,
    decode_game_text,
    encode_game_text,
    export_font_pair,
    extract_ascii_font,
    french_font_tiles,
    literal_slot_conflicts,
    patch_french_font,
)


class FrenchFontTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        cls.font = extract_ascii_font(cls.base)

    def test_canonical_french_variants_have_distinct_one_byte_codes(
        self,
    ) -> None:
        encoded = encode_game_text(
            "À Â É Î Ç à â ç è é ê î ï ô ù û"
        )
        self.assertEqual(
            encoded,
            b'" # * < ; { ~ [ | @ } \\ ] ^ _ `',
        )
        accent_codes = encoded[::2]
        self.assertEqual(len(accent_codes), 16)
        self.assertEqual(len(set(accent_codes)), 16)
        self.assertEqual(set(accent_codes), FRENCH_NATIVE_GLYPH_CODES)

    def test_semantic_decoder_restores_french_glyphs(self) -> None:
        self.assertEqual(
            decode_game_text(
                b'" # * < ; { ~ [ | @ } \\ ] ^ _ `'
            ),
            "À Â É Î Ç à â ç è é ê î ï ô ù û",
        )

    def test_every_mapped_single_byte_has_a_generated_tile(self) -> None:
        tiles = french_font_tiles(self.font)
        self.assertEqual(set(tiles), FRENCH_PATCHED_ASCII_CODES)
        self.assertEqual(
            REPURPOSED_ASCII_CODES,
            {
                ord(value)
                for value in FRENCH_CHAR_MAP.values()
                if len(value) == 1
            },
        )
        self.assertEqual(
            REPURPOSED_ASCII_CODES,
            FRENCH_PATCHED_ASCII_CODES | {ord("@")},
        )
        self.assertTrue(all(len(tile) == 16 for tile in tiles.values()))
        self.assertTrue(all(tile[8:] == b"\0" * 8 for tile in tiles.values()))

    def test_uppercase_glyphs_are_not_lowercase_aliases(self) -> None:
        tiles = french_font_tiles(self.font)
        lower_e_acute = self.font[
            (ord("@") - 0x20) * 16 : (ord("@") - 0x20 + 1) * 16
        ]
        self.assertNotEqual(tiles[ord("*")], lower_e_acute)
        self.assertNotEqual(tiles[ord('"')], tiles[ord("{")])
        self.assertNotEqual(tiles[ord("#")], tiles[ord("~")])
        self.assertNotEqual(tiles[ord(";")], tiles[ord("[")])
        self.assertNotEqual(tiles[ord("<")], tiles[ord("\\")])

    def test_patch_changes_only_declared_font_tiles(self) -> None:
        rom = bytearray(self.base)
        before = bytes(rom)
        tiles = patch_french_font(rom)
        changed = {
            offset
            for offset, (left, right) in enumerate(zip(before, rom))
            if left != right
        }
        allowed = {
            ASCII_FONT_OFFSET + (code - 0x20) * 16 + index
            for code in tiles
            for index in range(16)
        }
        self.assertTrue(changed)
        self.assertTrue(changed <= allowed)
        self.assertEqual(len(changed), 115)
        self.assertEqual(
            bytes(rom[ASCII_FONT_OFFSET : ASCII_FONT_OFFSET + ASCII_FONT_SIZE]),
            extract_ascii_font(bytes(rom)),
        )

    def test_ligatures_fall_back_without_question_mark(self) -> None:
        self.assertEqual(encode_game_text("cœur Œuf"), b"coeur OEuf")
        self.assertNotIn(b"?", encode_game_text("cœur Œuf"))

    def test_unmapped_diacritic_still_has_ascii_fallback(self) -> None:
        self.assertEqual(encode_game_text("ë"), b"e")

    def test_unsupported_unicode_is_rejected_instead_of_replaced(self) -> None:
        unsupported = {
            "curly apostrophe": "l’été",
            "opening guillemet": "«texte",
            "closing guillemet": "texte»",
            "opening English quotation mark": "“texte",
            "closing English quotation mark": "texte”",
            "em dash": "avant—après",
            "nonbreaking space": "avant\u00a0après",
            "emoji": "Pikachu ⚡",
        }
        for label, source in unsupported.items():
            with self.subTest(label=label, source=source):
                with self.assertRaises(UnicodeEncodeError):
                    encode_game_text(source)

    def test_complete_canonical_corpus_is_unchanged_by_strict_encoding(
        self,
    ) -> None:
        """The strict codec must not alter any currently reviewed dialogue."""

        def legacy_lossy_encoding(text: str) -> bytes:
            mapped = "".join(
                FRENCH_CHAR_MAP.get(character, character)
                for character in text
            )
            normalized = unicodedata.normalize("NFKD", mapped)
            ascii_text = "".join(
                character
                for character in normalized
                if not unicodedata.combining(character)
            )
            return ascii_text.encode("ascii", errors="replace")

        failures: list[str] = []
        for entry in parse_patch_entries():
            try:
                actual = encode_game_text(entry.text)
            except UnicodeEncodeError as exc:
                failures.append(f"0x{entry.offset:06X}: {exc}")
                continue
            expected = legacy_lossy_encoding(entry.text)
            if actual != expected:
                failures.append(
                    f"0x{entry.offset:06X}: {actual!r} != {expected!r}"
                )
        self.assertEqual(failures, [])

    def test_literal_repurposed_punctuation_is_detected(self) -> None:
        literal_slots = '"#*;<[\\]^_`{|}~@'
        self.assertEqual(
            literal_slot_conflicts(literal_slots),
            set(literal_slots),
        )
        self.assertEqual(literal_slot_conflicts("Texte français"), set())

    def test_player_name_ascii_letters_remain_unchanged(self) -> None:
        names = "MAX XAVIER xyz"
        self.assertEqual(encode_game_text(names), names.encode("ascii"))
        self.assertEqual(literal_slot_conflicts(names), set())
        self.assertTrue(
            all(
                not chr(code).isalpha()
                for code in FRENCH_PATCHED_ASCII_CODES
            )
        )

    def test_canonical_corpus_uses_only_native_non_ascii_letters(self) -> None:
        failures: list[str] = []
        conflicts: list[str] = []
        for entry in parse_patch_entries():
            literal_conflicts = literal_slot_conflicts(entry.text)
            if literal_conflicts:
                conflicts.append(
                    f"0x{entry.offset:06X}: "
                    + "".join(sorted(literal_conflicts))
                )
            for character in set(entry.text):
                if ord(character) < 0x80 or not character.isalpha():
                    continue
                encoded = encode_game_text(character)
                if character in {"œ", "Œ"}:
                    expected_fallback = {
                        "œ": b"oe",
                        "Œ": b"OE",
                    }[character]
                    if encoded != expected_fallback:
                        failures.append(
                            f"0x{entry.offset:06X}: {character!r} -> "
                            f"{encoded!r}"
                        )
                    continue
                if (
                    len(encoded) != 1
                    or encoded[0] not in FRENCH_NATIVE_GLYPH_CODES
                    or decode_game_text(encoded) != character
                ):
                    failures.append(
                        f"0x{entry.offset:06X}: {character!r} -> "
                        f"{encoded!r}"
                    )
        self.assertEqual(conflicts, [])
        self.assertEqual(failures, [])

    def test_invariant_runtime_ascii_does_not_use_repurposed_slots(
        self,
    ) -> None:
        conflicts = {
            offset: {
                character
                for character in text
                if ord(character) in FRENCH_PATCHED_ASCII_CODES
            }
            for offset, (text, _, _) in REVIEWED_ASCII_REMAINDERS.items()
            if any(
                ord(character) in FRENCH_PATCHED_ASCII_CODES
                for character in text
            )
        }
        self.assertEqual(conflicts, {})

    def test_export_contains_editable_fonts_tiles_and_previews(self) -> None:
        patched = bytearray(self.base)
        patch_french_font(patched)
        with tempfile.TemporaryDirectory(
            prefix="pokemon-french-font-export-"
        ) as temporary:
            output = Path(temporary)
            before, after = export_font_pair(
                self.base,
                bytes(patched),
                output,
            )
            self.assertEqual(before.stat().st_size, ASCII_FONT_SIZE)
            self.assertEqual(after.stat().st_size, ASCII_FONT_SIZE)
            self.assertEqual(
                (output / "glyphs" / "french_glyphs_3tiles.chr").stat().st_size,
                48,
            )
            self.assertEqual(
                (
                    output
                    / "glyphs"
                    / "french_glyphs_patched_15tiles.chr"
                ).stat().st_size,
                15 * 16,
            )
            self.assertEqual(
                (
                    output
                    / "glyphs"
                    / "french_glyphs_all_16tiles.chr"
                ).stat().st_size,
                16 * 16,
            )
            manifest = output / "glyphs" / "glyph_tiles_manifest.csv"
            with manifest.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 16)
            self.assertEqual(
                {int(row["ascii_code"], 16) for row in rows},
                FRENCH_NATIVE_GLYPH_CODES,
            )
            row_by_code = {
                int(row["ascii_code"], 16): row for row in rows
            }
            self.assertEqual(row_by_code[ord('"')]["source_slot"], '"')
            self.assertEqual(
                row_by_code[ord("@")]["patched_by_french_build"],
                "false",
            )
            self.assertEqual(
                row_by_code[ord("*")]["french_character"],
                "É",
            )
            for code, (label, _) in FRENCH_GLYPH_LABELS.items():
                self.assertEqual(
                    (
                        output
                        / "glyphs"
                        / f"glyph_{code:02X}_{label}.chr"
                    ).stat().st_size,
                    16,
                )
            self.assertTrue(
                (output / "ui_ascii_font_french_sheet.bmp").is_file()
            )
            self.assertTrue(
                (
                    output
                    / "glyphs"
                    / "french_glyphs_3tiles_sheet.bmp"
                ).is_file()
            )
            self.assertTrue(
                (
                    output
                    / "glyphs"
                    / "french_glyphs_patched_15tiles_sheet.bmp"
                ).is_file()
            )
            self.assertTrue(
                (
                    output
                    / "glyphs"
                    / "french_glyphs_all_16tiles_sheet.bmp"
                ).is_file()
            )
