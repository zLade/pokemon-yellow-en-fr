#!/usr/bin/env python3
"""Regressions for the independent French dynamic-fragment validator."""

from __future__ import annotations

import unittest

from rom_traduction_assistant import cpu_addr_for_offset
from tools.dialogue_layout import format_game_text
from tools.validate_french_dynamic_fragments import (
    BATTLE_ARTIFACT_FREE_CELLS,
    DEAD_UNREFERENCED_REFS,
    DYNAMIC_FRAGMENT_EXPECTATIONS,
    DYNAMIC_LAYOUT_CLASSIFIED_REFS,
    ITEM_LIST_NAME_EXPECTATIONS,
    ITEM_LIST_NAME_MAX_CELLS,
    SEMANTIC_POINTER_EXPECTATIONS,
    dynamic_layout_composed_max,
    maximum_live_composition_cells,
    validate_dynamic_layout_catalogue,
    validate_dynamic_fragments,
)


class FrenchDynamicFragmentTests(unittest.TestCase):
    def _fixture(self) -> bytearray:
        rom = bytearray(b"NES\x1A" + bytes(0x4000C))
        cursor = 0x036010
        expectations = {
            **DYNAMIC_FRAGMENT_EXPECTATIONS,
            **SEMANTIC_POINTER_EXPECTATIONS,
            **ITEM_LIST_NAME_EXPECTATIONS,
        }
        for reference, text in sorted(expectations.items()):
            payload = format_game_text(text)
            rom[reference:reference + 2] = cpu_addr_for_offset(
                cursor
            ).to_bytes(2, "little")
            rom[cursor:cursor + len(payload) + 1] = payload + b"\x0D"
            cursor += len(payload) + 1
        return rom

    def test_catalogue_is_complete_and_preserves_edge_spaces(self) -> None:
        self.assertEqual(len(DYNAMIC_FRAGMENT_EXPECTATIONS), 101)
        self.assertEqual(
            DYNAMIC_LAYOUT_CLASSIFIED_REFS,
            frozenset(DYNAMIC_FRAGMENT_EXPECTATIONS),
        )
        self.assertEqual(len(SEMANTIC_POINTER_EXPECTATIONS), 5)
        self.assertEqual(len(ITEM_LIST_NAME_EXPECTATIONS), 40)
        self.assertEqual(ITEM_LIST_NAME_MAX_CELLS, 7)
        self.assertEqual(
            tuple(ITEM_LIST_NAME_EXPECTATIONS),
            tuple(range(0x03164B, 0x03169A, 2)),
        )
        self.assertEqual(
            {
                reference: ITEM_LIST_NAME_EXPECTATIONS[reference]
                for reference in (
                    0x03164B,
                    0x03164D,
                    0x03164F,
                    0x031651,
                    0x031655,
                    0x03165B,
                    0x031685,
                )
            },
            {
                0x03164B: "PokéB.",
                0x03164D: "SuperB.",
                0x03164F: "HyperB.",
                0x031651: "MasterB",
                0x031655: "Sup.Pot",
                0x03165B: "Antid.",
                0x031685: "EauFr.",
            },
        )
        self.assertTrue(
            all(
                len(format_game_text(text)) <= ITEM_LIST_NAME_MAX_CELLS
                for text in ITEM_LIST_NAME_EXPECTATIONS.values()
            )
        )
        self.assertEqual(
            len(set(ITEM_LIST_NAME_EXPECTATIONS.values())),
            len(ITEM_LIST_NAME_EXPECTATIONS),
        )
        self.assertEqual(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x03006B],
            " est intoxiqué !",
        )
        self.assertEqual(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x03006D],
            " a peur !",
        )
        self.assertTrue(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300BB].startswith(" ")
        )
        self.assertFalse(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300BB].endswith(" ")
        )
        self.assertEqual(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x03004B],
            "Sacha a vaincu\n",
        )
        self.assertEqual(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x030173],
            "\nRésiste au poison !",
        )
        self.assertEqual(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x030135],
            "Statut inchangé !",
        )
        self.assertEqual(
            DYNAMIC_FRAGMENT_EXPECTATIONS[0x030099],
            "Bravo ! ",
        )
        self.assertEqual(
            (
                DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300A5],
                DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300A7],
            ),
            ("Mais il connaît", "déjà 4 attaques !"),
        )
        self.assertEqual(
            (
                DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300B1],
                DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300B3],
                DYNAMIC_FRAGMENT_EXPECTATIONS[0x0300B5],
            ),
            ("L'attaque ", "est oubliée !", "Attaque apprise :"),
        )
        self.assertEqual(
            {
                reference: DYNAMIC_FRAGMENT_EXPECTATIONS[reference]
                for reference in (
                    0x0300A1,
                    0x0300A3,
                    0x0300AB,
                    0x0300AD,
                    0x0300B9,
                )
            },
            {
                0x0300A1: " veut apprendre",
                0x0300A3: "...!",
                0x0300AB: "Oublier une attaque ?",
                0x0300AD: "Oui / Non",
                0x0300B9: " ?",
            },
        )

    def test_every_live_composition_is_artifact_free_at_worst_case(self) -> None:
        self.assertEqual(validate_dynamic_layout_catalogue(), [])
        composed = {
            reference: dynamic_layout_composed_max(reference)
            for reference in DYNAMIC_FRAGMENT_EXPECTATIONS
        }
        self.assertEqual(
            {reference for reference, width in composed.items() if width is None},
            DEAD_UNREFERENCED_REFS,
        )
        self.assertTrue(
            all(
                width is None or width <= BATTLE_ARTIFACT_FREE_CELLS
                for width in composed.values()
            )
        )
        self.assertEqual(composed[0x0300BB], 24)
        self.assertEqual(composed[0x0300CD], 24)
        self.assertEqual(composed[0x030099], 18)
        self.assertEqual(composed[0x0300A5], 17)
        self.assertEqual(composed[0x0300A7], 17)
        self.assertEqual(composed[0x0300B1], 20)
        self.assertEqual(composed[0x0300B3], 20)
        self.assertEqual(composed[0x0300B5], 17)
        self.assertEqual(composed[0x0300A1], 25)
        self.assertEqual(composed[0x0300A3], 14)
        self.assertEqual(composed[0x0300AB], 21)
        self.assertIsNone(composed[0x0300AD])
        self.assertEqual(composed[0x0300B9], 20)
        self.assertEqual(maximum_live_composition_cells(), 25)

    def test_exact_fixture_passes_and_a_lost_separator_fails(self) -> None:
        rom = self._fixture()
        self.assertEqual(validate_dynamic_fragments(bytes(rom)), [])

        reference = 0x03006F
        word = int.from_bytes(rom[reference:reference + 2], "little")
        target = 0x030010 + (word - 0x8000)
        self.assertEqual(rom[target], 0x20)
        rom[target] = ord("s")
        errors = validate_dynamic_fragments(bytes(rom))
        self.assertTrue(
            any("0x03006F" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
