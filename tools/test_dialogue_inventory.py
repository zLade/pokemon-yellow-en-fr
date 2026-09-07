#!/usr/bin/env python3
"""Integrity and stale-source regressions for the dialogue inventory."""

from __future__ import annotations

import unittest

from tools.dialogue_inventory import (
    INVENTORY_DIALOGUE_RECORD_COUNT,
    INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT,
    INVENTORY_POKEDEX_RECORD_COUNT,
    load_dialogue_inventory,
    load_pokedex_inventory,
    reviewed_dialogue_override,
    reviewed_pokedex_override,
)


class DialogueInventoryTests(unittest.TestCase):
    def test_pinned_inventory_is_complete(self) -> None:
        records = load_dialogue_inventory()
        self.assertEqual(len(records), INVENTORY_DIALOGUE_RECORD_COUNT)
        self.assertEqual(
            sum(len(item["faulty_boundaries"]) for item in records.values()),
            814,
        )
        self.assertEqual(
            sum(
                len(item["legitimate_boundaries"])
                for item in records.values()
            ),
            29,
        )

    def test_exact_source_returns_semantic_proposal(self) -> None:
        record = load_dialogue_inventory()[0x0333FF]
        semantic = reviewed_dialogue_override(
            0x0333FF,
            record["source_fr_text"],
        )
        self.assertEqual(semantic, record["semantic_text_proposed"])

    def test_stale_source_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "diverged"):
            reviewed_dialogue_override(0x0333FF, "Texte changé")

    def test_unlisted_offset_has_no_override(self) -> None:
        self.assertIsNone(
            reviewed_dialogue_override(0x0301D7, "Apparaît !")
        )

    def test_reviewed_semantic_spacing_regressions(self) -> None:
        records = load_dialogue_inventory()
        expected_fragments = {
            0x033A48: "tu ne seras jamais Champion",
            0x033D67: "Roc Nombri. Tu peux",
            0x034739: "Tu as gagné le respect de ce Pokémon.",
            0x0387F3: "tu peux lui donner? Merci.",
            0x0389B4: "Sacha, pas besoin de carte!",
            0x038B03: "Oublie ça, tu n'as",
            0x038BBC: "Dresseurs coriaces. Je dois",
            0x038EFE: "preuve de ta victoire",
            0x03A821: "un meilleur dresseur",
            0x03C21F: "s'est apaisée et elle est partie",
            0x03C370: "esprit est en paix. Merci.",
            0x03CA26: "Sacha! Les Pokémon",
            0x03E8A0: "planque! Je comptais",
            0x03F27B: "PROF CHEN, à côté",
        }
        for offset, fragment in expected_fragments.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertIn(
                    fragment,
                    records[offset]["semantic_text_proposed"],
                )

    def test_pokedex_inventory_is_complete(self) -> None:
        records = load_pokedex_inventory()
        self.assertEqual(len(records), INVENTORY_POKEDEX_RECORD_COUNT)
        self.assertEqual(
            sum(
                len(item["artificial_hyphenations"])
                for item in records.values()
            ),
            INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT,
        )

    def test_exact_pokedex_source_returns_complete_reformulation(
        self,
    ) -> None:
        record = load_pokedex_inventory()[0x03247F]
        semantic = reviewed_pokedex_override(
            0x03247F,
            record["source_fr_text"],
        )
        self.assertEqual(
            semantic,
            "Sa queue brise les os de ses proies.",
        )

    def test_stale_pokedex_source_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "diverged"):
            reviewed_pokedex_override(0x03247F, "Texte changé")


if __name__ == "__main__":
    unittest.main()
