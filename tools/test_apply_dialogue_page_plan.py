#!/usr/bin/env python3
"""Regressions for ROM-budgeted explicit dialogue page authoring."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tools.apply_dialogue_page_plan import (
    Candidate,
    apply_selected_pages,
    author_pages,
    select_for_budget,
)


class ApplyDialoguePagePlanTests(unittest.TestCase):
    def test_knapsack_maximises_strong_gain_then_saves_bytes(self) -> None:
        candidates = (
            Candidate(1, 6, 5, 2, "a", ("a",)),
            Candidate(2, 6, 3, 1, "b", ("b",)),
            Candidate(3, 6, 2, 1, "c", ("c",)),
        )
        selected = select_for_budget(candidates, 5)
        self.assertEqual(tuple(row.offset for row in selected), (1,))

    def test_authored_pages_preserve_accented_source_units(self) -> None:
        candidate = Candidate(
            0x123456,
            7,
            2,
            1,
            "La télé parle de Pokémon.",
            ("La télé parle", "de Pokémon."),
        )
        self.assertEqual(
            author_pages(candidate),
            ("La télé parle", "de Pokémon."),
        )

    def test_apply_rewrites_only_selected_text_argument(self) -> None:
        source = (
            "def p(*args, **kwargs):\n"
            "    pass\n"
            "p(0x123456, \"Tu vas affronter le Conseil des 4 ?\", "
            "layout=\"dialogue_19_19\")\n"
            "p(0x654321, \"Inchangé\", layout=\"dialogue_19_19\")\n"
        )
        candidate = Candidate(
            0x123456,
            7,
            3,
            1,
            "Tu vas affronter le Conseil des 4 ?",
            ("Tu vas affronter", "le Conseil des 4 ?"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "script.py"
            path.write_text(source, encoding="utf-8")
            rewritten, pages = apply_selected_pages(path, (candidate,))
        ast.parse(rewritten)
        self.assertIn("Tu vas affronter\\n", rewritten)
        self.assertIn("Inchangé", rewritten)
        self.assertEqual(
            pages[0x123456],
            ("Tu vas affronter", "le Conseil des 4 ?"),
        )


if __name__ == "__main__":
    unittest.main()
