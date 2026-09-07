from __future__ import annotations

import csv
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from tools.generate_english_catalog import (
    EXPECTED_ADJUDICATION_ROWS,
    EXPECTED_CATALOG_ROWS,
    EXPECTED_MAIN_DIALOGUES,
    EXPECTED_MAIN_ROWS,
    EXPECTED_MANUAL_SOURCE_KEYS,
    EXPECTED_MULTI_SOURCE_KEYS,
    EXPECTED_NON_DIALOGUE_MAIN_ROWS,
    EXPECTED_POINTER_VARIANT_ROWS,
    EXPECTED_POKEDEX_ROWS,
    EXPECTED_RESTORED_ROWS,
    EXPECTED_UNALIGNED_DIALOGUE_KEYS,
    EXPECTED_UNALIGNED_NON_DIALOGUE_KEYS,
    FALSE_HIGH_KEYS,
    POINTER_VARIANT_KEYS,
    RESTORATION_SPLIT_KEYS,
    SAFE_SHARED_KEYS,
    STORAGE_OVERLAP_PAIRS,
    build_catalog_bundle,
    write_bundle,
)


class EnglishCatalogSeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = build_catalog_bundle()
        cls.catalog = cls.bundle["catalog.csv"]
        cls.catalog_by_key = {
            row["stable_key"]: row for row in cls.catalog
        }

    def test_generated_metadata_notes_are_complete_english(self) -> None:
        self.assertEqual(
            {row["note"] for row in self.bundle["storage_overlaps.csv"]},
            {
                "The short payload already aliased the suffix of the longer "
                "payload in the 2015 English ROM; future edits must "
                "relocate them or preserve compatible bytes."
            },
        )
        self.assertEqual(
            {row["fidelity_comment"] for row in self.bundle["pointer_variants.csv"]},
            {
                "The 2015 English ROM shares storage for semantically distinct "
                "Chinese messages; translate this variant before compilation.",
                "The 2015 English table shifts this move-name pointer; "
                "translate this reviewed Chinese variant before compilation.",
            },
        )

    def test_catalog_cardinalities_and_unique_stable_keys(self) -> None:
        self.assertEqual(len(self.catalog), EXPECTED_CATALOG_ROWS)
        self.assertEqual(
            Counter(row["record_type"] for row in self.catalog),
            Counter(
                {
                    "MAIN": EXPECTED_MAIN_ROWS,
                    "RESTORED": EXPECTED_RESTORED_ROWS,
                }
            ),
        )
        self.assertEqual(
            len({row["stable_key"] for row in self.catalog}),
            EXPECTED_CATALOG_ROWS,
        )
        self.assertEqual(
            sum(
                row["record_type"] == "MAIN" and bool(row["dialogue_id"])
                for row in self.catalog
            ),
            EXPECTED_MAIN_DIALOGUES,
        )
        self.assertEqual(
            sum(
                row["record_type"] == "MAIN" and not row["dialogue_id"]
                for row in self.catalog
            ),
            EXPECTED_NON_DIALOGUE_MAIN_ROWS,
        )
        self.assertEqual(
            sum(row["category"] == "Pokédex" for row in self.catalog),
            EXPECTED_POKEDEX_ROWS,
        )
        self.assertTrue(all(row["chinese_text"] for row in self.catalog))

    def test_fresh_seed_never_claims_editorial_review(self) -> None:
        self.assertEqual(
            {row["review_status"] for row in self.catalog}, {"pending"}
        )
        seeded = [row for row in self.catalog if row["english_v2"]]
        self.assertTrue(seeded)
        self.assertEqual(
            {row["editorial_origin"] for row in seeded},
            {"english_2015_unreviewed_seed"},
        )
        for row in seeded:
            self.assertEqual(
                int(row["encoded_length"]),
                len(row["english_v2"].encode("ascii")),
            )
            self.assertLessEqual(
                int(row["encoded_length"]),
                int(row["source_capacity_bytes"]),
            )
        graphical = [
            row
            for row in self.catalog
            if row["english_2015_storage"] == "graphical_codes"
        ]
        self.assertTrue(graphical)
        self.assertTrue(all(not row["english_v2"] for row in graphical))
        restored = [
            row for row in self.catalog if row["record_type"] == "RESTORED"
        ]
        self.assertTrue(all(not row["english_v2"] for row in restored))

    def test_sixty_three_source_adjudications_are_derived(self) -> None:
        adjudications = self.bundle["source_adjudications.csv"]
        self.assertEqual(len(adjudications), EXPECTED_ADJUDICATION_ROWS)
        non_high = {
            row["stable_key"]
            for row in self.catalog
            if row["record_type"] == "MAIN"
            and row["alignment_confidence"] != "high"
        }
        self.assertEqual(
            Counter(
                row["alignment_confidence"]
                for row in self.catalog
                if row["record_type"] == "MAIN"
                and row["alignment_confidence"] != "high"
            ),
            Counter({"medium": 42, "low": 16}),
        )
        self.assertEqual(len(non_high), 58)
        self.assertEqual(
            {row["stable_key"] for row in adjudications},
            non_high | FALSE_HIGH_KEYS,
        )
        self.assertTrue(
            all(row["review_status"] == "pending" for row in adjudications)
        )

    def test_all_fifteen_unaligned_sources_are_explicitly_resolved(
        self,
    ) -> None:
        unaligned = [
            row
            for row in self.catalog
            if row["record_type"] == "MAIN"
            and row["alignment_method"] == "unaligned"
        ]
        dialogue_rows = [row for row in unaligned if row["dialogue_id"]]
        non_dialogue_rows = [row for row in unaligned if not row["dialogue_id"]]
        self.assertEqual(len(dialogue_rows), 9)
        self.assertEqual(len(non_dialogue_rows), 6)
        self.assertEqual(
            {row["stable_key"] for row in dialogue_rows},
            EXPECTED_UNALIGNED_DIALOGUE_KEYS,
        )
        self.assertEqual(
            {row["stable_key"] for row in non_dialogue_rows},
            EXPECTED_UNALIGNED_NON_DIALOGUE_KEYS,
        )
        self.assertTrue(
            all(
                row["source_resolution"] == "dialogue_inventory_overlay"
                and row["chinese_text"]
                for row in dialogue_rows
            )
        )
        self.assertTrue(
            all(
                row["source_resolution"] == "reviewed_manual/direct"
                and row["chinese_text"]
                for row in non_dialogue_rows
            )
        )
        self.assertEqual(
            {row["stable_key"] for row in non_dialogue_rows},
            EXPECTED_MANUAL_SOURCE_KEYS,
        )
        expected_manual = {
            "MAIN:0x0310FB": ("0x030F99", "", "0x0310FB", "火花"),
            "MAIN:0x031A0F": ("0x03196F", "", "0x031A0F", "没有东西"),
            "MAIN:0x031E6A": ("0x031DF4", "", "0x031E6A", "小茂"),
            "MAIN:0x035F75": ("0x0300A1", "59", "0x030430", "想学会"),
            "MAIN:0x03656D": (
                "0x034AF9",
                "1063",
                "0x034CD9",
                "我相信科学的力量!现在电脑可以通信精灵和道具",
            ),
            "MAIN:0x0368F1": (
                "0x034B51",
                "1107",
                "0x03523F",
                "最近幽灵塔里好象出现幽灵...",
            ),
        }
        for key, expected in expected_manual.items():
            row = self.catalog_by_key[key]
            self.assertEqual(
                (
                    row["selected_pointer_references"],
                    row["chinese_record_indexes"],
                    row["chinese_offsets"],
                    row["chinese_text"],
                ),
                expected,
            )
            self.assertEqual(row["review_status"], "pending")
        adjudications = {
            row["stable_key"]: row
            for row in self.bundle["source_adjudications.csv"]
        }
        for key in EXPECTED_MANUAL_SOURCE_KEYS:
            self.assertEqual(
                adjudications[key]["resolution_status"],
                "source_text_resolved_manual",
            )
            self.assertTrue(
                adjudications[key]["selected_source_method"].startswith(
                    "reviewed_manual_"
                )
            )
            self.assertEqual(adjudications[key]["review_status"], "pending")
        false_high = self.catalog_by_key["MAIN:0x03F033"]
        self.assertEqual(false_high["chinese_record_indexes"], "1974")
        self.assertEqual(false_high["selected_pointer_references"], "0x03D086")
        self.assertEqual(false_high["chinese_text"], "你真是个难缠的人......")

    def test_all_eight_multi_source_targets_have_explicit_policy(self) -> None:
        modes = {
            row["stable_key"]: row["multi_source_mode"]
            for row in self.catalog
            if row["record_type"] == "MAIN"
            and row["multi_source_mode"]
        }
        self.assertEqual(set(modes), EXPECTED_MULTI_SOURCE_KEYS)
        self.assertEqual(
            {key for key, mode in modes.items() if mode == "pointer_variant_split"},
            POINTER_VARIANT_KEYS,
        )
        self.assertEqual(
            {
                key
                for key, mode in modes.items()
                if mode == "restored_reference_split"
            },
            RESTORATION_SPLIT_KEYS,
        )
        self.assertEqual(
            {key for key, mode in modes.items() if mode == "safe_shared_payload"},
            SAFE_SHARED_KEYS,
        )
        for key in RESTORATION_SPLIT_KEYS:
            row = self.catalog_by_key[key]
            all_refs = row["pointer_references"].split()
            selected_refs = row["selected_pointer_references"].split()
            self.assertEqual(len(all_refs), 2)
            self.assertEqual(len(selected_refs), 1)
            restored_ref = next(ref for ref in all_refs if ref not in selected_refs)
            self.assertIn(f"RESTORED:{restored_ref}", self.catalog_by_key)

    def test_pointer_variants_cover_shared_and_shifted_source_splits(self) -> None:
        variants = self.bundle["pointer_variants.csv"]
        self.assertEqual(len(variants), EXPECTED_POINTER_VARIANT_ROWS)
        self.assertEqual(
            Counter(row["stable_key"] for row in variants),
            Counter(
                {
                    "MAIN:0x0302FA": 2,
                    "MAIN:0x03162C": 2,
                    "MAIN:0x031A15": 3,
                }
            ),
        )
        self.assertEqual(
            {row["chinese_text"] for row in variants if row["stable_key"] == "MAIN:0x0302FA"},
            {"中剧毒了", "害怕了"},
        )
        self.assertTrue(all(not row["english_v2"] for row in variants))
        self.assertTrue(
            all(row["review_status"] == "pending" for row in variants)
        )

    def test_three_suffix_aliases_are_declared_and_annotated(self) -> None:
        overlaps = self.bundle["storage_overlaps.csv"]
        self.assertEqual(len(overlaps), len(STORAGE_OVERLAP_PAIRS))
        self.assertEqual(
            {(row["owner_key"], row["alias_key"]) for row in overlaps},
            set(STORAGE_OVERLAP_PAIRS),
        )
        for row in overlaps:
            owner = self.catalog_by_key[row["owner_key"]]
            alias = self.catalog_by_key[row["alias_key"]]
            self.assertEqual(
                owner["storage_overlap_group"], row["overlap_group"]
            )
            self.assertEqual(owner["storage_overlap_role"], "owner")
            self.assertEqual(
                alias["storage_overlap_group"], row["overlap_group"]
            )
            self.assertEqual(alias["storage_overlap_role"], "suffix_alias")

    def test_writer_requires_force_before_overwriting_editorial_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "en-US"
            write_bundle(output, self.bundle)
            with (output / "catalog.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), EXPECTED_CATALOG_ROWS)
            with self.assertRaises(FileExistsError):
                write_bundle(output, self.bundle)
            write_bundle(output, self.bundle, force=True)


if __name__ == "__main__":
    unittest.main()
