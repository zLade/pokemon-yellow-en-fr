#!/usr/bin/env python3
"""Regressions for the first player-visible field dialogues."""

from __future__ import annotations

import unittest

from rom_traduction_assistant import PATCH_SCRIPT, parse_patch_entries
from tools.dialogue_layout import wrap_dialogue_lines
from tools.french_font import decode_game_text


EXPECTED_PAGES = {
    0x03F27B: (
        "MAMAN : C'est vrai.",
        "Tous les garçons",
        "partent un jour.",
        "La télé l'a dit !",
        "Le Prof te cherche.",
        "Il est à côté.",
    ),
    0x038519: (
        "PROF. CHEN :",
        "Ne sors pas !",
        "Des Pokémon rôdent",
        "dans les herbes.",
        "Il t'en faut un.",
        "Suis-moi !",
    ),
    0x03F2EE: (
        "PROF. CHEN :",
        "Régis ? Déjà là ?",
        "Je t'avais dit",
        "d'attendre. Sacha,",
        "cette Poké Ball",
        "contient",
        "ton Pokémon.",
        "Prends-la !",
    ),
}


class EarlyDialogueReadabilityTests(unittest.TestCase):
    def test_first_field_dialogues_have_reviewed_pages(self) -> None:
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(PATCH_SCRIPT)
        }
        for offset, expected_pages in EXPECTED_PAGES.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                entry = entries[offset]
                actual_pages = tuple(
                    decode_game_text(line).rstrip()
                    for line in wrap_dialogue_lines(
                        entry.text,
                        entry.layout,
                    )
                )
                self.assertEqual(actual_pages, expected_pages)

    def test_reviewed_pages_fit_the_real_one_line_renderer(self) -> None:
        for offset, pages in EXPECTED_PAGES.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertTrue(pages)
                self.assertTrue(all(1 <= len(page) <= 19 for page in pages))


if __name__ == "__main__":
    unittest.main()
