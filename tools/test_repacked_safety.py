#!/usr/bin/env python3
"""Safety regressions for the translated-text repack."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    FINAL_ROM,
    TRANSLATION_BASE_ROM,
    load_french_pointer_variants,
    verified_dialogue_restoration_payloads,
)
from tools.dialogue_layout import format_game_text  # noqa: E402
from tools.validate_repacked import build_parser, compute_plan  # noqa: E402


INES_HEADER_SIZE = 16
PRG_BANK_SIZE = 0x8000
TAIL_SIZE = 64
TEXT_BANKS = (6, 7)
EXPECTED_TAIL_SHA256 = (
    "56b6d6893d45a154c5caaacd89ceceba"
    "a32c4dc87b1ad50984ec67f503699871"
)
FINAL_ROM_UNDER_TEST = Path(
    os.environ.get(
        "POKEMON_FINAL_ROM_UNDER_TEST",
        str(ROM_DIR / FINAL_ROM),
    )
)


def bank_tail_range(bank: int) -> tuple[int, int]:
    end = INES_HEADER_SIZE + (bank + 1) * PRG_BANK_SIZE
    return end - TAIL_SIZE, end


def intersects(
    start: int,
    end: int,
    protected_start: int,
    protected_end: int,
) -> bool:
    return start < protected_end and end > protected_start


class RepackedTailSafetyTests(unittest.TestCase):
    def test_final_rom_preserves_text_bank_tail_hashes(self) -> None:
        base = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        rebuilt = FINAL_ROM_UNDER_TEST.read_bytes()
        self.assertEqual(len(rebuilt), len(base))

        for bank in TEXT_BANKS:
            with self.subTest(bank=bank):
                start, end = bank_tail_range(bank)
                base_tail = base[start:end]
                rebuilt_tail = rebuilt[start:end]
                self.assertEqual(
                    hashlib.sha256(base_tail).hexdigest(),
                    EXPECTED_TAIL_SHA256,
                )
                self.assertEqual(
                    hashlib.sha256(rebuilt_tail).hexdigest(),
                    EXPECTED_TAIL_SHA256,
                )
                self.assertEqual(rebuilt_tail, base_tail)

    def test_default_plan_never_uses_text_bank_tails(self) -> None:
        args = build_parser().parse_args([])
        (
            original,
            row_info,
            row_pointer_refs,
            allocations,
            failures,
            _,
            _,
        ) = compute_plan(args)
        self.assertFalse(failures)

        row_by_offset = {
            row.offset: encoded
            for row, _, encoded in row_info
        }
        restoration_payloads = verified_dialogue_restoration_payloads(
            original
        )
        row_by_offset.update(restoration_payloads)
        row_layouts = {row.offset: row.layout for row, _, _ in row_info}
        pointer_variant_payloads = {
            variant.pointer_reference: format_game_text(
                variant.text,
                row_layouts[main_offset],
            )
            for main_offset, variants in load_french_pointer_variants().items()
            for variant in variants[1:]
        }
        row_by_offset.update(pointer_variant_payloads)
        tail_ranges = {
            bank: bank_tail_range(bank)
            for bank in TEXT_BANKS
        }

        for old_offset, new_offset in allocations.items():
            allocation_end = new_offset + len(row_by_offset[old_offset]) + 1
            for bank, (tail_start, tail_end) in tail_ranges.items():
                with self.subTest(
                    kind="allocation",
                    bank=bank,
                    old_offset=f"0x{old_offset:06X}",
                ):
                    self.assertFalse(
                        intersects(
                            new_offset,
                            allocation_end,
                            tail_start,
                            tail_end,
                        )
                    )

        pointer_refs = {
            ref
            for target_refs in row_pointer_refs.values()
            for _, refs in target_refs
            for ref in refs
        }
        pointer_refs.update(restoration_payloads)
        pointer_refs.update(pointer_variant_payloads)
        for ref in pointer_refs:
            for bank, (tail_start, tail_end) in tail_ranges.items():
                with self.subTest(
                    kind="pointer-reference",
                    bank=bank,
                    ref=f"0x{ref:06X}",
                ):
                    self.assertFalse(
                        intersects(ref, ref + 2, tail_start, tail_end)
                    )


class RepackedCliSafetyTests(unittest.TestCase):
    def test_oversized_translation_fails_without_outputs(self) -> None:
        source_csv = ROM_DIR / "traduction_base.csv"
        with source_csv.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames
            rows = list(reader)
        self.assertIsNotNone(fieldnames)

        target = next(
            row
            for row in rows
            if row["offset_hex"].lower() == "0x03041d"
        )
        target["fr_text"] = "A" * (PRG_BANK_SIZE * 2)

        with tempfile.TemporaryDirectory(
            prefix="pokemon-repack-safety-"
        ) as temporary:
            temp_dir = Path(temporary)
            oversized_csv = temp_dir / "oversized.csv"
            output_rom = temp_dir / "must-not-exist.nes"
            output_ips = temp_dir / "must-not-exist.ips"
            overflow_report = temp_dir / "must-not-exist.csv"

            with oversized_csv.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            for command in ("build", "build-repointed", "build-repacked"):
                with self.subTest(command=command):
                    output_rom.unlink(missing_ok=True)
                    output_ips.unlink(missing_ok=True)
                    overflow_report.unlink(missing_ok=True)
                    arguments = [
                        sys.executable,
                        "-B",
                        str(ROM_DIR / "rom_traduction_assistant.py"),
                        command,
                        "--csv",
                        str(oversized_csv),
                        "--input-rom",
                        str(ROM_DIR / TRANSLATION_BASE_ROM),
                        "--output-rom",
                        str(output_rom),
                        "--output-ips",
                        str(output_ips),
                    ]
                    if command == "build-repacked":
                        arguments.extend(
                            [
                                "--fixed-overflow-output",
                                str(overflow_report),
                            ]
                        )
                    result = subprocess.run(
                        arguments,
                        cwd=ROM_DIR,
                        capture_output=True,
                        text=True,
                        timeout=60,
                        check=False,
                    )
                    diagnostic = (
                        f"returncode={result.returncode}\n"
                        f"stdout:\n{result.stdout}\n"
                        f"stderr:\n{result.stderr}"
                    )
                    self.assertNotEqual(
                        result.returncode,
                        0,
                        diagnostic,
                    )
                    self.assertFalse(output_rom.exists(), diagnostic)
                    self.assertFalse(output_ips.exists(), diagnostic)
                    self.assertFalse(
                        overflow_report.exists(),
                        diagnostic,
                    )

    def test_validator_rejects_single_unplanned_bank_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="pokemon-repack-validator-"
        ) as temporary:
            temp_dir = Path(temporary)
            output_rom = temp_dir / "candidate.nes"
            output_ips = temp_dir / "candidate.ips"
            overflow_report = temp_dir / "fixed-overflow.csv"
            build = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROM_DIR / "rom_traduction_assistant.py"),
                    "build-repacked",
                    "--csv",
                    str(ROM_DIR / "traduction_base.csv"),
                    "--input-rom",
                    str(ROM_DIR / TRANSLATION_BASE_ROM),
                    "--output-rom",
                    str(output_rom),
                    "--output-ips",
                    str(output_ips),
                    "--fixed-overflow-output",
                    str(overflow_report),
                ],
                cwd=ROM_DIR,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            self.assertEqual(
                build.returncode,
                0,
                f"stdout:\n{build.stdout}\nstderr:\n{build.stderr}",
            )

            candidate = bytearray(output_rom.read_bytes())
            tail_start, _ = bank_tail_range(6)
            candidate[tail_start] ^= 0x01
            output_rom.write_bytes(candidate)

            validation = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROM_DIR / "tools" / "validate_repacked.py"),
                    "--rom",
                    str(output_rom),
                    "--csv",
                    str(ROM_DIR / "traduction_base.csv"),
                    "--input-rom",
                    str(ROM_DIR / TRANSLATION_BASE_ROM),
                    "--fixed-overflow",
                    str(overflow_report),
                ],
                cwd=ROM_DIR,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            diagnostic = (
                f"returncode={validation.returncode}\n"
                f"stdout:\n{validation.stdout}\n"
                f"stderr:\n{validation.stderr}"
            )
            self.assertNotEqual(validation.returncode, 0, diagnostic)
            self.assertIn("tail code", validation.stdout, diagnostic)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--final-rom",
        default=str(FINAL_ROM_UNDER_TEST),
    )
    test_args, unittest_args = parser.parse_known_args()
    FINAL_ROM_UNDER_TEST = Path(test_args.final_rom).resolve()
    unittest.main(argv=[sys.argv[0], *unittest_args])
