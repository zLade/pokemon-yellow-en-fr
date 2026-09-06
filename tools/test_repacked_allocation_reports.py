from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from rom_traduction_assistant import (
    FreeSpan,
    allocation_report_rows,
    write_allocation_report,
    write_bank_budget_report,
)


class RepackedAllocationReportTests(unittest.TestCase):
    def test_suffix_pool_is_charged_once(self) -> None:
        main = 0x030100
        restored = 0x030200
        variant = 0x030300
        rows = allocation_report_rows(
            allocation_payloads={
                main: b"Hyper Potion",
                restored: b"Potion",
                variant: b"Potion",
            },
            allocations={
                main: 0x031000,
                restored: 0x031006,
                variant: 0x031006,
            },
            main_offsets={main},
            restoration_offsets={restored},
            pointer_variant_offsets={variant},
            pointer_counts={main: 4},
        )
        self.assertEqual([row["record_type"] for row in rows], [
            "MAIN",
            "RESTORED",
            "POINTER_VARIANT",
        ])
        self.assertEqual(sum(int(row["physical_bytes"]) for row in rows), 13)
        self.assertEqual(rows[0]["pointer_reference_count"], 4)
        self.assertEqual(rows[1]["suffix_delta"], 6)
        self.assertEqual(rows[2]["pool_host_offset_hex"], "0x030100")

    def test_csv_reports_have_deterministic_totals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            allocation_path = root / "allocation.csv"
            budget_path = root / "budget.csv"
            rows = allocation_report_rows(
                allocation_payloads={0x030100: b"Text"},
                allocations={0x030100: 0x031000},
                main_offsets={0x030100},
                restoration_offsets=set(),
                pointer_variant_offsets=set(),
                pointer_counts={0x030100: 2},
            )
            write_allocation_report(allocation_path, rows)
            write_bank_budget_report(
                budget_path,
                initial_spans={6: ((0x031000, 20),), 7: ((0x039000, 10),)},
                remaining_spans={
                    6: [FreeSpan(0x031005, 15)],
                    7: [FreeSpan(0x039000, 10)],
                },
            )
            with allocation_path.open(encoding="utf-8", newline="") as handle:
                allocation = list(csv.DictReader(handle))
            with budget_path.open(encoding="utf-8", newline="") as handle:
                budget = list(csv.DictReader(handle))
            self.assertEqual(allocation[0]["physical_bytes"], "5")
            self.assertEqual(budget[0]["allocated_physical_bytes"], "5")
            self.assertEqual(budget[0]["remaining_free_bytes"], "15")
            self.assertEqual(budget[1]["allocated_physical_bytes"], "0")


if __name__ == "__main__":
    unittest.main()
