#!/usr/bin/env python3
"""Regressions for the Chinese-faithful French editorial pass."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from rom_traduction_assistant import parse_patch_entries
from tools.chinese_dialogue_restorations import (
    ANIME_MOTTO_RESTORATION_REFERENCES,
    BASE_RESTORED_DIALOGUES,
    EXPECTED_RESTORATION_NATURALIZATION_COUNT,
    OFFICIAL_YELLOW_RESTORATION_REFERENCES,
    RESTORED_DIALOGUES,
    RESTORATION_NATURALIZATION_OVERRIDES,
)
from tools.dialogue_layout import DIALOGUE_LAYOUT
from tools.dialogue_page_quality import optimise_dialogue_pages


DATA_DIR = Path(__file__).resolve().parent / "data"


def load_map(name: str) -> dict[int, str]:
    return {
        int(offset, 0): text
        for offset, text in json.loads(
            (DATA_DIR / name).read_text(encoding="utf-8")
        ).items()
    }


class FrenchNaturalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.chinese_fidelity = load_map(
            "chinese_fidelity_dialogue_overrides.json"
        )
        cls.naturalized = load_map(
            "french_naturalization_overrides.json"
        )
        cls.batch10 = load_map(
            "french_naturalization_batch10_overrides.json"
        )
        cls.batch11 = load_map(
            "french_naturalization_batch11_overrides.json"
        )
        cls.batch12 = load_map(
            "french_naturalization_batch12_overrides.json"
        )
        cls.batch13 = load_map(
            "french_naturalization_batch13_overrides.json"
        )
        cls.batch14 = load_map(
            "french_naturalization_batch14_overrides.json"
        )
        cls.batch15 = load_map(
            "french_naturalization_batch15_overrides.json"
        )
        cls.batch16 = load_map(
            "french_naturalization_batch16_overrides.json"
        )
        cls.batch17 = load_map(
            "french_naturalization_batch17_overrides.json"
        )
        cls.batch18 = load_map(
            "french_naturalization_batch18_overrides.json"
        )
        cls.batch19 = load_map(
            "french_naturalization_batch19_overrides.json"
        )
        cls.batch20 = load_map(
            "french_naturalization_batch20_overrides.json"
        )
        cls.batch21 = load_map(
            "french_naturalization_batch21_overrides.json"
        )
        cls.batch22 = load_map(
            "french_naturalization_batch22_overrides.json"
        )
        cls.batch23 = load_map(
            "french_naturalization_batch23_overrides.json"
        )
        cls.batch24 = load_map(
            "french_naturalization_batch24_overrides.json"
        )
        cls.batch24_compact = load_map(
            "french_naturalization_batch24_compact_overrides.json"
        )
        cls.batch25 = load_map(
            "french_naturalization_batch25_overrides.json"
        )
        cls.batch26 = load_map(
            "french_naturalization_batch26_overrides.json"
        )
        cls.storage_compact = load_map(
            "french_storage_compact_dialogue_overrides.json"
        )
        cls.storage_compact_restorations = load_map(
            "french_storage_compact_restoration_overrides.json"
        )
        cls.official_yellow = load_map(
            "french_official_yellow_dialogue_overrides.json"
        )
        cls.official_gen1_shared = load_map(
            "french_official_gen1_shared_dialogue_overrides.json"
        )
        cls.anime_motto_main = load_map(
            "french_anime_motto_main_overrides.json"
        )
        cls.entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }

    def test_editorial_map_is_a_chinese_fidelity_overlay(self) -> None:
        self.assertEqual(len(self.chinese_fidelity), 970)
        self.assertEqual(len(self.naturalized), 970)
        self.assertEqual(
            set(self.naturalized),
            set(self.chinese_fidelity),
        )

    def test_batch10_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch10), 29)
        self.assertTrue(set(self.batch10).issubset(self.naturalized))
        for offset, expected in self.batch10.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch11_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch11), 23)
        self.assertTrue(set(self.batch11).issubset(self.naturalized))
        for offset, expected in self.batch11.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch12_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch12), 43)
        self.assertTrue(set(self.batch12).issubset(self.naturalized))
        for offset, expected in self.batch12.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch13_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch13), 20)
        self.assertTrue(set(self.batch13).issubset(self.naturalized))
        for offset, expected in self.batch13.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch14_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch14), 24)
        self.assertTrue(set(self.batch14).issubset(self.naturalized))
        for offset, expected in self.batch14.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch15_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch15), 31)
        self.assertTrue(set(self.batch15).issubset(self.naturalized))
        for offset, expected in self.batch15.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch16_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch16), 19)
        self.assertTrue(set(self.batch16).issubset(self.naturalized))
        for offset, expected in self.batch16.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch17_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch17), 12)
        self.assertTrue(set(self.batch17).issubset(self.naturalized))
        for offset, expected in self.batch17.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch18_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch18), 20)
        self.assertTrue(set(self.batch18).issubset(self.naturalized))
        for offset, expected in self.batch18.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch19_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch19), 16)
        self.assertTrue(set(self.batch19).issubset(self.naturalized))
        for offset, expected in self.batch19.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch20_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch20), 21)
        self.assertTrue(set(self.batch20).issubset(self.naturalized))
        for offset, expected in self.batch20.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch21_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch21), 35)
        self.assertTrue(set(self.batch21).issubset(self.naturalized))
        for offset, expected in self.batch21.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch22_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch22), 57)
        self.assertTrue(set(self.batch22).issubset(self.naturalized))
        for offset, expected in self.batch22.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch23_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch23), 126)
        self.assertTrue(set(self.batch23).issubset(self.naturalized))
        for offset, expected in self.batch23.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch24_completes_the_main_editorial_map(self) -> None:
        self.assertEqual(len(self.batch24), 157)
        self.assertEqual(len(self.naturalized), 970)
        self.assertTrue(set(self.batch24).issubset(self.naturalized))
        for offset, expected in self.batch24.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch24_compact_pass_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch24_compact), 35)
        self.assertTrue(
            set(self.batch24_compact).issubset(self.batch24)
        )
        for offset, expected in self.batch24_compact.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.batch24[offset], expected)
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch25_semantic_completion_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch25), 19)
        self.assertTrue(set(self.batch25).issubset(self.naturalized))
        for offset, expected in self.batch25.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)
                self.assertEqual(self.entries[offset].text, expected)
                plan = optimise_dialogue_pages(expected, DIALOGUE_LAYOUT)
                self.assertFalse(
                    any(issue.severity == "strong" for issue in plan.issues)
                )

    def test_batch26_final_naturalization_is_complete_and_exact(self) -> None:
        self.assertEqual(len(self.batch26), 8)
        self.assertTrue(set(self.batch26).issubset(self.naturalized))
        for offset, expected in self.batch26.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)
                self.assertEqual(self.entries[offset].text, expected)
                plan = optimise_dialogue_pages(expected, DIALOGUE_LAYOUT)
                self.assertFalse(
                    any(issue.severity == "strong" for issue in plan.issues)
                )

    def test_storage_compact_dialogues_are_complete_and_exact(self) -> None:
        self.assertEqual(len(self.storage_compact), 137)
        self.assertTrue(set(self.storage_compact).issubset(self.naturalized))
        for offset, expected in self.storage_compact.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], expected)
                self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_storage_compact_restorations_are_complete_and_exact(self) -> None:
        self.assertEqual(len(self.storage_compact_restorations), 3)
        self.assertTrue(
            set(self.storage_compact_restorations).issubset(
                RESTORATION_NATURALIZATION_OVERRIDES
            )
        )
        for reference, expected in self.storage_compact_restorations.items():
            with self.subTest(reference=f"0x{reference:06X}"):
                self.assertEqual(
                    RESTORATION_NATURALIZATION_OVERRIDES[reference],
                    expected,
                )
                self.assertEqual(RESTORED_DIALOGUES[reference], expected)

    def test_every_naturalized_dialogue_is_exact_in_script(self) -> None:
        intro_offsets = {0x03082C, 0x035DCC, 0x035E82}
        for offset, expected in self.naturalized.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertIn(offset, self.entries)
                entry = self.entries[offset]
                self.assertEqual(entry.text, expected)
                expected_layout = (
                    "dialogue_intro_17_19"
                    if offset in intro_offsets
                    else DIALOGUE_LAYOUT
                )
                self.assertEqual(entry.layout, expected_layout)

    def test_naturalized_dialogues_have_no_strong_boundaries(self) -> None:
        intro_offsets = {0x03082C, 0x035DCC, 0x035E82}
        for offset, text in self.naturalized.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                layout = (
                    "dialogue_intro_17_19"
                    if offset in intro_offsets
                    else DIALOGUE_LAYOUT
                )
                plan = optimise_dialogue_pages(
                    text,
                    layout,
                )
                strong = [
                    issue
                    for issue in plan.issues
                    if issue.severity == "strong"
                ]
                self.assertEqual(strong, [])

    def test_external_french_sources_are_explicit_exact_overlays(self) -> None:
        self.assertEqual(len(self.official_yellow), 42)
        self.assertEqual(len(self.official_gen1_shared), 136)
        self.assertEqual(len(self.anime_motto_main), 3)
        source_maps = (
            self.official_yellow,
            self.official_gen1_shared,
            self.anime_motto_main,
        )
        for index, left in enumerate(source_maps):
            for right in source_maps[index + 1:]:
                self.assertFalse(set(left) & set(right))
        for source_map in (
            self.official_yellow,
            self.official_gen1_shared,
            self.anime_motto_main,
        ):
            self.assertTrue(set(source_map).issubset(self.chinese_fidelity))
            self.assertTrue(set(source_map).issubset(self.naturalized))
            for offset, expected in source_map.items():
                with self.subTest(offset=f"0x{offset:06X}"):
                    self.assertEqual(self.naturalized[offset], expected)
                    self.assertEqual(self.chinese_fidelity[offset], expected)

    def test_batch17_yellow_scene_matches_are_provenanced(self) -> None:
        expected = {0x03C722, 0x03CB91, 0x03CE78}
        self.assertTrue(expected.issubset(self.batch17))
        self.assertTrue(expected.issubset(self.official_yellow))

    def test_batch18_does_not_force_nonmatching_external_dialogues(self) -> None:
        external = (
            set(self.official_yellow)
            | set(self.official_gen1_shared)
            | set(self.anime_motto_main)
        )
        self.assertFalse(set(self.batch18) & external)

    def test_batch19_yellow_scene_matches_are_provenanced(self) -> None:
        expected = {0x0384F8, 0x03E1BB}
        self.assertTrue(expected.issubset(self.batch19))
        self.assertTrue(expected.issubset(self.official_yellow))
        self.assertEqual(
            set(self.batch19) & set(self.official_yellow),
            expected,
        )

    def test_batch20_external_scene_matches_are_provenanced(self) -> None:
        yellow = {0x03B1FF}
        shared = {0x03AB27}
        self.assertTrue(yellow.issubset(self.batch20))
        self.assertTrue(yellow.issubset(self.official_yellow))
        self.assertTrue(shared.issubset(self.batch20))
        self.assertTrue(shared.issubset(self.official_gen1_shared))
        self.assertEqual(
            set(self.batch20) & set(self.official_yellow),
            yellow,
        )
        self.assertEqual(
            set(self.batch20) & set(self.official_gen1_shared),
            shared,
        )

    def test_batch21_external_scene_matches_are_provenanced(self) -> None:
        yellow = {0x038744, 0x039D74, 0x03B20E}
        shared = {
            0x03897B,
            0x038A8E,
            0x038F49,
            0x038F91,
            0x0392F0,
            0x039F7C,
            0x03A60F,
            0x03A62F,
            0x03A745,
            0x03ABA2,
            0x03BE50,
            0x03BFD6,
            0x03D9CD,
            0x03D9DD,
            0x03DC83,
            0x03DEDF,
            0x03DFF8,
            0x03E076,
        }
        self.assertEqual(
            set(self.batch21) & set(self.official_yellow),
            yellow,
        )
        self.assertEqual(
            set(self.batch21) & set(self.official_gen1_shared),
            shared,
        )

    def test_batch22_external_scene_matches_are_provenanced(self) -> None:
        self.assertEqual(
            set(self.batch22) & set(self.official_yellow),
            {0x03A555},
        )
        self.assertFalse(
            set(self.batch22) & set(self.official_gen1_shared)
        )
        self.assertFalse(set(self.batch22) & set(self.anime_motto_main))

    def test_batch23_external_scene_matches_are_provenanced(self) -> None:
        self.assertEqual(
            set(self.batch23) & set(self.official_yellow),
            {0x03B835},
        )
        self.assertEqual(
            set(self.batch23) & set(self.official_gen1_shared),
            {0x03CAE7, 0x03DB75, 0x03DC8E},
        )
        self.assertFalse(set(self.batch23) & set(self.anime_motto_main))

    def test_batch24_external_scene_matches_are_provenanced(self) -> None:
        yellow = {
            0x0385D6,
            0x0385F3,
            0x038620,
            0x03864F,
            0x038670,
            0x03868A,
            0x0386A2,
            0x038755,
            0x038DBF,
            0x039C17,
            0x039C62,
            0x03A88A,
            0x03A8A5,
            0x03B188,
            0x03F2EE,
        }
        shared = {
            0x03082C,
            0x035DCC,
            0x035E82,
            0x037994,
            0x038445,
            0x038519,
            0x0387F3,
            0x038A46,
            0x038B03,
            0x038BBC,
            0x038D7A,
            0x038D9F,
            0x038EFE,
            0x03906E,
            0x0392A6,
            0x0392E5,
            0x039540,
            0x0395AE,
            0x039770,
            0x0397E8,
            0x039875,
            0x03989A,
            0x039AC6,
            0x039B19,
            0x039B59,
            0x039B6A,
            0x039B86,
            0x039E91,
            0x039F3F,
            0x039F8C,
            0x03A1C4,
            0x03A1E6,
            0x03A525,
            0x03A538,
            0x03A57C,
            0x03A9D1,
            0x03B4B9,
            0x03B9F1,
            0x03BAF9,
            0x03BB57,
            0x03BBFA,
            0x03BC0A,
            0x03C370,
            0x03C464,
            0x03C493,
            0x03C765,
            0x03C7DF,
            0x03C992,
            0x03CA26,
            0x03CAB3,
            0x03D292,
            0x03D83E,
            0x03D9EC,
            0x03DA39,
            0x03DA73,
            0x03DBE1,
            0x03E03E,
            0x03F27B,
            0x03F3D2,
        }
        self.assertEqual(
            set(self.batch24) & set(self.official_yellow),
            yellow,
        )
        self.assertEqual(
            set(self.batch24) & set(self.official_gen1_shared),
            shared,
        )
        self.assertFalse(set(self.batch24) & set(self.anime_motto_main))

    def test_anti_para_and_reveil_have_distinct_french_payloads(self) -> None:
        self.assertEqual(
            RESTORED_DIALOGUES[0x0348F1],
            "Anti-Para reçu !",
        )
        self.assertEqual(
            self.entries[0x03499D].text,
            "Réveil reçu !",
        )

    def test_nonmatching_rocket_substitutions_follow_live_chinese_pointers(self) -> None:
        expected = {
            0x03BEE1: "JAMES :\nT'as pas honte ?",
            0x03C33F: "JAMES :\nTu vas voir !",
        }
        self.assertFalse(set(expected) & set(self.official_yellow))
        for offset, text in expected.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.naturalized[offset], text)
                self.assertEqual(self.chinese_fidelity[offset], text)

    def test_restoration_editorial_overlay_is_complete_and_exact(self) -> None:
        self.assertEqual(
            len(RESTORATION_NATURALIZATION_OVERRIDES),
            EXPECTED_RESTORATION_NATURALIZATION_COUNT,
        )
        self.assertTrue(
            set(RESTORATION_NATURALIZATION_OVERRIDES).issubset(
                BASE_RESTORED_DIALOGUES
            )
        )
        for reference, expected in (
            RESTORATION_NATURALIZATION_OVERRIDES.items()
        ):
            with self.subTest(reference=f"0x{reference:06X}"):
                self.assertEqual(RESTORED_DIALOGUES[reference], expected)

    def test_semantic_completion_restorations_are_exact(self) -> None:
        expected = {
            0x0331C3: (
                "JESSIE :\nLa Team Nanjing,\nplus rapide\n"
                "que la lumière !"
            ),
            0x038321: (
                "JESSIE :\nLa Team Rocket,\nplus rapide\n"
                "que la lumière !"
            ),
            0x038353: (
                "SCOUT :\nTu es le premier\nà nous avoir tous\n"
                "battus !"
            ),
            0x03AFA6: (
                "JESSIE :\nLa Team Rocket,\nplus rapide\n"
                "que la lumière !"
            ),
            0x03AFFC: (
                "JESSIE :\nLa Team Rocket,\nplus rapide\n"
                "que la lumière !"
            ),
            0x03CF4E: (
                "JESSIE :\nLa Team Rocket,\nplus rapide\n"
                "que la lumière !"
            ),
        }
        for reference, text in expected.items():
            with self.subTest(reference=f"0x{reference:06X}"):
                self.assertEqual(
                    RESTORATION_NATURALIZATION_OVERRIDES[reference],
                    text,
                )
                plan = optimise_dialogue_pages(text, DIALOGUE_LAYOUT)
                self.assertFalse(
                    any(issue.severity == "strong" for issue in plan.issues)
                )

    def test_restoration_provenances_are_complete_and_disjoint(self) -> None:
        self.assertEqual(len(ANIME_MOTTO_RESTORATION_REFERENCES), 58)
        self.assertEqual(len(OFFICIAL_YELLOW_RESTORATION_REFERENCES), 5)
        self.assertFalse(
            ANIME_MOTTO_RESTORATION_REFERENCES
            & OFFICIAL_YELLOW_RESTORATION_REFERENCES
        )
        editorial_references = set(
            RESTORATION_NATURALIZATION_OVERRIDES
        )
        self.assertTrue(
            ANIME_MOTTO_RESTORATION_REFERENCES.issubset(
                editorial_references
            )
        )
        self.assertTrue(
            OFFICIAL_YELLOW_RESTORATION_REFERENCES.issubset(
                editorial_references
            )
        )

    def test_naturalized_restorations_have_no_strong_boundaries(self) -> None:
        for reference, text in (
            RESTORATION_NATURALIZATION_OVERRIDES.items()
        ):
            with self.subTest(reference=f"0x{reference:06X}"):
                plan = optimise_dialogue_pages(text, DIALOGUE_LAYOUT)
                strong = [
                    issue
                    for issue in plan.issues
                    if issue.severity == "strong"
                ]
                self.assertEqual(strong, [])

    def test_beibei_cameo_remains_complete(self) -> None:
        self.assertEqual(
            self.entries[0x034887].text,
            "BEIBEI : Tu es vraiment formidable !",
        )
        self.assertEqual(
            self.entries[0x03BAB6].text,
            "BEIBEI : Je sais tout, jeux vidéo compris ! "
            "Cet Évoli est pour toi !",
        )

    def test_reviewed_chinese_fidelity_corrections_remain_exact(self) -> None:
        expected = {
            0x0336E4: "J'ai perdu...\nBien joué !\nLa suite t'attend.",
            0x03407F: "ALDO : Perdu...\nBien joué !\nLa suite t'attend.",
            0x03584D: "Bats-le et avance.\nBonne chance !",
            0x037A51: (
                "JESSIE : Oui !\nSon nom : Kameiyu !\nIl est développeur\n"
                "chez Nanjing Tech,\nà Céladopole !"
            ),
            0x038F91: "CT35 reçue !",
            0x039E91: (
                "LÉO : Salut !\nMoi, Léo,\nle Pokémaniac !\nTu doutes ?\n"
                "Une expérience\nratée m'a fusionné\navec un Pokémon.\n"
                "Aide-moi.\nJe prends place\nau Téléporteur.\n"
                "Sur ce PC, lance\nla séparation !"
            ),
            0x03B993: (
                "ERIKA : Quel beau\ntemps ! Bienvenue\ndans mon Arène.\n"
                "J'aime les fleurs.\nTu veux combattre ?\nJe ne perdrai pas !"
            ),
            0x03BF2D: (
                "GIOVANNI :\nIm... impossible !\nTu tiens vraiment\n"
                "à tes Pokémon ?\nÇa me dépasse...\nJ'ai fort à faire.\n"
                "Je pars !"
            ),
            0x03C096: "Tout tourne...\nSuis-je anémique ?",
            0x03C370: (
                "M. FUJI :\nTu viens m'aider ?\nMerci.\nJe suis venu\n"
                "apaiser l'âme\nde la mère\nd'Osselait.\n"
                "Elle est en paix.\nRentrons."
            ),
            0x03C992: (
                "GIOVANNI : Sacha !\nEncore toi...\nLe PDG et moi\n"
                "parlons affaires.\nNe t'en mêle pas,\ngamin. Gare à toi !"
            ),
            0x03D37C: "Tu as l'air\nsûr de toi !",
            0x03E1BB: (
                "Salut !\nChampion en herbe !\nAuguste maîtrise\n"
                "les Pokémon Feu !"
            ),
            0x03E954: (
                "GIOVANNI :\nJ'ai perdu. Prends\nle Badge Terre.\n"
                "Tu seras un grand\nDresseur !\nJe reprends\n"
                "mon entraînement.\nJe dissous\nla Team Rocket\n"
                "pour le moment.\nÀ bientôt !"
            ),
        }
        for offset, text in expected.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                self.assertEqual(self.entries[offset].text, text)
                self.assertEqual(self.naturalized[offset], text)
                self.assertEqual(self.chinese_fidelity[offset], text)

        restored = (
            "JAMES : Tu es fort.\nPourtant,\nnotre nouveau chef,\n"
            "Kameiyu, te battra\navec ses Pokémon !\nHa ha !"
        )
        self.assertEqual(RESTORED_DIALOGUES[0x0331D1], restored)
        self.assertEqual(
            RESTORATION_NATURALIZATION_OVERRIDES[0x0331D1],
            restored,
        )


if __name__ == "__main__":
    unittest.main()
