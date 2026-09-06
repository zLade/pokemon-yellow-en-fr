from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.validate_english_bank_budget import (
    EnglishBankBudgetError,
    validate_budget,
)


ALLOC_FIELDS = (
    "record_type",
    "stable_key",
    "source_pair",
    "target_pair",
    "physical_bytes",
    "payload_bytes",
    "pointer_reference_count",
)
BUDGET_FIELDS = (
    "prg_pair",
    "initial_free_bytes",
    "allocated_physical_bytes",
    "remaining_free_bytes",
    "initial_span_count",
    "remaining_span_count",
    "largest_remaining_span",
)


class EnglishBankBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.allocation = self.root / "allocation.csv"
        self.budget = self.root / "budget.csv"
        self.policy = self.root / "policy.json"
        with self.allocation.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=ALLOC_FIELDS)
            writer.writeheader()
            writer.writerows([
                {
                    "record_type": "MAIN",
                    "stable_key": "MAIN:0x030100",
                    "source_pair": 6,
                    "target_pair": 6,
                    "physical_bytes": 60,
                    "payload_bytes": 59,
                    "pointer_reference_count": 2,
                },
                {
                    "record_type": "RESTORED",
                    "stable_key": "RESTORED:0x038000",
                    "source_pair": 7,
                    "target_pair": 7,
                    "physical_bytes": 40,
                    "payload_bytes": 39,
                    "pointer_reference_count": 1,
                },
            ])
        with self.budget.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=BUDGET_FIELDS)
            writer.writeheader()
            writer.writerows([
                {
                    "prg_pair": 6,
                    "initial_free_bytes": 160,
                    "allocated_physical_bytes": 60,
                    "remaining_free_bytes": 100,
                    "initial_span_count": 2,
                    "remaining_span_count": 1,
                    "largest_remaining_span": 80,
                },
                {
                    "prg_pair": 7,
                    "initial_free_bytes": 240,
                    "allocated_physical_bytes": 40,
                    "remaining_free_bytes": 200,
                    "initial_span_count": 3,
                    "remaining_span_count": 2,
                    "largest_remaining_span": 120,
                },
            ])
        self.policy.write_text(json.dumps({
            "schema": "nj046-en2-bank-budget-policy/v1",
            "rationale": "English thresholds measured independently.",
            "pairs": {
                "6": {
                    "minimum_remaining_free_bytes": 64,
                    "minimum_largest_remaining_span": 32,
                },
                "7": {
                    "minimum_remaining_free_bytes": 128,
                    "minimum_largest_remaining_span": 64,
                },
            },
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_consistent_reports_and_pair_specific_floors_pass(self) -> None:
        report = validate_budget(self.allocation, self.budget, self.policy)
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["logical_allocations"], 2)
        self.assertEqual(report["pairs"]["6"]["remaining_free_bytes"], 100)

    def test_cross_pair_allocation_is_fatal(self) -> None:
        text = self.allocation.read_text(encoding="utf-8")
        self.allocation.write_text(text.replace("6,6,60", "6,7,60"), encoding="utf-8")
        with self.assertRaisesRegex(EnglishBankBudgetError, "cross-pair"):
            validate_budget(self.allocation, self.budget, self.policy)

    def test_zero_rows_for_other_prg_pairs_are_accepted(self) -> None:
        with self.budget.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=BUDGET_FIELDS)
            writer.writerow({field: 0 for field in BUDGET_FIELDS})
        report = validate_budget(self.allocation, self.budget, self.policy)
        self.assertEqual(report["result"], "PASS")

    def test_nonzero_budget_outside_text_pairs_is_fatal(self) -> None:
        with self.budget.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=BUDGET_FIELDS)
            row = {field: 0 for field in BUDGET_FIELDS}
            row["prg_pair"] = 5
            row["initial_free_bytes"] = 1
            writer.writerow(row)
        with self.assertRaisesRegex(
            EnglishBankBudgetError, "outside pairs 6/7"
        ):
            validate_budget(self.allocation, self.budget, self.policy)

    def test_floor_and_accounting_regressions_are_fatal(self) -> None:
        policy = json.loads(self.policy.read_text(encoding="utf-8"))
        policy["pairs"]["6"]["minimum_remaining_free_bytes"] = 101
        self.policy.write_text(json.dumps(policy), encoding="utf-8")
        with self.assertRaisesRegex(EnglishBankBudgetError, "below floor"):
            validate_budget(self.allocation, self.budget, self.policy)


if __name__ == "__main__":
    unittest.main()
