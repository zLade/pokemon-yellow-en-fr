#!/usr/bin/env python3
"""Focused mutation tests for the EN2 static catalogue gate."""

from __future__ import annotations

import unittest

from tools.validate_english_catalog import (
    BATTLE_LINE_BREAK_KEYS,
    EXPECTED_BATTLE_BOUNDARY_PAYLOADS,
    EXPECTED_FIXED_ITEM_NAME_PAYLOADS,
    EXPECTED_FIXED_GRID_7X3_KEYS,
    EnglishCatalogueError,
    validate_catalogue_rows,
    validate_variants,
)


def catalogue_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(1929):
        restored = index >= 1844
        if restored:
            layout = "dialogue_19_19"
            record_type = "RESTORED"
        elif index < 970:
            layout = "dialogue_19_19"
            record_type = "MAIN"
        elif index < 1129:
            layout = "pokedex_13x4"
            record_type = "MAIN"
        else:
            layout = ""
            record_type = "MAIN"
        rows.append(
            {
                "stable_key": f"{'RESTORED' if restored else 'MAIN'}:0x{index:06X}",
                "record_type": record_type,
                "layout": layout,
                "chinese_text": "中",
                "english_v2": "Test",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "source_resolution": "pointer_table",
                "review_status": "ai_source_reviewed",
                "encoded_length": "4" if layout != "pokedex_13x4" else "4",
                "compression": "no",
                "compression_justification": "",
            }
        )
    for index, key in enumerate(sorted(EXPECTED_FIXED_GRID_7X3_KEYS)):
        row = rows[1129 + index]
        row["stable_key"] = key
        row["layout"] = "fixed_grid_7x3"
    # Keep row 1200 free for the focused mutation tests below.
    candidates = iter(rows[1300:])
    for key, text in EXPECTED_FIXED_ITEM_NAME_PAYLOADS.items():
        row = next(candidates)
        row["stable_key"] = key
        row["english_v2"] = text
        row["encoded_length"] = str(len(text.encode("ascii", "replace")))
    candidates = iter(rows[1400:])
    for key in BATTLE_LINE_BREAK_KEYS:
        row = next(candidates)
        row["stable_key"] = key
        row["english_v2"] = EXPECTED_BATTLE_BOUNDARY_PAYLOADS.get(
            key, " \nSafe text"
        )
        row["encoded_length"] = str(len(row["english_v2"]))
    return rows


