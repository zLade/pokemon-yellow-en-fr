#!/usr/bin/env python3
"""Tests for the complete 63-row EN2 Chinese-source adjudication."""

from __future__ import annotations

import unittest

from tools.adjudicate_english_sources import (
    ADJUDICATION_REVIEW_FIELDS,
    CATALOGUE_SOURCE_FIELDS,
    CATALOGUE_SOURCE_RESOLUTION,
    DIRECT_SELECTIONS,
    RECOVERED_POINTER_RECORDS,
    RESOLUTION_STATUS,
    SHADOW_OWNER_RECORDS,
    SOURCE_REVIEW_STATUS,
    SPECIAL_SELECTIONS,
    apply_reviews,
    build_decisions,
)
from tools.generate_english_catalog import (
    EXPECTED_ADJUDICATION_ROWS,
    build_catalog_bundle,
)


class EnglishSourceAdjudicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = build_catalog_bundle()
        cls.decisions = build_decisions()
        cls.adjudications, cls.catalogue = apply_reviews(
            cls.seed["source_adjudications.csv"],
            cls.seed["catalog.csv"],
            cls.decisions,
        )

    def test_exactly_sixty_three_reviewed_decisions_have_no_pending_marker(self) -> None:
        self.assertEqual(len(self.decisions), EXPECTED_ADJUDICATION_ROWS)
        self.assertEqual(len(self.adjudications), EXPECTED_ADJUDICATION_ROWS)
        for row in self.adjudications:
            with self.subTest(key=row["stable_key"]):
                self.assertTrue(row["selected_source_method"])
                self.assertTrue(row["selected_chinese_offsets"])
                self.assertTrue(row["selected_chinese_text"])
                self.assertEqual(row["resolution_status"], RESOLUTION_STATUS)
                self.assertEqual(row["review_status"], SOURCE_REVIEW_STATUS)
                self.assertNotIn("pending", " ".join(row.values()).casefold())
                # Empty record/pointer fields are valid only when the note
                # explicitly documents direct or sequential/unpointed storage.
                if not row["selected_chinese_record_indexes"]:
                    self.assertIn("direct compact payload", row["note"])
                if not row["selected_pointer_references"]:
                    self.assertIn("sequential/unpointed", row["note"])

    def test_all_fifteen_unaligned_sources_are_explicitly_resolved(self) -> None:
        seed_unaligned = {
            row["stable_key"]
            for row in self.seed["source_adjudications.csv"]
            if row["alignment_method"] == "unaligned"
        }
        self.assertEqual(len(seed_unaligned), 15)
        reviewed = {row["stable_key"]: row for row in self.adjudications}
        for key in seed_unaligned:
            with self.subTest(key=key):
                self.assertEqual(reviewed[key]["resolution_status"], RESOLUTION_STATUS)
                self.assertTrue(reviewed[key]["selected_chinese_text"])

    def test_false_physical_move_matches_use_the_reviewed_owner(self) -> None:
        for key, record_index in {
            **SHADOW_OWNER_RECORDS,
            **RECOVERED_POINTER_RECORDS,
        }.items():
            with self.subTest(key=key):
                self.assertEqual(
                    self.decisions[key].record_indexes,
                    (record_index,),
                )
        self.assertEqual(self.decisions["MAIN:0x0316E9"].chinese_text, "无")
        self.assertEqual(
            self.decisions["MAIN:0x03DF0D"].record_indexes,
            ("1827",),
        )

    def test_catalogue_only_changes_source_fields_on_the_sixty_three_keys(self) -> None:
        before = {row["stable_key"]: row for row in self.seed["catalog.csv"]}
        after = {row["stable_key"]: row for row in self.catalogue}
        self.assertEqual(before.keys(), after.keys())
        changed_keys: set[str] = set()
        for key in before:
            changed = {
                field
                for field in before[key]
                if before[key][field] != after[key][field]
            }
            if changed:
                changed_keys.add(key)
                self.assertTrue(changed.issubset(set(CATALOGUE_SOURCE_FIELDS)))
        self.assertEqual(changed_keys, set(self.decisions))
        for key in self.decisions:
            self.assertEqual(after[key]["source_resolution"], CATALOGUE_SOURCE_RESOLUTION)
            self.assertEqual(after[key]["review_status"], "pending")
            self.assertEqual(after[key]["english_v2"], before[key]["english_v2"])

    def test_adjudication_only_changes_reviewed_selection_fields(self) -> None:
        before = {
            row["stable_key"]: row
            for row in self.seed["source_adjudications.csv"]
        }
        after = {row["stable_key"]: row for row in self.adjudications}
        self.assertEqual(before.keys(), after.keys())
        for key in before:
            changed = {
                field
                for field in before[key]
                if before[key][field] != after[key][field]
            }
            with self.subTest(key=key):
                self.assertTrue(changed)
                self.assertTrue(
                    changed.issubset(set(ADJUDICATION_REVIEW_FIELDS))
                )

    def test_explicit_exception_sets_are_disjoint_and_accounted_for(self) -> None:
        groups = [
            set(DIRECT_SELECTIONS),
            set(SHADOW_OWNER_RECORDS),
            set(RECOVERED_POINTER_RECORDS),
            set(SPECIAL_SELECTIONS),
        ]
        for index, group in enumerate(groups):
            for other in groups[index + 1 :]:
                self.assertTrue(group.isdisjoint(other))
        self.assertTrue(set().union(*groups).issubset(self.decisions))


if __name__ == "__main__":
    unittest.main()
