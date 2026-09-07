#!/usr/bin/env python3
"""Tests for the final critical-restoration runtime target map."""

from __future__ import annotations

import hashlib
import unittest

from tools.prepare_critical_restoration_runtime import (
    CASES,
    CriticalRestorationRuntimeError,
    build_rows,
    render,
)


class CriticalRestorationRuntimeMapTests(unittest.TestCase):
    def fixtures(self) -> tuple[dict[str, object], bytes]:
        rom = bytearray(0x40010)
        records: list[dict[str, object]] = []
        case_targets = {
            "pair6": iter((0x030010, 0x030020, 0x030030)),
        }
        for group, stable_key, harness_reference in CASES:
            target = next(case_targets[group])
            payload = stable_key.encode("ascii")[-5:]
            rom[target : target + len(payload)] = payload
            rom[target + len(payload)] = 0x0D
            records.append(
                {
                    "kind": "restoration",
                    "reference": f"0x{harness_reference:06X}",
                    "stable_key": stable_key,
                    "final_target": f"0x{target:06X}",
                    "payload_length": len(payload),
                    "payload_sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        records.extend(
            {
                "kind": "ordinary",
                "stable_key": f"MAIN:fixture-{index}",
                "final_target": "0x030100",
                "payload_length": 1,
                "payload_sha256": hashlib.sha256(b"\0").hexdigest(),
            }
            for index in range(1912 - len(records))
        )
        manifest = {
            "result": "PASS",
            "inputs": {"rom": {"sha256": "ab" * 32}},
            "records": records,
        }
        return manifest, bytes(rom)

    def test_exact_three_cases_are_bound_to_same_pair_harnesses(self) -> None:
        manifest, rom = self.fixtures()
        rows = build_rows(manifest, rom)
        self.assertEqual(len(rows), 3)
        self.assertEqual({row["group"] for row in rows}, {"pair6"})
        self.assertIn(
            "schema\tnj046-en2-critical-restoration-runtime/v1",
            render(manifest, rows),
        )

    def test_cross_pair_target_is_fatal(self) -> None:
        manifest, rom = self.fixtures()
        manifest["records"][0]["final_target"] = "0x038010"  # type: ignore[index]
        with self.assertRaisesRegex(CriticalRestorationRuntimeError, "cannot be reached"):
            build_rows(manifest, rom)


if __name__ == "__main__":
    unittest.main()
