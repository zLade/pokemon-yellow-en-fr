#!/usr/bin/env python3
"""Contract tests for the locale-neutral pointer inventory."""

from __future__ import annotations

import hashlib
import json
import unittest

from tools.pin_structural_pointer_inventory import (
    DEFAULT_OUTPUT,
    EXPECTED_PROVENANCE,
    EXPECTED_RECORDS,
    canonical_json,
)


class StructuralPointerInventoryTests(unittest.TestCase):
    def test_versioned_inventory_has_exact_partition_and_commitment(self) -> None:
        document = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        records = document["records"]
        self.assertEqual(len(records), EXPECTED_RECORDS)
        self.assertEqual(
            len({row["reference"] for row in records}),
            EXPECTED_RECORDS,
        )
        self.assertEqual(
            document["summary"]["by_provenance"],
            EXPECTED_PROVENANCE,
        )
        self.assertEqual(
            document["summary"]["records_sha256"],
            hashlib.sha256(canonical_json(records)).hexdigest(),
        )
        self.assertEqual(
            sum(row["kind"] == "restoration" for row in records),
            85,
        )

    def test_inventory_contains_no_localized_final_payload_fields(self) -> None:
        document = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
        forbidden = {
            "final_target",
            "cpu_address",
            "payload_length",
            "payload_sha256",
            "french_text",
        }
        for record in document["records"]:
            self.assertTrue(forbidden.isdisjoint(record))


if __name__ == "__main__":
    unittest.main()
