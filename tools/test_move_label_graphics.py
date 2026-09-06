#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from tools.move_label_graphics import (  # noqa: E402
    ASCII_FONT_FIRST_CODE,
    ASCII_FONT_OFFSET,
    ASCII_FONT_TILE_COUNT,
    ASCII_FONT_TILE_SIZE,
    DEFAULT_EXCLUDED_EVEN_SLOTS,
    GRAPHIC_ATLAS_OFFSET,
    GRAPHIC_ATLAS_SLOT_SIZE,
    IncompleteMoveLabelPatch,
    MOVE_COUNT,
    MOVE_NAME_BANK_CPU_BASE,
    MOVE_NAME_BANK_FILE_BASE,
    MOVE_NAME_POINTER_TABLE_OFFSET,
    MoveLabelCsvError,
    RomLayoutError,
    extract_graphic_slot_pool,
    french_text_encoder,
    graphic_code,
    load_move_label_csv,
    patch_move_labels,
    read_move_records,
)


REAL_SOURCE = ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
REAL_CANDIDATE = (
    ROM_DIR
    / "build"
    / "english-battle-ui-20260816"
    / "Pokemon_Yellow_EN_Battle_UI_Fixed.nes"
)


def _font_tile(rom: bytes, character: str) -> bytes:
    code = ord(character)
    start = ASCII_FONT_OFFSET + (code - ASCII_FONT_FIRST_CODE) * ASCII_FONT_TILE_SIZE
    return rom[start : start + ASCII_FONT_TILE_SIZE]


def _synthetic_rom(*, source_graphics: bool) -> bytes:
    size = ASCII_FONT_OFFSET + ASCII_FONT_TILE_COUNT * ASCII_FONT_TILE_SIZE + 0x100
    rom = bytearray(size)
    record_base = 0x032000
    stride = 12

    source_slots = [202]
    source_slots.extend(
        slot
        for slot in range(38, 760, 2)
        if slot != 202
    )
    for move_index in range(MOVE_COUNT):
        target = record_base + move_index * stride
        pointer = MOVE_NAME_BANK_CPU_BASE + target - MOVE_NAME_BANK_FILE_BASE
        pointer_offset = MOVE_NAME_POINTER_TABLE_OFFSET + move_index * 2
        rom[pointer_offset : pointer_offset + 2] = pointer.to_bytes(2, "little")
        if source_graphics:
            if move_index == 0:
                # B1 0D maps to slot 202.  The low byte is data, not a terminator.
                payload = bytes((0xB1, 0x0D, 0x0D))
            else:
                payload = graphic_code(source_slots[move_index]) + b"\r"
        else:
            payload = b"ABCDEFGH\r"
        rom[target : target + len(payload)] = payload

    for code in range(ASCII_FONT_FIRST_CODE, ASCII_FONT_FIRST_CODE + ASCII_FONT_TILE_COUNT):
        start = ASCII_FONT_OFFSET + (code - ASCII_FONT_FIRST_CODE) * ASCII_FONT_TILE_SIZE
        rom[start : start + ASCII_FONT_TILE_SIZE] = bytes((code,)) * ASCII_FONT_TILE_SIZE

    atlas_end = GRAPHIC_ATLAS_OFFSET + 800 * GRAPHIC_ATLAS_SLOT_SIZE
    rom[GRAPHIC_ATLAS_OFFSET:atlas_end] = b"\xA5" * (atlas_end - GRAPHIC_ATLAS_OFFSET)
    return bytes(rom)


def _catalogue_path(directory: Path, rows: str) -> Path:
    path = directory / "move_labels.csv"
    path.write_text(
        "move_index,full_name,line_1,line_2\n" + rows,
        encoding="utf-8",
        newline="",
    )
    return path


