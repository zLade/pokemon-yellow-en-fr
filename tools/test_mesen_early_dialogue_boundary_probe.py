#!/usr/bin/env python3
"""Static contracts for the natural early-dialogue Mesen probe."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import parse_patch_entries  # noqa: E402
from tools.dialogue_layout import format_game_text  # noqa: E402


CAMPAIGN_DIR = ROM_DIR / "tools" / "campaign"
TARGETS_PATH = CAMPAIGN_DIR / "dialogue_targets.lua"
CAPTURE_PATH = CAMPAIGN_DIR / "dialogue_capture.lua"
PROBE_PATH = CAMPAIGN_DIR / "mesen_early_dialogue_boundary_probe.lua"

REQUIRED_OFFSETS = {
    0x03082C,
    0x035DCC,
    0x035E82,
    0x03F27B,
    0x038519,
    0x03F2EE,
}
OPTIONAL_JADIELLE_OFFSET = 0x0387F3
OPTIONAL_EXPLORATION_OFFSETS = {
    0x034CB3,
    0x034D08,
    0x034D3A,
    0x034D4C,
    0x034DE5,
    OPTIONAL_JADIELLE_OFFSET,
}


def lua_target_rows(source: str) -> dict[int, dict[str, object]]:
    rows: dict[int, dict[str, object]] = {}
    pattern = re.compile(
        r"""\{\s*
        source_offset\s*=\s*(?P<offset>0x[0-9A-Fa-f]+),\s*
        label\s*=\s*"(?P<label>[^"]+)",\s*
        required\s*=\s*(?P<required>true|false),\s*
        (?P<body>.*?)
        payload_hex\s*=\s*(?P<payload>.*?)
        \n\s*\},""",
        flags=re.DOTALL | re.VERBOSE,
    )
    for match in pattern.finditer(source):
        offset = int(match.group("offset"), 16)
        payload_chunks = re.findall(
            r'"([0-9A-Fa-f]+)"',
            match.group("payload"),
        )
        if not payload_chunks:
            raise AssertionError(f"payload_hex vide à ${offset:06X}")
        milestone_match = re.search(
            r'milestone\s*=\s*"([^"]+)"',
            match.group("body"),
        )
        rows[offset] = {
            "label": match.group("label"),
            "required": match.group("required") == "true",
            "milestone": milestone_match.group(1)
            if milestone_match
            else "",
            "payload": bytes.fromhex("".join(payload_chunks)),
        }
    return rows


class MesenEarlyDialogueBoundaryProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.targets_source = TARGETS_PATH.read_text(encoding="utf-8")
        cls.capture_source = CAPTURE_PATH.read_text(encoding="utf-8")
        cls.probe_source = (
            PROBE_PATH.read_text(encoding="utf-8")
            if PROBE_PATH.is_file()
            else ""
        )
        cls.targets = lua_target_rows(cls.targets_source)

    def test_target_payloads_follow_current_script_exactly(self) -> None:
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                "script.py",
                apply_dialogue_inventory=False,
            )
        }
        expected_offsets = REQUIRED_OFFSETS | OPTIONAL_EXPLORATION_OFFSETS
        self.assertEqual(set(self.targets), expected_offsets)
        for offset, row in self.targets.items():
            entry = entries[offset]
            expected = format_game_text(entry.text, entry.layout) + b"\x0D"
            self.assertEqual(
                row["payload"],
                expected,
                f"payload Lua périmé à ${offset:06X}",
            )
            self.assertEqual(row["payload"][-1:], b"\x0D")

    def test_required_and_optional_route_contract(self) -> None:
        actual_required = {
            offset
            for offset, row in self.targets.items()
            if row["required"]
        }
        self.assertEqual(actual_required, REQUIRED_OFFSETS)
        self.assertTrue(self.targets[0x03F27B]["required"])
        self.assertTrue(self.targets[0x038519]["required"])
        self.assertTrue(self.targets[0x03F2EE]["required"])
        self.assertEqual(
            self.targets[0x03F27B]["milestone"],
            "mother_downstairs",
        )
        self.assertEqual(
            self.targets[0x038519]["milestone"],
            "oak_first_meeting",
        )
        self.assertEqual(
            self.targets[0x03F2EE]["milestone"],
            "oak_lab_initial",
        )
        for offset in OPTIONAL_EXPLORATION_OFFSETS:
            self.assertFalse(self.targets[offset]["required"])
        self.assertEqual(
            self.targets[OPTIONAL_JADIELLE_OFFSET]["milestone"],
            "jadielle",
        )

    def test_mother_and_oak_capture_exact_page_counts(self) -> None:
        expected_pages = {
            0x03F27B: 6,
            0x038519: 6,
            0x03F2EE: 8,
        }
        for offset, page_count in expected_pages.items():
            with self.subTest(offset=f"0x{offset:06X}"):
                payload_length = len(self.targets[offset]["payload"]) - 1
                self.assertEqual(
                    (payload_length + 18) // 19,
                    page_count,
                )

    def test_observer_is_passive_and_exports_same_frame_evidence(self) -> None:
        self.assertIsNone(
            re.search(r"\bemu\s*\.\s*write\s*\(", self.capture_source)
        )
        required = (
            'name = "17_19"',
            'name = "19_19"',
            "local TILE_BASES = {0x40, 0xD4}",
            "first_page_bytes = 19",
            "subsequent_page_bytes = 19",
            "tile_base = 0xD4",
            "ordinary_one_19_column_slice",
            "local function pageSourceReadComplete",
            'target.detected_layout.name == "19_19"',
            "local function nametableAddress(globalX, globalY)",
            "origin_search=64x60_logical_nametable",
            "promptArrowVisible()",
            "y >= 222 and y <= 225",
            "target.read_bytes[#target.record - 1]",
            "self._stable_frames >= 12",
            "emu.memType.nesChrRam",
            "emu.memType.nesPpuDebug",
            "emu.memType.nesSpriteRam",
            '"early_dialogue_pages.tsv"',
            '"early_dialogue_targets.tsv"',
            '"early_dialogue_runtime_pcs.tsv"',
            '"early_dialogue_observer.txt"',
            "function DialogueCapture:layoutSummary",
            "target.last_captured_signature",
            "target.ppu_2006_write_pcs",
            "target.ppu_2007_write_pcs",
            "target.detected_tile_base",
            "target.detected_origin_x",
            "target.detected_origin_y",
            "x = originX + (19 - firstLineWidth) + lineIndex",
            "x = originX + lineIndex",
            "(tileBase + pageIndex * 2) & 0xFF",
            "target.last_read_frame < 12",
            "target.layout_scan_attempts >= 3",
            "POKEMON_DIALOGUE_LAYOUT_PENDING",
            "_layout_observations.txt",
        )
        for snippet in required:
            self.assertIn(snippet, self.capture_source)
        for suffix in (
            ".png",
            "_chr_ram_8k.bin",
            "_ppu_pattern_8k.bin",
            "_nametable_4k.bin",
            "_palette_32.bin",
            "_oam_256.bin",
            "_mesen_state.txt",
            "_expected_page_hex.txt",
        ):
            self.assertIn(f'prefix .. "{suffix}"', self.capture_source)

    def test_nametable_origin_is_the_stable_19_column_left_edge(self) -> None:
        self.assertIn(
            "x = originX + (19 - firstLineWidth) + lineIndex",
            self.capture_source,
        )
        self.assertIn(
            "x = originX + lineIndex",
            self.capture_source,
        )
        self.assertNotIn(
            "x = originX - (19 - firstLineWidth) + lineIndex",
            self.capture_source,
        )
        canonical_origin = 6
        self.assertEqual(
            [
                canonical_origin + (19 - first_line_width)
                for first_line_width in (17, 19)
            ],
            [8, 6],
        )

    def test_controller_route_talks_to_mother_before_leaving_home(self) -> None:
        required = (
            "local MOTHER_APPROACH_X = 0x40",
            "local MOTHER_APPROACH_Y = 0x40",
            'next = "align_below_mother"',
            'next = "talk_to_mother"',
            'next = "round_table_left"',
            'captureCheckpoint("01a_mother_approach")',
            'captureCheckpoint("01b_mother_dialogue_complete")',
        )
        for snippet in required:
            self.assertIn(snippet, self.probe_source)

        route_states = [
            self.probe_source.index(f'engine:add_state("{state}"')
            for state in (
                "descend_right_of_table",
                "align_below_mother",
                "talk_to_mother",
                "round_table_left",
                "leave_house",
            )
        ]
        self.assertEqual(route_states, sorted(route_states))

    def test_probe_requires_natural_lab_completion(self) -> None:
        self.assertTrue(
            self.probe_source,
            "mesen_early_dialogue_boundary_probe.lua absent",
        )
        self.assertIsNone(
            re.search(r"\bemu\s*\.\s*write\s*\(", self.probe_source)
        )
        required = (
            'loadModule("dialogue_capture.lua")',
            'loadModule("dialogue_targets.lua")',
            "capture:tick()",
            "capture:allRequiredCompleted()",
            "capture:validationErrors()",
            'engine:add_state("align_below_mother"',
            'engine:add_state("talk_to_mother"',
            'capture:milestoneCompleted("mother_downstairs")',
            'ctx.input:pulse("down", 4, 6, "face_mother")',
            'ctx.input:pulse("a", 3, 24, "advance_mother_dialogue")',
            'capture:milestoneCompleted("oak_first_meeting")',
            'capture:milestoneCompleted("oak_lab_initial")',
            '"04a_oak_first_meeting_complete"',
            '"04b_oak_lab_initial_complete"',
            "LAB_NAMETABLE",
            "POKEMON_EARLY_DIALOGUE_BOUNDARY_PASS",
            "writes_to_game=0",
            "jadielle=false",
        )
        for snippet in required:
            self.assertIn(snippet, self.probe_source)


if __name__ == "__main__":
    unittest.main()
