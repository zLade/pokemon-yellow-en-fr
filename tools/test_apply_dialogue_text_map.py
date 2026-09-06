#!/usr/bin/env python3
"""Tests de la réécriture AST offset→texte."""

from __future__ import annotations

import ast
import unittest

from tools.apply_dialogue_text_map import apply_text_map


class ApplyDialogueTextMapTests(unittest.TestCase):
    def test_only_selected_text_argument_changes(self) -> None:
        source = (
            "PATCHES = [\n"
            "    p(0x123456, \"Ancien texte\", layout=\"dialogue_19_19\"),\n"
            "    p(0x654321, \"Inchangé\", layout=\"dialogue_19_19\"),\n"
            "]\n"
        )
        expected = "Nouvelle page\nPuis la suite."
        updated, changed = apply_text_map(
            source,
            {0x123456: expected},
        )
        self.assertEqual(changed, 1)
        tree = ast.parse(updated)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        ]
        by_offset = {
            call.args[0].value: call.args[1].value
            for call in calls
        }
        self.assertEqual(by_offset[0x123456], expected)
        self.assertEqual(by_offset[0x654321], "Inchangé")
        self.assertIn('layout="dialogue_19_19"', updated)

    def test_missing_offset_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "0x123456"):
            apply_text_map("PATCHES = []\n", {0x123456: "Texte"})


if __name__ == "__main__":
    unittest.main()