class MoveLabelCsvTests(unittest.TestCase):
    def test_loads_utf8_and_counts_encoded_french_glyphs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = _catalogue_path(
                Path(temporary),
                "019,Éclair Fou,Éclair,Fou\n",
            )
            specs = load_move_label_csv(path, encoder=french_text_encoder)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].move_index, 19)
        self.assertEqual(specs[0].encoded_line_1, b"*clair")
        self.assertEqual(specs[0].encoded_line_2, b"Fou")
        self.assertEqual(specs[0].code_count, 3)
        self.assertEqual(specs[0].required_payload_size, 7)

    def test_rejects_duplicate_and_out_of_range_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            duplicate = _catalogue_path(
                directory,
                "001,First,Fi,rst\n001,Again,Ag,ain\n",
            )
            with self.assertRaisesRegex(MoveLabelCsvError, "duplicate move_index 1"):
                load_move_label_csv(duplicate)
            outside = _catalogue_path(
                directory,
                "177,Outside,Out,side\n",
            )
            with self.assertRaisesRegex(MoveLabelCsvError, "outside 0..176"):
                load_move_label_csv(outside)

    def test_rejects_empty_or_more_than_eight_encoded_glyphs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            empty = _catalogue_path(directory, "001,Empty,,Line\n")
            with self.assertRaisesRegex(MoveLabelCsvError, "line_1 must not be empty"):
                load_move_label_csv(empty)
            long_line = _catalogue_path(
                directory,
                "001,Too Long,123456789,Line\n",
            )
            with self.assertRaisesRegex(MoveLabelCsvError, "9 encoded glyphs"):
                load_move_label_csv(long_line)

    def test_rejects_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.csv"
            path.write_bytes(
                b"move_index,full_name,line_1,line_2\n001,Name,One,Tw\xff\n"
            )
            with self.assertRaisesRegex(MoveLabelCsvError, "invalid UTF-8"):
                load_move_label_csv(path)


class SyntheticMoveLabelPatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = _synthetic_rom(source_graphics=True)
        self.candidate = _synthetic_rom(source_graphics=False)

    def _specs(self, rows: str):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = _catalogue_path(Path(temporary.name), rows)
        return load_move_label_csv(path)

    def test_parser_does_not_treat_graphical_low_0d_as_terminator(self) -> None:
        record = read_move_records(self.source)[0]
        self.assertEqual(record.payload, bytes((0xB1, 0x0D, 0x0D)))
        self.assertEqual(record.graphical_slots, (202,))
        self.assertEqual(len(read_move_records(self.source)), MOVE_COUNT)

    def test_parser_includes_terminator_after_even_or_odd_ascii_length(self) -> None:
        candidate = bytearray(self.candidate)
        first = read_move_records(self.candidate)[0]
        second = read_move_records(self.candidate)[1]
        candidate[first.target : first.target + 3] = b"A\rX"
        candidate[second.target : second.target + 4] = b"AB\rX"

        records = read_move_records(bytes(candidate))
        self.assertEqual(records[0].payload, b"A\r")
        self.assertEqual(records[0].capacity, 2)
        self.assertEqual(records[1].payload, b"AB\r")
        self.assertEqual(records[1].capacity, 3)

    def test_patch_builds_two_char_top_and_bottom_atlas_halves(self) -> None:
        specs = self._specs("019,Thunder Shock,Thunder,Shock\n")
        before_excluded = {
            slot: self.candidate[
                GRAPHIC_ATLAS_OFFSET + slot * GRAPHIC_ATLAS_SLOT_SIZE :
                GRAPHIC_ATLAS_OFFSET + (slot + 2) * GRAPHIC_ATLAS_SLOT_SIZE
            ]
            for slot in DEFAULT_EXCLUDED_EVEN_SLOTS
        }
        result = patch_move_labels(self.candidate, self.source, specs)
        report = result.report

        self.assertTrue(report.complete)
        self.assertEqual(report.applied_count, 1)
        self.assertEqual(report.candidate_target_count, MOVE_COUNT)
        self.assertEqual(report.candidate_unique_target_count, MOVE_COUNT)
        self.assertEqual(report.used_even_slots, (38, 40, 42, 44))
        self.assertNotIn(208, report.used_even_slots)
        self.assertGreater(report.changed_offset_count, 0)
        json.dumps(report.to_dict())

        target = read_move_records(self.candidate)[19].target
        expected_payload = b"".join(graphic_code(slot) for slot in (38, 40, 42, 44)) + b"\r"
        self.assertEqual(result.rom[target : target + len(expected_payload)], expected_payload)

        first_cell = GRAPHIC_ATLAS_OFFSET + 38 * GRAPHIC_ATLAS_SLOT_SIZE
        self.assertEqual(
            result.rom[first_cell : first_cell + GRAPHIC_ATLAS_SLOT_SIZE],
            _font_tile(self.candidate, "T") + _font_tile(self.candidate, "h"),
        )
        self.assertEqual(
            result.rom[
                first_cell + GRAPHIC_ATLAS_SLOT_SIZE :
                first_cell + 2 * GRAPHIC_ATLAS_SLOT_SIZE
            ],
            _font_tile(self.candidate, "S") + _font_tile(self.candidate, "h"),
        )
        for slot, before in before_excluded.items():
            start = GRAPHIC_ATLAS_OFFSET + slot * GRAPHIC_ATLAS_SLOT_SIZE
            self.assertEqual(
                result.rom[start : start + 2 * GRAPHIC_ATLAS_SLOT_SIZE],
                before,
            )

        allowed = set(range(target, target + len(expected_payload)))
        for slot in report.used_even_slots:
            start = GRAPHIC_ATLAS_OFFSET + slot * GRAPHIC_ATLAS_SLOT_SIZE
            allowed.update(range(start, start + 2 * GRAPHIC_ATLAS_SLOT_SIZE))
        changed = {
            offset
            for offset, pair in enumerate(zip(self.candidate, result.rom))
            if pair[0] != pair[1]
        }
        self.assertLessEqual(changed, allowed)

    def test_insufficient_payload_is_reported_and_never_written(self) -> None:
        candidate = bytearray(self.candidate)
        record = read_move_records(self.candidate)[7]
        candidate[record.target : record.target + record.capacity] = b"A\r" + b"X" * 7
        candidate = bytes(candidate)
        specs = self._specs("007,Four Letters,ABCD,WXYZ\n")

        with self.assertRaises(IncompleteMoveLabelPatch) as caught:
            patch_move_labels(candidate, self.source, specs)
        self.assertEqual(caught.exception.report.entries[0].status, "insufficient_capacity")

        partial = patch_move_labels(
            candidate,
            self.source,
            specs,
            require_all=False,
        )
        self.assertEqual(partial.rom, candidate)
        self.assertEqual(partial.report.applied_count, 0)
        self.assertEqual(partial.report.skipped_count, 1)

    def test_unselected_graphical_record_protects_its_atlas_cell(self) -> None:
        candidate = bytearray(self.candidate)
        record = read_move_records(self.candidate)[0]
        candidate[record.target : record.target + 3] = graphic_code(38) + b"\r"
        specs = self._specs("001,Small Label,AB,CD\n")
        result = patch_move_labels(bytes(candidate), self.source, specs)
        self.assertEqual(result.report.used_even_slots, (40,))
        self.assertGreaterEqual(result.report.pool_protected_count, 2)

    def test_duplicate_candidate_targets_are_rejected(self) -> None:
        candidate = bytearray(self.candidate)
        first_pointer = candidate[
            MOVE_NAME_POINTER_TABLE_OFFSET : MOVE_NAME_POINTER_TABLE_OFFSET + 2
        ]
        candidate[
            MOVE_NAME_POINTER_TABLE_OFFSET + 2 : MOVE_NAME_POINTER_TABLE_OFFSET + 4
        ] = first_pointer
        specs = self._specs("001,Small Label,AB,CD\n")
        with self.assertRaisesRegex(RomLayoutError, "176/177 unique targets"):
            patch_move_labels(bytes(candidate), self.source, specs)

    def test_graphical_payload_may_not_cross_another_live_move_target(self) -> None:
        candidate = bytearray(self.candidate)
        first = read_move_records(self.candidate)[0]
        nested_target = first.target + 4
        nested_pointer = (
            MOVE_NAME_BANK_CPU_BASE
            + nested_target
            - MOVE_NAME_BANK_FILE_BASE
        )
        second_pointer_offset = MOVE_NAME_POINTER_TABLE_OFFSET + 2
        candidate[second_pointer_offset : second_pointer_offset + 2] = (
            nested_pointer.to_bytes(2, "little")
        )
        candidate = bytes(candidate)

        bounded = read_move_records(candidate)[0]
        self.assertEqual(bounded.raw_capacity, 9)
        self.assertEqual(bounded.capacity, 4)
        self.assertEqual(bounded.next_live_target, nested_target)
        self.assertEqual(bounded.overlapping_move_indexes, (1,))

        specs = self._specs("000,Wide Label,ABCDEFGH,12345678\n")
        with self.assertRaises(IncompleteMoveLabelPatch) as caught:
            patch_move_labels(candidate, self.source, specs)
        entry = caught.exception.report.entries[0]
        self.assertEqual(entry.status, "insufficient_disjoint_capacity")
        self.assertEqual(entry.capacity, 4)
        self.assertEqual(entry.raw_capacity, 9)
        self.assertEqual(entry.overlapping_move_indexes, (1,))

        partial = patch_move_labels(
            candidate,
            self.source,
            specs,
            require_all=False,
        )
        self.assertEqual(partial.rom, candidate)

    def test_complete_177_label_patch_is_byte_idempotent(self) -> None:
        rows = "".join(
            f"{move_index:03d},Move {move_index:03d},A,B\n"
            for move_index in range(MOVE_COUNT)
        )
        specs = self._specs(rows)
        first = patch_move_labels(
            self.candidate,
            None,
            specs,
            pool_mode="canonical",
        )
        second = patch_move_labels(
            first.rom,
            None,
            specs,
            pool_mode="canonical",
        )

        self.assertTrue(first.report.complete)
        self.assertEqual(first.report.applied_count, MOVE_COUNT)
        self.assertEqual(len(first.report.used_even_slots), MOVE_COUNT)
        self.assertEqual(second.rom, first.rom)
        self.assertEqual(
            second.report.used_even_slots,
            first.report.used_even_slots,
        )
        self.assertEqual(second.report.changed_offset_count, 0)


