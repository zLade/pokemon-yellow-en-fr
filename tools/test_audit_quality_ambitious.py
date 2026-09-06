#!/usr/bin/env python3
"""Tests ciblés des règles à fort signal de l'audit qualité."""

from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from tools.audit_quality_ambitious import Row, audit_rows, read_rows


def row(offset: int, fr_text: str, source_en: str = "") -> Row:
    return Row(
        offset=offset,
        line=1,
        max_len=256,
        source_en=source_en,
        fr_text=fr_text,
    )


def rule_ids(rows: list[Row]) -> set[str]:
    return {str(issue["rule_id"]) for issue in audit_rows(rows)}


class AuditQualityAmbitiousTests(unittest.TestCase):
    def test_csv_safe_page_breaks_are_restored_before_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dialogues.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "offset_hex",
                        "line",
                        "max_len",
                        "source_en",
                        "fr_text",
                        "layout",
                    ),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "offset_hex": "0x03329F",
                        "line": "1",
                        "max_len": "123",
                        "source_en": "First\\nSecond",
                        "fr_text": "D'abord,\\naffronte-moi !",
                        "layout": "dialogue_19_19",
                    }
                )

            parsed = read_rows(path)

        self.assertEqual(parsed[0].source_en, "First\nSecond")
        self.assertEqual(parsed[0].fr_text, "D'abord,\naffronte-moi !")

    def test_known_english_artifacts_are_detected(self) -> None:
        found = rule_ids(
            [
                row(0x030602, "Balls"),
                row(0x030659, "Oui No"),
                row(0x030290, "Dresseur bloque la ball!"),
                row(0x03492F, "Un Pokéball"),
            ]
        )

        self.assertTrue(
            {"english_balls", "mixed_oui_no", "article_ball", "pokeball_gender"}
            <= found
        )

    def test_corrected_ball_labels_are_not_flagged(self) -> None:
        found = rule_ids(
            [
                row(0x030602, "Poké Balls"),
                row(0x030659, "Oui Non"),
                row(0x030290, "Dresseur bloque la Poké Ball!"),
                row(0x03492F, "Une Poké Ball!"),
            ]
        )

        self.assertTrue(
            {
                "english_balls",
                "mixed_oui_no",
                "article_ball",
                "pokeball_gender",
            }.isdisjoint(found)
        )

    def test_wrong_official_terms_are_detected_at_their_offsets(self) -> None:
        found = rule_ids(
            [
                row(0x039937, "Tu peux utiliser la CS Surf!"),
                row(0x03DC8E, "Cette CT enseigne Psyko."),
                row(0x03B9F1, "Voici le Badge Arc-en-Ciel!"),
                row(0x03DB8E, "Tu veux le badge Arène de Morgane!"),
                row(0x031538, "BlopAtq"),
                row(0x031545, "Vit.E"),
                row(0x03176F, "MaxElixr"),
            ]
        )

        self.assertTrue(
            {
                "misty_wrong_hm",
                "psybeam_psyko",
                "rainbow_badge",
                "marsh_badge",
                "fake_out",
                "swift",
                "max_ether",
            }
            <= found
        )

    def test_corrected_official_terms_and_legitimate_surf_are_not_flagged(
        self,
    ) -> None:
        found = rule_ids(
            [
                row(0x039937, "CS Coupe. CT11 Bulles d'O."),
                row(0x03DC8E, "Cette CT enseigne Rafale Psy."),
                row(0x03B9F1, "Voici le Badge Prisme!"),
                row(0x03DB8E, "Tu veux le Badge Marais!"),
                row(0x031538, "Bluff"),
                row(0x031545, "Météores"),
                row(0x03176F, "Huile Max"),
                row(0x040000, "La CS Surf permet de traverser l'eau."),
            ]
        )

        targeted_rules = {
            "misty_wrong_hm",
            "psybeam_psyko",
            "rainbow_badge",
            "marsh_badge",
            "fake_out",
            "swift",
            "max_ether",
        }
        self.assertTrue(targeted_rules.isdisjoint(found))
        self.assertNotIn("term_gym", found)

    def test_dialogue_layout_boundary_is_not_reported_as_glue(self) -> None:
        found = rule_ids(
            [
                row(
                    0x03A745,
                    "Tu es vraiment   "
                    "fort, gamin! Voici "
                    "le Badge Foudre! Il"
                    "te permet          "
                    "d'utiliser Vol à   "
                    "tout moment! Prends"
                    "aussi cette CT!",
                ),
            ]
        )

        self.assertNotIn("possible_glue", found)

    def test_truncated_endings_and_missing_spaces_are_detected(self) -> None:
        found = rule_ids(
            [
                row(0x040001, "est empoiso"),
                row(0x03ADC8, "J'abando"),
                row(0x040002, "Il tepermets de passer."),
            ]
        )

        self.assertIn("ending_empoiso", found)
        self.assertIn("clip_03adc8", found)
        self.assertIn("fragment_17", found)

    def test_common_short_terms_do_not_look_truncated(self) -> None:
        found = rule_ids(
            [
                row(
                    0x040003,
                    "Vol Surf Route Continue Master Ball Super Ball",
                ),
                row(0x040004, "Att."),
                row(0x040005, "Il couve"),
            ]
        )

        self.assertFalse(any(rule_id.startswith("ending_") for rule_id in found))

    def test_prefixed_caught_message_is_detected(self) -> None:
        self.assertIn(
            "caught_unaccented",
            rule_ids([row(0x03024E, "00000000est capture!")]),
        )

    def test_reviewed_canonical_false_positives_are_allowlisted(self) -> None:
        reviewed = [
            row(0x0314A5, "Dracosouffle"),
            row(0x0340C1, "Autrefois, il était redoutable."),
            row(0x03BD9E, "Argh...Aaaah..."),
            row(0x03B160, "Tu avais l'air inoffensif."),
            row(0x032E5F, "Il guide les égarés dans les blizzards."),
            row(0x032924, "Son odeur affreuse peut faire perdre connaissance."),
            row(0x037067, "Affamé, il avale tout ce qui bouge."),
            row(0x03DE2C, "Mon ami m'offre des perles !"),
            row(
                0x032420,
                "Ses piquants venimeux le rendent dangereux.",
                "Its venomous barbs render this Pok@mon dangerous.",
            ),
            row(
                0x032451,
                "Agressif, il attaque sans hésiter.",
                "An aggressive Pok@mon that is quick to attack.",
            ),
            row(
                0x0324AF,
                "Rare, il a beaucoup d'admirateurs",
                "This Pok@mon has many admirers and is very rare.",
            ),
            row(
                0x032B12,
                "Rare, il apporterait le bonheur à tous.",
                "Rare Pok@mon said to bring happiness to all.",
            ),
            row(
                0x032E2F,
                "Très paresseux, il dévore tout.",
                "A very lazy Pok@mon that will devour anything.",
            ),
            row(
                0x032F2A,
                "Son aboiement gronde comme le tonnerre.",
                "This legendary Pok@mon barks like thunder.",
            ),
            row(
                0x036BD3,
                "Il préfère les attaques au contact et les morsures.",
                "This Pok@mon prefers close combat.",
            ),
            row(
                0x03744B,
                "Ses coups de pied terrassent ses rivaux.",
                "This Pok@mon destroys opponents with its kicks.",
            ),
            row(
                0x03773F,
                "Programmé, il voyage dans le cyberespace.",
                "A programmed Pok@mon that can move in cyberspace.",
            ),
            row(
                0x0398D1,
                "Les Dresseurs pros ont chacun leur stratégie.",
                "Water Pok@mon strategy.",
            ),
        ]

        self.assertEqual(audit_rows(reviewed), [])

    def test_term_pokemon_exception_is_offset_scoped(self) -> None:
        found = rule_ids(
            [
                row(
                    0x040006,
                    "Son aboiement gronde comme le tonnerre.",
                    "This legendary Pok@mon barks like thunder.",
                )
            ]
        )

        self.assertIn("term_pokemon", found)


if __name__ == "__main__":
    unittest.main()