class ValidateEnglishCatalogTests(unittest.TestCase):
    def test_complete_synthetic_catalogue_passes(self) -> None:
        by_key, counts = validate_catalogue_rows(catalogue_rows())
        self.assertEqual(len(by_key), 1929)
        self.assertEqual(counts["restored"], 85)
        self.assertEqual(counts["dialogues"], 1055)
        self.assertEqual(counts["pokedex"], 159)
        self.assertEqual(counts["item_descriptions"], 31)

    def test_pending_codec_french_spacing_and_leak_are_fatal(self) -> None:
        mutations = (
            ("review_status", "pending", "pending review_status"),
            ("english_v2", "literal @", "codec/layout"),
            ("english_v2", "Hello !", "French punctuation"),
            ("english_v2", "SACHA", "French leakage"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field, value=value):
                rows = catalogue_rows()
                rows[0][field] = value
                with self.assertRaisesRegex(EnglishCatalogueError, message):
                    validate_catalogue_rows(rows)

    def test_pointer_variants_require_primary_main_payload_parity(self) -> None:
        catalogue = {
            "MAIN:0x0302FA": {"english_v2": " is badly poisoned"},
            "MAIN:0x03162C": {"english_v2": "Curse"},
            "MAIN:0x031A15": {"english_v2": "Catches Pokémon"},
        }
        rows = [
            {
                "variant_key": "v1",
                "stable_key": "MAIN:0x0302FA",
                "english_v2": " is badly poisoned",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
            {
                "variant_key": "v2",
                "stable_key": "MAIN:0x0302FA",
                "english_v2": " flinched",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
            {
                "variant_key": "v3",
                "stable_key": "MAIN:0x03162C",
                "english_v2": "Curse",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
            {
                "variant_key": "v4",
                "stable_key": "MAIN:0x03162C",
                "english_v2": "Strength",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
            {
                "variant_key": "v5",
                "stable_key": "MAIN:0x031A15",
                "english_v2": "Catches Pokémon",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
            {
                "variant_key": "v6",
                "stable_key": "MAIN:0x031A15",
                "english_v2": "Better Poké Ball",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
            {
                "variant_key": "v7",
                "stable_key": "MAIN:0x031A15",
                "english_v2": "Better Great Ball",
                "editorial_origin": "translated_directly_from_chinese_ai_review",
                "review_status": "ai_source_reviewed",
            },
        ]
        validate_variants(rows, catalogue)
        rows[0]["english_v2"] = "Poisoned"
        with self.assertRaisesRegex(EnglishCatalogueError, "primary variant"):
            validate_variants(rows, catalogue)

        rows[0]["english_v2"] = " is badly poisoned"
        rows[5]["english_v2"] = "X" * 22
        with self.assertRaisesRegex(EnglishCatalogueError, "fixed 7x3"):
            validate_variants(rows, catalogue)

    def test_english_combat_is_not_mistaken_for_french(self) -> None:
        rows = catalogue_rows()
        rows[0]["english_v2"] = "God of combat!"
        rows[0]["encoded_length"] = str(len("God of combat!"))
        validate_catalogue_rows(rows)

    def test_battle_boundary_payloads_are_exact(self) -> None:
        rows = catalogue_rows()
        row = rows[1200]
        row["stable_key"] = "MAIN:0x030634"
        row["english_v2"] = "Foe "
        row["encoded_length"] = "4"
        with self.assertRaisesRegex(
            EnglishCatalogueError,
            "battle boundary payload",
        ):
            validate_catalogue_rows(rows)

        row["english_v2"] = "Enemy "
        row["encoded_length"] = "6"
        validate_catalogue_rows(rows)

    def test_executable_context_payloads_are_exact(self) -> None:
        rows = catalogue_rows()
        row = rows[1200]
        row["stable_key"] = "MAIN:0x0349E5"
        row["english_v2"] = "Got PP Up!"
        row["encoded_length"] = str(len(row["english_v2"]))
        with self.assertRaisesRegex(
            EnglishCatalogueError, "executable-context payload"
        ):
            validate_catalogue_rows(rows)
        row["english_v2"] = "Got Ether!"
        row["encoded_length"] = str(len(row["english_v2"]))
        validate_catalogue_rows(rows)

    def test_fixed_item_description_grid_rejects_a_22nd_cell(self) -> None:
        rows = catalogue_rows()
        row = next(
            item for item in rows
            if item["stable_key"] == "MAIN:0x031A15"
        )
        row["english_v2"] = "X" * 22
        row["encoded_length"] = "22"
        with self.assertRaisesRegex(EnglishCatalogueError, "fixed 7x3"):
            validate_catalogue_rows(rows)
        row["english_v2"] = "X" * 21
        row["encoded_length"] = "21"
        validate_catalogue_rows(rows)

    def test_fixed_item_name_rejects_collision_with_quantity(self) -> None:
        rows = catalogue_rows()
        row = next(
            item for item in rows
            if item["stable_key"] == "MAIN:0x031710"
        )
        row["english_v2"] = "Super Potion"
        row["encoded_length"] = str(len(row["english_v2"]))
        with self.assertRaisesRegex(EnglishCatalogueError, "fixed item name"):
            validate_catalogue_rows(rows)

    def test_battle_line_break_gate_rejects_undeclared_or_long_rows(self) -> None:
        rows = catalogue_rows()
        row = rows[1200]
        row["english_v2"] = "Unexpected\nbreak"
        row["encoded_length"] = str(len(row["english_v2"]))
        with self.assertRaisesRegex(EnglishCatalogueError, "line-break topology"):
            validate_catalogue_rows(rows)

        rows = catalogue_rows()
        row = next(
            item for item in rows
            if item["stable_key"] == "MAIN:0x0307B9"
        )
        row["english_v2"] = "\n" + "X" * 26
        row["encoded_length"] = str(len(row["english_v2"]))
        with self.assertRaisesRegex(EnglishCatalogueError, "artifact-free maximum"):
            validate_catalogue_rows(rows)

    def test_bootleg_and_official_proper_nouns_are_source_driven(self) -> None:
        rows = catalogue_rows()
        row = rows[1200]
        row["chinese_text"] = "南晶队"
        row["english_v2"] = "Team Rocket"
        row["encoded_length"] = str(len("Team Rocket"))
        with self.assertRaisesRegex(EnglishCatalogueError, "Team Nanjing"):
            validate_catalogue_rows(rows)
        row["english_v2"] = "Team Nanjing"
        row["encoded_length"] = str(len("Team Nanjing"))
        validate_catalogue_rows(rows)

    def test_shared_battle_result_has_narrow_player_name_exception(self) -> None:
        rows = catalogue_rows()
        row = rows[1200]
        row["stable_key"] = "MAIN:0x035F3D"
        row["chinese_text"] = "小智作为奖金"
        row["english_v2"] = "Battle result: "
        row["encoded_length"] = str(len("Battle result: "))
        validate_catalogue_rows(rows)

        row["stable_key"] = "MAIN:0x035F3E"
        with self.assertRaisesRegex(EnglishCatalogueError, "requires 'Ash'"):
            validate_catalogue_rows(rows)


if __name__ == "__main__":
    unittest.main()
