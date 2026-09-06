#!/usr/bin/env python3
"""Regressions for the reviewed non-Pokédex translation corrections."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rom_traduction_assistant import parse_patch_entries
from tools.dialogue_layout import DIALOGUE_LAYOUT, format_game_text


CHINESE_FIDELITY_TEXTS = {
    int(offset, 0): text
    for offset, text in json.loads(
        (
            Path(__file__).resolve().parent
            / "data"
            / "chinese_fidelity_dialogue_overrides.json"
        ).read_text(encoding="utf-8")
    ).items()
}

FRENCH_NATURALIZATION_TEXTS = {
    int(offset, 0): text
    for offset, text in json.loads(
        (
            Path(__file__).resolve().parent
            / "data"
            / "french_naturalization_overrides.json"
        ).read_text(encoding="utf-8")
    ).items()
}


EXPECTED_TEXTS = {
    0x03043F: "000000Déjà 4 attaques!",
    0x0306C9: "PV restaurés !",
    0x030955: "00000000000000000PV restaurés !",
    0x035154: "Ces misérables Rockets ! Ils ont volé notre CT Tunnel !",
    0x0353F0: "Ils ont dû viser Sylphe SARL pour leurs produits Pokémon.",
    0x037BEF: (
        "La grotte est très sombre. Un Pokémon pourrait l'éclairer."
    ),
    0x038D9F: "Pierre cherche des Dresseurs à affronter.",
    0x038DBF: (
        "Hé, Champion ! Un conseil : Pierre utilise des Pokémon Roche. "
        "Les attaques Électrik sont inefficaces contre eux !"
    ),
    0x038EFE: (
        "Je t'ai sous-estimé ! Comme preuve de ta victoire, voici le "
        "Badge Roche !"
    ),
    0x038F91: (
        "Elle contient Armure. Ça augmente la Défense de ton Pokémon."
    ),
    0x0393B1: (
        "La Team Rocket, c'est nous ! Des gangsters Pokémon !"
    ),
    0x039698: "James : Rends-toi ou prépare-toi à combattre !",
    0x039770: (
        "Ces gens ont été volés. On pense que c'est la Team Rocket ! "
        "Même notre police ne peut rien faire !"
    ),
    0x039D4E: "Tu es incroyable !",
    0x03A433: "Hé, matelot ! Battons-nous !",
    0x03A62F: (
        "Ouf ! Merci ! Tiens, je te donne la CS Coupe ! Ton Pokémon "
        "peut l'utiliser hors combat pour couper des arbres ! "
        "CS01 obtenue !"
    ),
    0x03B390: (
        "Cette ville est connue comme le cimetière des Pokémon."
    ),
    0x03B4B9: (
        "Pourquoi t'es là, Sacha ? Tes Pokémon vont bien ! Mais je "
        "peux au moins les mettre K.O. ! Allons-y !"
    ),
    0x03B687: "On a l'air bêtes, debout là comme ça.",
    0x03BD1A: "Les Pokémon capturés ont des numéros.",
    0x03BFF8: "Ouf ! Je suis libre !",
    0x03C1B2: "J'étais contrôlé par des esprits.",
    0x03C28D: (
        "Jessie : Stop ! Miaouss : Le papi voulait se plaindre, alors "
        "on le remet à sa place. James : Disparais ou prépare-toi à "
        "combattre !"
    ),
    0x03C60E: (
        "La Team Rocket a dit que, si je l'aidais, je pourrais étudier "
        "les Pokémon !"
    ),
    0x03C748: "Le chemin jusqu'au Boss est encore long !",
    0x03C765: (
        "T'en as mis du temps, Sacha ! Haha ! La Team Rocket t'a "
        "ralenti ! Je t'ai vu à Safrania, alors j'ai voulu voir si tu "
        "avais progressé !"
    ),
    0x03C8B1: "Oh oh ! Je sens un intrus !",
    0x03C8E5: (
        "Jessie : Stop, sale morveux ! James : Disparais ou "
        "prépare-toi ! Miaouss : Exact !"
    ),
    0x03CB39: "Il s'est échappé !",
    0x03D0A7: "Gagner ou perdre, c'est pareil.",
    0x03D0FB: "Le meilleur moyen de voyager !",
    0x03D25A: "Ce qui est génial ? Échanger des Pokémon !",
    0x03D292: (
        "Hé, Champion ! Cette Arène a des murs invisibles ! Trouve les "
        "passages !"
    ),
    0x03D406: "De quelle lignée descends-tu ?",
    0x03D746: "Ça doit être amusant de monter son Pokémon !",
    0x03D9EC: (
        "Hé, Champion ! Les Pokémon de Morgane sont de type Psy. "
        "Les Pokémon Combat n'ont aucune chance !"
    ),
    0x03DFC0: (
        "Ma machine de résurrection va redonner vie à Amonita !"
    ),
    0x03E376: (
        "Je suis Auguste, Champion de l'Arène de Cramois'Île ! "
        "Mes Pokémon vont t'incendier !"
    ),
}

FINAL_EDITORIAL_TEXTS = {
    0x038EFE: (
        "Je t'ai sous-estimé ! Ta victoire mérite le Badge Roche !"
    ),
    0x0393B1: "Team Rocket : gangsters Pokémon, c'est nous !",
    0x039770: (
        "Ces gens ont été volés. On soupçonne la Team Rocket ! "
        "Même la police reste impuissante !"
    ),
    0x03BD1A: "Chaque Pokémon a son propre numéro.",
    0x03C28D: (
        "Jessie : Stop ! Miaouss : Papi voulait râler, alors on le "
        "remet à sa place. James : Disparais ou prépare-toi à "
        "combattre !"
    ),
    0x03C8B1: "Oh oh ! Un intrus approche !",
    0x03D9EC: (
        "Hé, Champion ! Morgane utilise des Pokémon Psy. Le type "
        "Combat n'a aucune chance !"
    ),
}


FIXED_LAYOUT_OFFSETS = {
    0x03043F,
    0x0306C9,
    0x030955,
}


class NonPokedexTranslationCorrectionsTests(unittest.TestCase):
    def test_exact_reviewed_texts_and_layouts(self) -> None:
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }
        self.assertEqual(len(EXPECTED_TEXTS), 38)
        for offset, expected in EXPECTED_TEXTS.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertIn(offset, entries)
                expected = FRENCH_NATURALIZATION_TEXTS.get(
                    offset,
                    CHINESE_FIDELITY_TEXTS.get(
                        offset,
                        FINAL_EDITORIAL_TEXTS.get(offset, expected),
                    ),
                )
                # Newlines are authoritative page breaks rather than
                # translation content; page placement has dedicated tests.
                self.assertEqual(
                    " ".join(entries[offset].text.split()),
                    " ".join(expected.split()),
                )
                expected_layout = (
                    ""
                    if offset in FIXED_LAYOUT_OFFSETS
                    else DIALOGUE_LAYOUT
                )
                self.assertEqual(entries[offset].layout, expected_layout)

    def test_every_reviewed_text_encodes_and_wraps(self) -> None:
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }
        for offset in EXPECTED_TEXTS:
            with self.subTest(offset=f"0x{offset:06X}"):
                payload = format_game_text(
                    entries[offset].text,
                    entries[offset].layout,
                )
                self.assertGreater(len(payload), 0)

    def test_broken_trade_machine_follows_the_chinese_source(self) -> None:
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }
        entry = entries[0x038173]
        self.assertEqual(
            entry.text,
            (
                "Même la machine\n"
                "d'échange est\n"
                "en panne...\n"
                "Reviens plus tard."
            ),
        )
        self.assertEqual(entry.layout, DIALOGUE_LAYOUT)
        self.assertNotIn(0x038173, EXPECTED_TEXTS)


if __name__ == "__main__":
    unittest.main()
