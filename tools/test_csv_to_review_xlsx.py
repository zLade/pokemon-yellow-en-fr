#!/usr/bin/env python3
"""Regressions for English review metadata and lossless CSV conversion."""

from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from tools.csv_to_review_xlsx import DEFAULT_CSV, build_xlsx
from tools.export_dialogue_review_table import write_csv


NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXPECTED_HEADERS = [
    "id", "stable_key", "category", "source_offset_or_pointer", "script_line",
    "layout", "speaker", "french_reference_text", "chinese_text", "english_2015",
    "alignment_confidence", "translation_history", "naturalized",
    "chinese_fidelity_corrected", "review_verdict", "review_comment",
]


def worksheet_rows(payload: bytes) -> list[list[str]]:
    root = ET.fromstring(payload)
    return [
        [cell.findtext("s:is/s:t", default="", namespaces=NS) for cell in row]
        for row in root.findall("s:sheetData/s:row", NS)
    ]


class CsvToReviewXlsxTests(unittest.TestCase):
    def test_exporter_and_root_ledger_use_english_headers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            write_csv(path, [])
            for source in (path, DEFAULT_CSV):
                with self.subTest(source=source):
                    with source.open(newline="", encoding="utf-8-sig") as handle:
                        self.assertEqual(next(csv.reader(handle)), EXPECTED_HEADERS)

    def test_preserves_headers_and_reference_payloads(self) -> None:
        reference = "RÉGIS : Salut !\nÇa va ?"
        values = [""] * len(EXPECTED_HEADERS)
        values[0] = "D0001"
        values[1] = "MAIN:0x0333FF"
        values[7] = reference
        values[8] = "你好！"
        values[9] = "Hello!"
        values[-1] = " Keep <markup> & whitespace "
        rows = [EXPECTED_HEADERS, values]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "review.csv"
            output = Path(directory) / "review.xlsx"
            with source.open("w", newline="", encoding="utf-8-sig") as handle:
                csv.writer(handle).writerows(rows)
            self.assertEqual(build_xlsx(source, output), (2, 16))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    worksheet_rows(archive.read("xl/worksheets/sheet1.xml")), rows
                )
                core = ET.fromstring(archive.read("docProps/core.xml"))
                self.assertEqual(
                    core.findtext("{http://purl.org/dc/elements/1.1/}title"),
                    "Pokémon Yellow NES — Dialogue review",
                )

    def test_invalid_csv_reports_english_errors(self) -> None:
        for contents, message in (
            ("", "Empty CSV"),
            ("id,stable_key\nD0001\n", "Non-rectangular CSV"),
        ):
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "review.csv"
                output = Path(directory) / "review.xlsx"
                source.write_text(contents, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    build_xlsx(source, output)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
