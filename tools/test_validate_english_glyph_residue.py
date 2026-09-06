from __future__ import annotations

import csv
import unittest
from pathlib import Path

from tools.validate_english_glyph_residue import (
    DEFAULT_NEUTRAL,
    EXPECTED_NEUTRAL_INDICES,
)


class EnglishGlyphResidueTableTests(unittest.TestCase):
    def test_neutral_table_is_explicit_exact_and_reviewed(self) -> None:
        with Path(DEFAULT_NEUTRAL).open(
            encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 18)
        self.assertEqual(
            {int(row["record_index"]) for row in rows},
            EXPECTED_NEUTRAL_INDICES,
        )
        self.assertTrue(all(
            row["classification"] == "language_neutral_type_pictogram"
            and row["review_status"] == "reviewed_language_neutral"
            and row["reason"].strip()
            for row in rows
        ))
        self.assertEqual(rows[0]["start_hex"], "0x03059D")
        self.assertEqual(rows[-1]["end_hex_exclusive"], "0x0305E6")


if __name__ == "__main__":
    unittest.main()
