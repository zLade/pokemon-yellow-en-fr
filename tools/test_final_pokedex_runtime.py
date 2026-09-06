from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.validate_final_pokedex_runtime import (
    DEFAULT_FINAL_ROM,
    validate,
)


class FinalPokedexRuntimeValidationTests(unittest.TestCase):
    def test_current_final_rom_contains_all_159_exact_payloads(self) -> None:
        report, errors = validate()
        self.assertEqual(errors, [])
        self.assertEqual(report["result"], "PASS")
        summary = report["summary"]
        self.assertEqual(summary["expected_records"], 159)
        self.assertEqual(summary["checked_records"], 159)
        self.assertEqual(summary["accessible_records"], 151)
        self.assertEqual(summary["extended_records"], 8)
        self.assertEqual(summary["valid_layouts"], 159)
        self.assertEqual(summary["valid_pointer_ranges"], 159)
        self.assertEqual(summary["exact_payloads"], 159)
        self.assertEqual(summary["exact_terminators"], 159)
        self.assertEqual(summary["physical_lines"], 619)
        self.assertEqual(summary["word_split_boundaries"], 0)

    def test_all_eight_extended_records_are_compiled_and_exact(self) -> None:
        report, _ = validate()
        extended = [
            record
            for record in report["records"]
            if not record["accessible_in_kanto_ui"]
        ]
        self.assertEqual(
            [record["table_index"] for record in extended],
            list(range(152, 160)),
        )
        self.assertTrue(
            all(
                record["payload_exact"]
                and record["terminator_exact"]
                and not record["word_split"]
                for record in extended
            )
        )

    def test_one_corrupted_compiled_byte_is_a_hard_failure(self) -> None:
        clean_report, clean_errors = validate()
        self.assertEqual(clean_errors, [])
        first = clean_report["records"][0]
        target = int(first["compiled_target_offset"], 16)
        data = bytearray(DEFAULT_FINAL_ROM.read_bytes())
        data[target] ^= 0x01

        with tempfile.TemporaryDirectory() as directory:
            corrupt = Path(directory) / "corrupt-final.nes"
            corrupt.write_bytes(data)
            report, errors = validate(corrupt)

        self.assertEqual(report["result"], "FAIL")
        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("Pokédex #1", errors[0])
        self.assertEqual(report["summary"]["exact_payloads"], 158)


if __name__ == "__main__":
    unittest.main()
