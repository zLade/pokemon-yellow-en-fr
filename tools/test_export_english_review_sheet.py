from __future__ import annotations

import unittest

from tools.export_english_review_sheet import FIELDS, export_rows, render_csv


class EnglishReviewSheetExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = export_rows()

    def test_cardinality_and_keys(self) -> None:
        self.assertEqual(len(self.rows), 1929)
        self.assertEqual(len({row["stable_key"] for row in self.rows}), 1929)

    def test_reference_counts(self) -> None:
        self.assertEqual(
            sum(
                row["changed_during_official_reference_pass"] == "Yes"
                for row in self.rows
            ),
            170,
        )
        self.assertEqual(
            sum(row["reference_disposition"] != "n/a" for row in self.rows),
            183,
        )

    def test_human_review_fields_are_seeded(self) -> None:
        self.assertTrue(
            all(row["human_review_status"] == "To review" for row in self.rows)
        )
        self.assertTrue(all(not row["human_reviewer"] for row in self.rows))
        self.assertTrue(all(not row["human_review_notes"] for row in self.rows))

    def test_rendered_header_is_stable(self) -> None:
        header = render_csv(self.rows).splitlines()[0].split(",")
        self.assertEqual(header, list(FIELDS))


if __name__ == "__main__":
    unittest.main()
