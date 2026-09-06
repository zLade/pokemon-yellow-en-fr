#!/usr/bin/env python3
"""Regressions for the French battle vocabulary audit."""

from __future__ import annotations

import unittest

from rom_traduction_assistant import load_french_pointer_variants

from tools.audit_battle_french import (
    BATTLE_TEXT_EXPECTATIONS,
    GEN1_MOVE_LABELS,
    MOVE_POINTER_COUNT,
    NES_MOVE_COLUMNS,
    audit,
)


class BattleFrenchAuditTests(unittest.TestCase):
    def test_complete_move_table_and_battle_texts(self) -> None:
        result = audit()
        self.assertEqual(len(result.move_labels), MOVE_POINTER_COUNT)
        self.assertEqual(result.official_gen1_count, len(GEN1_MOVE_LABELS))
        self.assertEqual(result.battle_text_count, len(BATTLE_TEXT_EXPECTATIONS))
        self.assertTrue(
            all(
                all(len(line) <= NES_MOVE_COLUMNS for line in label.splitlines())
                for label in result.move_labels
            )
        )
        self.assertEqual(result.two_line_count, 94)

    def test_reported_problem_labels_are_locked(self) -> None:
        result = audit()
        self.assertEqual(result.move_labels[19], "Éclair")
        self.assertEqual(result.move_labels[22], "Poing-\nÉclair")
        self.assertEqual(result.move_labels[160], "Rugisse-\nment")
        self.assertEqual(BATTLE_TEXT_EXPECTATIONS[0x030599], "Fuite")
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x0302BF],
            " utilise ",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x0301EB],
            "En avant ! ",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x03024E],
            "00000000 est capturé !",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x030ADB],
            "Sacha a vaincu\n",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x030634],
            " ",
        )
        # The live renderer composes this prefix, a Pokémon name (10 columns
        # maximum), then the K.O. suffix on one 24-column line.  The previous
        # ``L'ennemi `` prefix produced a 25-column message and left its final
        # exclamation mark visible during the following EXP message.
        self.assertLessEqual(
            len(BATTLE_TEXT_EXPECTATIONS[0x030634])
            + 10
            + len(BATTLE_TEXT_EXPECTATIONS[0x0301F9]),
            24,
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x030203],
            " EXP gagn. !",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x030AB5],
            " EXP gagnés !",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x03076B],
            "00Dresseur ",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x035F05],
            " veut se battre !",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x035F3D],
            "Résultat : ",
        )
        self.assertEqual(
            BATTLE_TEXT_EXPECTATIONS[0x035FB6],
            "Adversaire : ",
        )

    def test_distinct_chinese_statuses_and_ball_help_are_not_collapsed(self) -> None:
        variants = load_french_pointer_variants()
        status = variants[0x0302FA]
        self.assertEqual(
            tuple(item.pointer_reference for item in status),
            (0x03006B, 0x03006D),
        )
        self.assertEqual(
            tuple(item.text for item in status),
            (" est intoxiqué !", " a peur !"),
        )

        ball_help = variants[0x031A15]
        self.assertEqual(
            tuple(item.pointer_reference for item in ball_help),
            (0x031971, 0x031973, 0x031975),
        )
        self.assertEqual(ball_help[0].text, "CapturePokémon")
        self.assertNotEqual(ball_help[1].text, ball_help[0].text)
        self.assertNotEqual(ball_help[2].text, ball_help[0].text)
        self.assertLessEqual(len(ball_help[1].text), 21)
        self.assertLessEqual(len(ball_help[2].text), 21)
        self.assertLessEqual(len("Captureaccrue "), 14)
        self.assertLessEqual(len("Capturemax.   "), 14)


if __name__ == "__main__":
    unittest.main()
