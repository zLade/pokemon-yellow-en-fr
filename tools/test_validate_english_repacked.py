#!/usr/bin/env python3
"""Unit tests for exact English rebuild validation helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_english_repacked import (
    EnglishRepackedError,
    builder_arguments,
    differing_ranges,
    validate_move_label_report,
    validate_overflow_report,
)
from tools.validate_mapper163 import MoveLabelCertification


class ValidateEnglishRepackedTests(unittest.TestCase):
    def test_builder_arguments_include_all_locale_catalogues(self) -> None:
        args = builder_arguments(
            catalogue=Path("catalog.csv"),
            variants=Path("variants.csv"),
            move_labels=Path("move_labels.csv"),
            base=Path("base.nes"),
            output_rom=Path("out.nes"),
            output_ips=Path("out.ips"),
            overflow=Path("overflow.csv"),
            move_label_report=Path("move_label_report.json"),
        )
        self.assertIn("--profile", args)
        self.assertEqual(args[args.index("--profile") + 1], "en-US")
        self.assertEqual(
            args[args.index("--pointer-variants-csv") + 1],
            "variants.csv",
        )
        self.assertEqual(
            args[args.index("--move-labels-csv") + 1],
            "move_labels.csv",
        )
        self.assertEqual(
            args[args.index("--move-label-report") + 1],
            "move_label_report.json",
        )

    def test_differing_ranges_are_compact_and_exact(self) -> None:
        left = b"abcdefghijk"
        right = b"abXXefgYYjk"
        self.assertEqual(differing_ranges(left, right), [(2, 4), (7, 9)])
        self.assertEqual(differing_ranges(left, left), [])
        self.assertEqual(differing_ranges(b"a", b"ab"), [(0, 2)])

    def test_fixed_overflow_report_must_be_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "overflow.csv"
            path.write_text(
                "offset_hex,max_len,en_len,overflow,english_v2\n",
                encoding="utf-8",
            )
            validate_overflow_report(path)
            path.write_text(
                "offset_hex,max_len,en_len,overflow,english_v2\n"
                "0x030100,4,5,1,Hello\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EnglishRepackedError, "1 fixed"):
                validate_overflow_report(path)

    def test_move_label_report_must_match_live_certification(self) -> None:
        certification = MoveLabelCertification(
            catalogue=Path("move_labels.csv"),
            requested_count=2,
            used_even_slots=(38, 40, 42),
            allowed_pair8_offsets=frozenset({1, 2}),
            changed_pair8_offsets=frozenset({1}),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.json"
            path.write_text(
                json.dumps(
                    {
                        "complete": True,
                        "requested_count": 2,
                        "applied_count": 2,
                        "used_even_slots": [38, 40, 42],
                    }
                ),
                encoding="utf-8",
            )
            validate_move_label_report(path, certification)

            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["used_even_slots"] = [38, 42, 40]
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(EnglishRepackedError, "slots differ"):
                validate_move_label_report(path, certification)


if __name__ == "__main__":
    unittest.main()
