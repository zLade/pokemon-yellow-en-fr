#!/usr/bin/env python3
"""Regressions for the language-neutral restoration topology."""

from __future__ import annotations

import csv
import dataclasses
import unittest
from pathlib import Path

from tools.restoration_topology import (
    BAD_ENGLISH_POINTER_COUNT,
    COLLAPSED_ENGLISH_POINTER_COUNT,
    EXPECTED_RESTORATION_COUNT,
    REMOVED_ENGLISH_POINTER_COUNT,
    RESTORATION_REFERENCES,
    RESTORATION_TOPOLOGY,
    RestorationKind,
    validate_restoration_catalogue,
)


class RestorationTopologyTests(unittest.TestCase):
    def test_topology_has_exact_structural_partition(self) -> None:
        counts = {
            kind: sum(slot.kind is kind for slot in RESTORATION_TOPOLOGY.values())
            for kind in RestorationKind
        }
        self.assertEqual(len(RESTORATION_TOPOLOGY), EXPECTED_RESTORATION_COUNT)
        self.assertEqual(REMOVED_ENGLISH_POINTER_COUNT, 80)
        self.assertEqual(BAD_ENGLISH_POINTER_COUNT, 4)
        self.assertEqual(COLLAPSED_ENGLISH_POINTER_COUNT, 1)
        self.assertEqual(
            counts,
            {
                RestorationKind.REMOVED: 80,
                RestorationKind.MISWIRED: 4,
                RestorationKind.COLLAPSED: 1,
            },
        )

    def test_current_english_catalogue_covers_neutral_topology_exactly(self) -> None:
        path = Path(__file__).resolve().parent.parent / "translation/catalog.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = [
                row for row in csv.DictReader(handle)
                if row["record_type"] == "RESTORED"
            ]
        self.assertEqual(len(rows), 85)
        restorations = {
            int(row["source_offset_or_pointer"], 16): row["english_v2"]
            for row in rows
        }
        self.assertEqual(len(restorations), len(rows), "duplicate restoration keys")
        self.assertTrue(all(text.strip() for text in restorations.values()))
        self.assertEqual(set(restorations), set(RESTORATION_REFERENCES))
        validate_restoration_catalogue(
            restorations,
            label="English restorations",
        )

    def test_four_miswired_targets_are_exact_and_locale_free(self) -> None:
        expected = {
            0x038347: 0x039D3B,
            0x03834B: 0x039D74,
            0x03834F: 0x039DB8,
            0x038353: 0x039DF5,
        }
        for reference, observed_target in expected.items():
            with self.subTest(reference=f"0x{reference:06X}"):
                slot = RESTORATION_TOPOLOGY[reference]
                self.assertIs(slot.kind, RestorationKind.MISWIRED)
                self.assertEqual(slot.observed_english_target, observed_target)
                self.assertEqual(slot.reviewed_replacement_target, 0x039AF5)

    def test_collapsed_item_message_is_a_distinct_restoration(self) -> None:
        slot = RESTORATION_TOPOLOGY[0x0348F1]
        self.assertIs(slot.kind, RestorationKind.COLLAPSED)
        self.assertEqual(slot.observed_english_target, 0x03499D)
        self.assertIsNone(slot.reviewed_replacement_target)

    def test_removed_slots_expect_no_valid_english_target(self) -> None:
        removed = [
            slot
            for slot in RESTORATION_TOPOLOGY.values()
            if slot.kind is RestorationKind.REMOVED
        ]
        self.assertEqual(len(removed), 80)
        self.assertTrue(
            all(slot.observed_english_target is None for slot in removed)
        )
        self.assertTrue(
            all(slot.reviewed_replacement_target is None for slot in removed)
        )

    def test_topology_and_slots_are_immutable(self) -> None:
        with self.assertRaises(TypeError):
            RESTORATION_TOPOLOGY[0x123456] = object()  # type: ignore[index]
        with self.assertRaises(dataclasses.FrozenInstanceError):
            RESTORATION_TOPOLOGY[0x033137].reference = 0  # type: ignore[misc]

    def test_catalogue_validation_reports_missing_and_unknown_keys(self) -> None:
        catalogue = {reference: "text" for reference in RESTORATION_REFERENCES}
        catalogue.pop(0x033137)
        catalogue[0x012345] = "not a restoration"
        with self.assertRaisesRegex(
            ValueError,
            r"test catalogue: missing 0x033137; unknown 0x012345",
        ):
            validate_restoration_catalogue(catalogue, label="test catalogue")


if __name__ == "__main__":
    unittest.main()
