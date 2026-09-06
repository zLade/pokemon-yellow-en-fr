#!/usr/bin/env python3
"""Tests for deterministic EN2 review batches and guarded merging."""

from __future__ import annotations

import unittest

from tools.english_review_workflow import (
    RELEASE_REVIEW_STATUS,
    ReviewWorkflowError,
    build_batches,
    merge_reviews,
)


def row(key: str, **updates: str) -> dict[str, str]:
    base = {
        "stable_key": key,
        "record_type": "MAIN",
        "entry_index": "1",
        "dialogue_id": "",
        "category": "Ordinary text",
        "source_offset_or_pointer": "0x030100",
        "pointer_references": "0x030001",
        "selected_pointer_references": "0x030001",
        "layout": "",
        "speaker": "",
        "chinese_text": "你好",
        "english_2015": "Hello",
        "french_v2_gloss": "Bonjour",
        "alignment_method": "pointer_table",
        "alignment_confidence": "high",
        "source_resolution": "pointer_table",
        "review_status": "pending",
        "english_v2": "Hello",
        "editorial_origin": "english_2015_unreviewed_seed",
        "encoded_length": "5",
        "compression": "",
        "compression_justification": "",
        "fidelity_comment": "",
        "source_capacity_bytes": "10",
        "multi_source_mode": "",
    }
    base.update(updates)
    return base


def review(key: str, text: str = "Hello") -> dict[str, object]:
    return {
        "stable_key": key,
        "english_v2": text,
        "editorial_origin": "translated_directly_from_chinese",
        "fidelity_comment": "Meaning checked against the Chinese source.",
        "compression": False,
        "compression_justification": "",
    }


class EnglishReviewWorkflowTests(unittest.TestCase):
    def test_batches_are_deterministic_and_only_export_pending_rows(self) -> None:
        rows = [
            row("MAIN:0x030100"),
            row("MAIN:0x030101", review_status=RELEASE_REVIEW_STATUS),
            row("MAIN:0x030102"),
        ]
        batches = build_batches(rows, batch_size=1)
        self.assertEqual(
            [batch["batch_id"] for batch in batches],
            ["other-001", "other-002"],
        )
        self.assertEqual(
            [batch["entries"][0]["stable_key"] for batch in batches],
            ["MAIN:0x030100", "MAIN:0x030102"],
        )

    def test_batches_group_dialogue_pokedex_and_other_domains(self) -> None:
        rows = [
            row("MAIN:0x030100", layout="pokedex_13x4"),
            row("MAIN:0x030101", layout="dialogue_19_19"),
            row("MAIN:0x030102"),
            row(
                "MAIN:0x030103",
                multi_source_mode="pointer_variant_split",
            ),
        ]
        batches = build_batches(rows, batch_size=10)
        self.assertEqual(
            [batch["batch_id"] for batch in batches],
            ["dialogue-001", "pokedex-001", "other-001"],
        )
        exported_keys = {
            entry["stable_key"]
            for batch in batches
            for entry in batch["entries"]
        }
        self.assertNotIn("MAIN:0x030103", exported_keys)

    def test_explicit_exclusions_are_left_for_a_later_review_wave(self) -> None:
        batches = build_batches(
            [row("MAIN:0x030100"), row("MAIN:0x030101")],
            batch_size=100,
            exclude_keys={"MAIN:0x030101"},
        )
        self.assertEqual(
            [entry["stable_key"] for entry in batches[0]["entries"]],
            ["MAIN:0x030100"],
        )

    def test_merge_sets_traceable_fields_and_encoded_length(self) -> None:
        merged = merge_reviews(
            [row("MAIN:0x030100")],
            {"MAIN:0x030100": review("MAIN:0x030100", "Pokémon")},
        )
        self.assertEqual(merged[0]["english_v2"], "Pokémon")
        self.assertEqual(merged[0]["encoded_length"], "7")
        self.assertEqual(merged[0]["review_status"], RELEASE_REVIEW_STATUS)
        self.assertEqual(merged[0]["compression"], "no")

    def test_strict_codec_and_layout_errors_are_fatal(self) -> None:
        with self.assertRaisesRegex(ReviewWorkflowError, "invalid English"):
            merge_reviews(
                [row("MAIN:0x030100")],
                {"MAIN:0x030100": review("MAIN:0x030100", "literal @")},
            )
        with self.assertRaisesRegex(ReviewWorkflowError, "invalid English"):
            merge_reviews(
                [row("MAIN:0x030100", layout="pokedex_13x4")],
                {
                    "MAIN:0x030100": review(
                        "MAIN:0x030100",
                        "aaaaaaaaaaaaa bbbbbbbbbbbbb ccccccccccccc "
                        "ddddddddddddd eeeeeeeeeeeee",
                    )
                },
            )

    def test_unresolved_or_empty_chinese_source_cannot_be_reviewed(self) -> None:
        for updates, message in (
            ({"chinese_text": ""}, "Chinese source is empty"),
            ({"source_resolution": "unaligned"}, "still unaligned"),
        ):
            with self.subTest(updates=updates):
                with self.assertRaisesRegex(ReviewWorkflowError, message):
                    merge_reviews(
                        [row("MAIN:0x030100", **updates)],
                        {"MAIN:0x030100": review("MAIN:0x030100")},
                    )

    def test_unknown_duplicates_and_silent_overwrites_are_rejected(self) -> None:
        with self.assertRaisesRegex(ReviewWorkflowError, "unknown reviewed"):
            merge_reviews(
                [row("MAIN:0x030100")],
                {"MAIN:0x039999": review("MAIN:0x039999")},
            )
        with self.assertRaisesRegex(ReviewWorkflowError, "already reviewed"):
            merge_reviews(
                [row("MAIN:0x030100", review_status=RELEASE_REVIEW_STATUS)],
                {"MAIN:0x030100": review("MAIN:0x030100")},
            )

    def test_compression_requires_an_explicit_reason(self) -> None:
        compressed = review("MAIN:0x030100")
        compressed["compression"] = True
        with self.assertRaisesRegex(ReviewWorkflowError, "needs a justification"):
            merge_reviews(
                [row("MAIN:0x030100")],
                {"MAIN:0x030100": compressed},
            )


if __name__ == "__main__":
    unittest.main()
