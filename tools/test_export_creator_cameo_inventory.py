#!/usr/bin/env python3
"""Regressions for the stable creator-cameo inventory."""

from __future__ import annotations

import unittest

from tools.export_creator_cameo_inventory import build_cameo_rows


class ExportCreatorCameoInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = build_cameo_rows()
        cls.by_key = {row["stable_key"]: row for row in cls.rows}

    def test_inventory_uses_current_stable_ids_and_payloads(self) -> None:
        self.assertEqual(len(self.rows), 17)
        self.assertEqual(len(self.by_key), len(self.rows))
        self.assertEqual(len({row["id"] for row in self.rows}), len(self.rows))
        for row in self.rows:
            with self.subTest(stable_key=row["stable_key"]):
                self.assertTrue(row["id"].startswith("D"))
                self.assertTrue(row["chinese_text"])
                self.assertTrue(row["french_reference_text"])
                self.assertEqual(
                    row["status"],
                    "restored in the French version",
                )

    def test_beibei_cameo_is_complete(self) -> None:
        expected = {
            "MAIN:0x034887": "D0064",
            "MAIN:0x03BAB6": "D0632",
        }
        for stable_key, public_id in expected.items():
            with self.subTest(stable_key=stable_key):
                row = self.by_key[stable_key]
                self.assertEqual(row["id"], public_id)
                self.assertEqual(row["creator_or_cameo"], "Beibei")
                self.assertIn("BEIBEI", row["french_reference_text"])

    def test_repaired_kameiyu_mentions_are_not_stale(self) -> None:
        self.assertEqual(
            self.by_key["MAIN:0x037A51"]["french_reference_text"],
            "JESSIE : Oui !\nSon nom : Kameiyu !\nIl est développeur\n"
            "chez Nanjing Tech,\nà Céladopole !",
        )
        restored = self.by_key["RESTORED:0x0331D1"]
        self.assertEqual(restored["id"], "D0993")
        self.assertIn("notre nouveau chef", restored["french_reference_text"])
        self.assertIn("avec ses Pokémon", restored["french_reference_text"])


if __name__ == "__main__":
    unittest.main()
