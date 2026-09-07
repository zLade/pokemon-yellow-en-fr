"""Regression coverage for the two editable catalogue parts."""
import csv
import tempfile
import unittest
from pathlib import Path

from tools.catalogue_io import PART_NAMES, GITHUB_CSV_LIMIT, catalogue_bytes, open_csv


class CataloguePartsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write(0, [["stable_key", "text"], ["a", ' Chinese 中文, "quoted"\n next ']])
        self.write(1, [["stable_key", "text"], ["b", "second"]])

    def write(self, part, rows):
        with (self.root / PART_NAMES[part]).open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle, lineterminator="\n").writerows(rows)

    def test_order_and_all_cell_contents(self):
        with open_csv(self.root) as handle:
            self.assertEqual(list(csv.reader(handle)), [
                ["stable_key", "text"], ["a", ' Chinese 中文, "quoted"\n next '],
                ["b", "second"]])

    def test_second_part_edit_is_read(self):
        self.write(1, [["stable_key", "text"], ["b", "edited"]])
        with open_csv(self.root) as handle:
            self.assertEqual(list(csv.DictReader(handle))[-1]["text"], "edited")

    def test_missing_part_fails(self):
        (self.root / PART_NAMES[1]).unlink()
        with self.assertRaises(FileNotFoundError):
            catalogue_bytes(self.root)

    def test_invalid_parts_fail(self):
        cases = [
            [["stable_key", "other"], ["b", "text"]],
            [["stable_key", "text"], ["a", "duplicate"]],
            [["stable_key", "text"], ["b", "text"], ["b", "duplicate"]],
            [["stable_key", "text"], ["", "missing"]],
            [["stable_key", "text"], ["b"]],
            [["stable_key", "text"]],
            [["stable_key", "text"], ["b", "x" * GITHUB_CSV_LIMIT]],
        ]
        for rows in cases:
            with self.subTest(rows=rows[0]):
                self.write(1, rows)
                with self.assertRaises(ValueError):
                    catalogue_bytes(self.root)

    def test_single_csv_fixture_remains_supported(self):
        path = self.root / PART_NAMES[0]
        self.assertEqual(catalogue_bytes(path), path.read_bytes())

    def test_build_tracks_both_parts_separately(self):
        from tools.build_english_release import input_records
        before = input_records([self.root])
        self.assertEqual(len(before), 2)
        self.write(1, [["stable_key", "text"], ["b", "edited"]])
        self.assertNotEqual(before, input_records([self.root]))


if __name__ == "__main__":
    unittest.main()
