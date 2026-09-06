#!/usr/bin/env python3
"""Static proof for Pierre's CT reward and its move."""

from __future__ import annotations

import unittest

from tools.audit_brock_tm_reward import (
    ENGLISH_ROM,
    audit_brock_tm_reward,
    french_move_for_tm,
    move_name_record_offset,
)


class BrockTmRewardTests(unittest.TestCase):
    def test_executable_tm_table_distinguishes_34_and_35(self) -> None:
        rom = ENGLISH_ROM.read_bytes()
        self.assertEqual(move_name_record_offset(rom, 34), 0x03118F)
        self.assertEqual(move_name_record_offset(rom, 35), 0x0315D0)
        self.assertEqual(french_move_for_tm(rom, 34), "Onde de Choc")
        self.assertEqual(french_move_for_tm(rom, 35), "Armure")

    def test_brock_reward_is_tm35_harden(self) -> None:
        result = audit_brock_tm_reward()
        self.assertEqual(result.source_receipt_tm, 34)
        self.assertEqual(result.source_explanation_tm, 35)
        self.assertEqual(result.english_runtime_receipt_tm, 35)
        self.assertEqual(result.resolved_tm, 35)
        self.assertEqual(result.resolved_move, "Armure")
        self.assertEqual(result.tm34_move, "Onde de Choc")
        self.assertTrue(result.source_receipt_is_typo)


if __name__ == "__main__":
    unittest.main()