@unittest.skipUnless(REAL_SOURCE.is_file(), "English 2015 ROM not present")
class RealEnglishRomTests(unittest.TestCase):
    def test_real_source_pool_and_embedded_0d_codes(self) -> None:
        source = REAL_SOURCE.read_bytes()
        pool = extract_graphic_slot_pool(source)
        self.assertEqual(len(pool.discovered_slots), 353)
        self.assertEqual(len(pool.available_even_slots), 350)
        self.assertTrue(DEFAULT_EXCLUDED_EVEN_SLOTS <= set(pool.discovered_slots))
        self.assertTrue(DEFAULT_EXCLUDED_EVEN_SLOTS.isdisjoint(pool.available_even_slots))

        record = read_move_records(source)[41]
        self.assertEqual(record.payload, bytes.fromhex("B1 0D B1 0F B1 11 0D"))
        self.assertEqual(record.graphical_slots, (202, 204, 206))

    @unittest.skipUnless(REAL_CANDIDATE.is_file(), "final English candidate not present")
    def test_real_candidate_is_patched_in_memory_only(self) -> None:
        source_before = REAL_SOURCE.read_bytes()
        candidate_before = REAL_CANDIDATE.read_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            catalogue = _catalogue_path(
                Path(temporary),
                "019,Thunder Shock,Thunder,Shock\n",
            )
            specs = load_move_label_csv(catalogue)
        result = patch_move_labels(candidate_before, source_before, specs)

        self.assertTrue(result.report.complete)
        self.assertEqual(result.report.used_even_slots, (38, 40, 42, 44))
        self.assertEqual(result.report.candidate_unique_target_count, MOVE_COUNT)
        patched_record = read_move_records(result.rom)[19]
        self.assertEqual(patched_record.graphical_slots, (38, 40, 42, 44))
        self.assertEqual(REAL_SOURCE.read_bytes(), source_before)
        self.assertEqual(REAL_CANDIDATE.read_bytes(), candidate_before)


if __name__ == "__main__":
    unittest.main()
