#!/usr/bin/env python3
"""Coverage regressions for the exhaustive French live-text review."""

from __future__ import annotations

import unittest
from pathlib import Path

from rom_traduction_assistant import (
    DEFAULT_FRENCH_POINTER_VARIANTS,
    TRANSLATION_BASE_ROM,
)
from tools.audit_full_french_text import (
    CERTAIN_TEXT_CORRECTION_OFFSETS,
    DEFAULT_MOVE_LABEL_CATALOGUE,
    EXPECTED_REVIEWED_UNIT_COUNT,
    build_full_review,
)


ROOT = Path(__file__).resolve().parent.parent


class FullFrenchTextReviewTests(unittest.TestCase):
    def test_current_live_inventory_is_complete_and_has_no_high_signal(self) -> None:
        inventory, summary, errors = build_full_review(
            csv_path=ROOT / "traduction_base.csv",
            input_rom_path=ROOT / TRANSLATION_BASE_ROM,
            move_labels_path=DEFAULT_MOVE_LABEL_CATALOGUE,
            pointer_variants_path=DEFAULT_FRENCH_POINTER_VARIANTS,
            dialogue_review_path=ROOT / "LISTE_EXHAUSTIVE_DIALOGUES.csv",
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(inventory), EXPECTED_REVIEWED_UNIT_COUNT)
        self.assertEqual(summary["status"], "PASS")
        self.assertEqual(summary["quality_heuristics"]["high"], 0)
        self.assertEqual(summary["counts_by_kind"]["script"], 1846)
        self.assertEqual(summary["counts_by_kind"]["fixed_live_text"], 3)
        self.assertEqual(summary["counts_by_kind"]["restoration"], 85)
        self.assertEqual(summary["counts_by_kind"]["move_graphic"], 94)
        self.assertEqual(summary["counts_by_kind"]["pointer_variant"], 3)
        self.assertEqual(len(CERTAIN_TEXT_CORRECTION_OFFSETS), 76)
        self.assertEqual(
            summary["corrections_this_review"]["live_source_entries"],
            76,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "fixed_runtime_records_patched_by_builder"
            ],
            1,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "status_already_control_flow_patches"
            ],
            1,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "battle_clear_width_patches"
            ],
            1,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "dynamic_pointer_entries_classified"
            ],
            101,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "live_dynamic_compositions_width_gated"
            ],
            97,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "dead_dynamic_pointer_entries"
            ],
            4,
        )
        self.assertEqual(
            summary["corrections_this_review"][
                "item_table_entries_width_gated"
            ],
            40,
        )


if __name__ == "__main__":
    unittest.main()
