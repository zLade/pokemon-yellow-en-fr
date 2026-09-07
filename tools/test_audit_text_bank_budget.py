#!/usr/bin/env python3
"""Unit tests for the text-bank capacity gate."""

from __future__ import annotations

import argparse
import unittest

from tools.audit_text_bank_budget import (
    BudgetFloor,
    check_floors,
    parse_floor,
    summarize_pair,
)
from tools.rom_builder import FreeSpan


class BudgetSummaryTests(unittest.TestCase):
    def test_summary_reports_residual_capacity_and_fragmentation(self) -> None:
        summary = summarize_pair(
            [FreeSpan(0x100, 10), FreeSpan(0x200, 30)],
            allocation_count=17,
        )

        self.assertEqual(summary.free_bytes, 40)
        self.assertEqual(summary.largest_block, 30)
        self.assertEqual(summary.fragment_count, 2)
        self.assertEqual(summary.fragmentation_ratio, 0.25)
        self.assertEqual(summary.allocation_count, 17)

    def test_empty_pair_is_well_defined(self) -> None:
        summary = summarize_pair([], allocation_count=0)
        self.assertEqual(summary.free_bytes, 0)
        self.assertEqual(summary.largest_block, 0)
        self.assertEqual(summary.fragmentation_ratio, 0.0)


class BudgetFloorTests(unittest.TestCase):
    def test_floor_checks_total_and_contiguous_capacity(self) -> None:
        budgets = {
            6: summarize_pair(
                [FreeSpan(0x100, 8), FreeSpan(0x200, 24)],
                allocation_count=2,
            )
        }
        errors = check_floors(budgets, [BudgetFloor(6, 40, 32)])

        self.assertEqual(len(errors), 2)
        self.assertIn("32 octets libres", errors[0])
        self.assertIn("plus grand bloc 24", errors[1])

    def test_missing_pair_fails_nonzero_floor(self) -> None:
        errors = check_floors({}, [BudgetFloor(7, 1, 1)])
        self.assertEqual(len(errors), 2)

    def test_floor_parser_rejects_malformed_or_negative_values(self) -> None:
        self.assertEqual(parse_floor("6:80:24"), BudgetFloor(6, 80, 24))
        for value in ("6:80", "x:80:24", "6:-1:24"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_floor(value)


if __name__ == "__main__":
    unittest.main()
