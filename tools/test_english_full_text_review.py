#!/usr/bin/env python3
"""Determinism and coverage tests for the exhaustive English text review."""

from __future__ import annotations

import csv
import io
import unittest

from tools.english_full_text_review import (
    CATALOGUE,
    CONTEXTUAL_SPEAKER_LABELS,
    EMBEDDED_SPEAKER_LABEL_RE,
    FIXED_GRID_7X3_KEYS,
    REPORT,
    REPORT_FIELDS,
    REVISIONS,
    SHADOWED_NONLIVE_ROWS,
    SPEAKER_PREFIXES,
    SPEAKER_LABEL_RE,
    VARIANTS,
    build_outputs,
)
from tools.validate_english_catalog import EXPECTED_FIXED_ITEM_NAME_PAYLOADS
from tools.validate_english_catalog import (
    BATTLE_ARTIFACT_FREE_LINE_CELLS,
    BATTLE_LINE_BREAK_KEYS,
)


def csv_rows(rendered: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(rendered)))


class EnglishFullTextReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs, cls.stats = build_outputs()
        cls.catalogue = csv_rows(cls.outputs[CATALOGUE])
        cls.variants = csv_rows(cls.outputs[VARIANTS])
        cls.report = csv_rows(cls.outputs[REPORT])

    def test_generated_outputs_are_current_and_complete(self) -> None:
        self.assertEqual(self.stats["catalogue_rows"], 1929)
        self.assertEqual(self.stats["pointer_variants"], 7)
        self.assertEqual(self.stats["report_rows"], 1936)
        self.assertEqual(self.stats["live_surfaces"], 1934)
        self.assertEqual(self.stats["shadowed_nonlive_rows"], 2)
        self.assertGreaterEqual(self.stats["corrected_catalogue_rows"], 430)
        for path, rendered in self.outputs.items():
            self.assertEqual(path.read_text(encoding="utf-8"), rendered, path)

    def test_report_has_one_unique_witness_per_catalogued_surface(self) -> None:
        identities = [
            (row["surface"], row["stable_key"])
            for row in self.report
        ]
        self.assertEqual(len(identities), 1936)
        self.assertEqual(len(set(identities)), 1936)
        self.assertEqual(tuple(self.report[0]), REPORT_FIELDS)

    def test_every_declared_revision_exists_in_the_catalogue(self) -> None:
        catalogue_keys = {row["stable_key"] for row in self.catalogue}
        self.assertLessEqual(set(REVISIONS), catalogue_keys)

    def test_item_descriptions_use_the_real_7x3_grid(self) -> None:
        rows = {
            row["stable_key"]: row
            for row in self.catalogue
            if row["layout"] == "fixed_grid_7x3"
        }
        self.assertEqual(set(rows), set(FIXED_GRID_7X3_KEYS))
        self.assertTrue(all(int(row["encoded_length"]) <= 21 for row in rows.values()))
        expected_variants = {
            "MAIN:0x031A15@0x031971": "Catch  Pokémon",
            "MAIN:0x031A15@0x031973": "Better than a Poké B.",
            "MAIN:0x031A15@0x031975": "Better than a Great B",
        }
        actual = {
            row["variant_key"]: row["english_v2"]
            for row in self.variants
            if row["stable_key"] == "MAIN:0x031A15"
        }
        self.assertEqual(actual, expected_variants)
        self.assertTrue(all(len(text.encode("ascii", "replace")) <= 21 for text in actual.values()))

    def test_bag_item_names_leave_one_cell_before_quantity(self) -> None:
        rows = {row["stable_key"]: row for row in self.catalogue}
        for key, expected in EXPECTED_FIXED_ITEM_NAME_PAYLOADS.items():
            self.assertEqual(rows[key]["english_v2"], expected, key)
            self.assertLessEqual(int(rows[key]["encoded_length"]), 7, key)

    def test_battle_line_breaks_are_declared_and_artifact_free(self) -> None:
        rows = {row["stable_key"]: row for row in self.catalogue}
        actual = {
            key for key, row in rows.items()
            if "\n" in row["english_v2"]
            and row["layout"] in {"", "raw"}
        }
        self.assertEqual(actual, set(BATTLE_LINE_BREAK_KEYS))
        for key in BATTLE_LINE_BREAK_KEYS:
            text = rows[key]["english_v2"]
            self.assertEqual(text.count("\n"), 1, key)
            self.assertTrue(
                all(
                    len(line.replace("é", "@")) <= BATTLE_ARTIFACT_FREE_LINE_CELLS
                    for line in text.split("\n")
                ),
                (key, text),
            )

    def test_executable_context_and_metadata_are_coherent(self) -> None:
        rows = {row["stable_key"]: row for row in self.catalogue}
        self.assertEqual(rows["MAIN:0x0349E5"]["english_v2"], "Got Ether!")
        self.assertEqual(rows["MAIN:0x0349F2"]["english_v2"], "Got Max Ether!")
        self.assertEqual(rows["MAIN:0x038F91"]["english_v2"], "Got TM35!")
        for key in ("MAIN:0x0349E5", "MAIN:0x0349F2", "MAIN:0x038F91"):
            self.assertNotIn("is unchanged", rows[key]["compression_justification"])
            self.assertEqual(rows[key]["compression"], "no")
        for row in self.catalogue:
            self.assertLessEqual(row["fidelity_comment"].count("Full-text review:"), 1)

    def test_nonstandard_speaker_prefixes_are_gone(self) -> None:
        forbidden = tuple(SPEAKER_PREFIXES)
        for row in self.catalogue:
            if row["layout"].startswith("dialogue_"):
                self.assertFalse(
                    row["english_v2"].startswith(forbidden),
                    (row["stable_key"], row["english_v2"]),
                )

    def test_generic_single_speaker_labels_are_omitted(self) -> None:
        for row in self.catalogue:
            if not row["layout"].startswith("dialogue_"):
                continue
            text = row["english_v2"]
            match = SPEAKER_LABEL_RE.match(text)
            if match is None or match.group(1) not in CONTEXTUAL_SPEAKER_LABELS:
                continue
            self.assertIsNotNone(
                EMBEDDED_SPEAKER_LABEL_RE.search(text[match.end():]),
                (row["stable_key"], text),
            )

    def test_shadowed_overlap_rows_pin_the_exact_live_owner(self) -> None:
        report = {row["stable_key"]: row for row in self.report}
        self.assertEqual(
            SHADOWED_NONLIVE_ROWS,
            {
                "MAIN:0x039D3B": (
                    "0x038347", "RESTORED:0x038347", "0x03A2CE"
                ),
                "MAIN:0x03DF0D": (
                    "0x03CF60", "MAIN:0x03D7CB", "0x03B1E6"
                ),
            },
        )
        for key, (reference, owner, target) in SHADOWED_NONLIVE_ROWS.items():
            self.assertEqual(report[key]["domain"], "shadowed_nonlive")
            self.assertEqual(report[key]["status"], "shadowed_nonlive")
            for witness in (reference, owner, target):
                self.assertIn(witness, report[key]["reason"])

    def test_obsolete_7x2_review_contract_is_gone(self) -> None:
        self.assertFalse(
            any("fixed_grid_7x2" in row["review_class"] for row in self.report)
        )


if __name__ == "__main__":
    unittest.main()
