#!/usr/bin/env python3
"""Targeted regressions for the exhaustive translation coverage audit."""

from __future__ import annotations

import contextlib
import csv
import io
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    FINAL_ROM,
    PATCH_SCRIPT,
    TRANSLATION_BASE_ROM,
    cpu_addr_for_offset,
    offset_for_cpu_addr,
    pair_for_offset,
    parse_patch_entries,
    verified_all_graphical_text_records,
)
from tools.audit_translation_coverage import (  # noqa: E402
    REVIEWED_ASCII_REMAINDERS,
    REVIEWED_LANGUAGE_NEUTRAL_GLYPH_RECORDS,
    audit,
    build_parser,
    raw_pointer_refs,
    validate_csv_sync,
)
from tools.glyph_text_tools import (  # noqa: E402
    FONT_BASE_OFFSET,
    FONT_SLOT_SIZE,
    glyph_slot,
)


class TranslationCoverageTests(unittest.TestCase):
    def test_english_battle_move_labels_fit_the_runtime_grid(self) -> None:
        catalogue_path = ROM_DIR / "locales" / "en-US" / "catalog.csv"
        with catalogue_path.open(
            newline="", encoding="utf-8-sig"
        ) as handle:
            rows = list(csv.DictReader(handle))

        move_table_start = 0x030F99
        move_table_end = 0x0310FB
        labels_by_reference: dict[int, tuple[str, str]] = {}
        for row in rows:
            for token in re.findall(
                r"0x[0-9A-Fa-f]+", row["pointer_references"]
            ):
                reference = int(token, 16)
                if move_table_start <= reference < move_table_end:
                    labels_by_reference[reference] = (
                        row["stable_key"],
                        row["english_v2"],
                    )

        self.assertGreaterEqual(len(labels_by_reference), 160)
        overflows = {
            reference: (stable_key, label)
            for reference, (stable_key, label) in labels_by_reference.items()
            if len(label) > 8
        }
        self.assertEqual(overflows, {})
        labels = [label for _, label in labels_by_reference.values()]
        self.assertEqual(len(labels), len(set(labels)))
        thunder_shock = next(
            row for row in rows if row["stable_key"] == "MAIN:0x031186"
        )
        self.assertEqual(thunder_shock["english_v2"], "ThndrShk")

    def test_dead_mist_ball_ascii_residue_is_structurally_locked(
        self,
    ) -> None:
        english = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
        final = (ROM_DIR / FINAL_ROM).read_bytes()

        move_table_directory_ref = 0x030014
        move_table_start = 0x030F99
        move_table_end = 0x0310FB
        move_table_count = 177
        mist_pointer_ref = 0x031067
        psyshock_pointer_ref = 0x031069
        mist_record = 0x03140B
        dead_ball_record = 0x031410
        psyshock_record = 0x031415

        self.assertEqual(
            int.from_bytes(
                english[
                    move_table_directory_ref:
                    move_table_directory_ref + 2
                ],
                "little",
            ),
            cpu_addr_for_offset(move_table_start),
        )
        self.assertEqual(
            move_table_end - move_table_start,
            move_table_count * 2,
        )
        self.assertEqual(
            english[move_table_end:move_table_end + 6],
            b"Ember\x0D",
        )

        pair = pair_for_offset(move_table_start)
        targets = []
        for ref in range(move_table_start, move_table_end, 2):
            target = offset_for_cpu_addr(
                pair,
                int.from_bytes(english[ref:ref + 2], "little"),
                len(english),
            )
            self.assertIsNotNone(target)
            targets.append(target)
        self.assertEqual(len(targets), move_table_count)
        self.assertEqual(targets[0], move_table_end)
        self.assertEqual(targets[-1], 0x031635)
        self.assertEqual(targets[103], mist_record)
        self.assertEqual(targets[104], psyshock_record)
        self.assertNotIn(dead_ball_record, targets)
        self.assertEqual(
            english[mist_pointer_ref:mist_pointer_ref + 2],
            cpu_addr_for_offset(mist_record).to_bytes(2, "little"),
        )
        self.assertEqual(
            english[psyshock_pointer_ref:psyshock_pointer_ref + 2],
            cpu_addr_for_offset(psyshock_record).to_bytes(2, "little"),
        )
        self.assertEqual(raw_pointer_refs(english, dead_ball_record), [])

        self.assertEqual(
            english[mist_record:psyshock_record],
            b"\xB5\x97\xB5\x99\x0DBall\x0D",
        )
        expected_tiles = {
            "M": bytes.fromhex("0082C6AA92828282") + b"\0" * 8,
            "i": bytes.fromhex("0010001010101010") + b"\0" * 8,
            "B": bytes.fromhex("00F88484FC8282FC") + b"\0" * 8,
            "a": bytes.fromhex("00000038043C443E") + b"\0" * 8,
            "s": bytes.fromhex("0000003C403C027C") + b"\0" * 8,
            "t": bytes.fromhex("0000107C1010100C") + b"\0" * 8,
            "l": bytes.fromhex("0000101010101010") + b"\0" * 8,
        }
        rendered_letters = (
            (0xB5, 0x97, (("M", "i"), ("B", "a"))),
            (0xB5, 0x99, (("s", "t"), ("l", "l"))),
        )
        for high, low, rows in rendered_letters:
            slot = glyph_slot(high, low)
            for row_index, letters in enumerate(rows):
                raw_start = (
                    FONT_BASE_OFFSET
                    + (slot + row_index) * FONT_SLOT_SIZE
                )
                raw = english[raw_start:raw_start + FONT_SLOT_SIZE]
                self.assertEqual(
                    raw[:16],
                    expected_tiles[letters[0]],
                )
                self.assertEqual(
                    raw[16:],
                    expected_tiles[letters[1]],
                )

        self.assertEqual(
            REVIEWED_ASCII_REMAINDERS[dead_ball_record][1],
            "dead_unreferenced_english_patch_residue",
        )

        final_targets = []
        for ref in range(move_table_start, move_table_end, 2):
            final_targets.append(
                offset_for_cpu_addr(
                    pair,
                    int.from_bytes(final[ref:ref + 2], "little"),
                    len(final),
                )
            )
        self.assertNotIn(dead_ball_record, final_targets)
        final_mist = final_targets[103]
        final_psyshock = final_targets[104]
        self.assertIsNotNone(final_mist)
        self.assertIsNotNone(final_psyshock)
        self.assertEqual(
            final[final_mist:final.index(0x0D, final_mist)],
            b"Ball'Brume",
        )
        self.assertEqual(
            final[
                final_psyshock:
                final.index(0x0D, final_psyshock)
            ],
            b"Choc Psy",
        )

    def dump_current_script(
        self,
        directory: Path,
        english_rom: Path | None = None,
    ) -> Path:
        csv_path = directory / "traduction_base.csv"
        overflow_path = directory / "traductions_trop_longues.csv"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROM_DIR / "rom_traduction_assistant.py"),
                "dump-script",
                "--english-rom",
                str(english_rom or ROM_DIR / TRANSLATION_BASE_ROM),
                "--output",
                str(csv_path),
                "--overflow-output",
                str(overflow_path),
            ],
            cwd=ROM_DIR,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"dump-script failed:\n{result.stdout}\n{result.stderr}",
        )
        self.assertTrue(csv_path.is_file())
        return csv_path

    def run_audit(
        self,
        directory: Path,
        *,
        candidate: Path,
        csv_path: Path,
        english_rom: Path | None = None,
    ) -> tuple[int, str]:
        args = build_parser().parse_args(
            [
                "--rom",
                str(candidate),
                "--csv",
                str(csv_path),
                "--english-rom",
                str(english_rom or ROM_DIR / TRANSLATION_BASE_ROM),
                "--chinese-rom",
                str(ROM_DIR / CHINESE_ROM),
                "--ascii-report",
                str(directory / "ascii.csv"),
                "--glyph-report",
                str(directory / "glyphs.csv"),
            ]
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = audit(args)
        return result, output.getvalue()

    def test_dumped_csv_is_synchronized_with_script(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="pokemon-coverage-csv-"
        ) as temporary:
            temp_dir = Path(temporary)
            csv_path = self.dump_current_script(temp_dir)
            english = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()

            self.assertEqual(validate_csv_sync(english, csv_path), [])

    def test_candidate_glyph_record_mutation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="pokemon-coverage-glyph-"
        ) as temporary:
            temp_dir = Path(temporary)
            csv_path = self.dump_current_script(temp_dir)
            english = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
            records = verified_all_graphical_text_records(english)
            neutral_index = min(
                REVIEWED_LANGUAGE_NEUTRAL_GLYPH_RECORDS
            )
            glyph_start, _, _, _ = records[neutral_index - 1]
            candidate = bytearray(english)
            candidate[glyph_start] ^= 0x01
            candidate_path = temp_dir / "mutated-glyph.nes"
            candidate_path.write_bytes(candidate)

            result, output = self.run_audit(
                temp_dir,
                candidate=candidate_path,
                csv_path=csv_path,
            )

            self.assertEqual(result, 1)
            self.assertIn(
                "1 graphical record(s) modified",
                output,
            )

    def test_declared_graphical_translation_may_rewrite_source(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="pokemon-coverage-declared-glyph-"
        ) as temporary:
            temp_dir = Path(temporary)
            csv_path = self.dump_current_script(temp_dir)
            english = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
            records = verified_all_graphical_text_records(english)
            glyph_starts = {
                start
                for start, _, _, _ in records
            }
            declared_starts = {
                entry.offset
                for entry in parse_patch_entries(PATCH_SCRIPT)
                if entry.offset in glyph_starts
            }
            self.assertEqual(
                len(declared_starts),
                len(records)
                - len(REVIEWED_LANGUAGE_NEUTRAL_GLYPH_RECORDS),
            )

            glyph_start = min(declared_starts)
            candidate = bytearray(english)
            candidate[glyph_start] ^= 0x01
            candidate_path = temp_dir / "declared-glyph.nes"
            candidate_path.write_bytes(candidate)

            result, output = self.run_audit(
                temp_dir,
                candidate=candidate_path,
                csv_path=csv_path,
            )

            self.assertEqual(result, 0, output)
            self.assertIn(
                "Graphical records declared translated into French : "
                f"{len(declared_starts)}",
                output,
            )

    def test_unknown_lexical_ascii_run_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="pokemon-coverage-ascii-"
        ) as temporary:
            temp_dir = Path(temporary)
            original = (ROM_DIR / TRANSLATION_BASE_ROM).read_bytes()
            mutated = bytearray(original)

            # This verified padding arena is outside both translated source
            # ranges and structured glyph records. Delimit the synthetic run
            # so the scanner reports its exact start.
            injection_start = 0x030B20
            unknown_text = b"UnreviewedCodexText"
            mutated[injection_start - 1] = 0x0D
            mutated[
                injection_start:injection_start + len(unknown_text)
            ] = unknown_text
            mutated[injection_start + len(unknown_text)] = 0x0D

            english_path = temp_dir / "english-with-unknown-run.nes"
            english_path.write_bytes(mutated)
            csv_path = self.dump_current_script(temp_dir)

            result, output = self.run_audit(
                temp_dir,
                candidate=english_path,
                csv_path=csv_path,
                english_rom=english_path,
            )

            self.assertEqual(result, 1)
            self.assertIn(
                "unclassified ASCII 0x030B20: 'UnreviewedCodexText'",
                output,
            )


if __name__ == "__main__":
    unittest.main()
