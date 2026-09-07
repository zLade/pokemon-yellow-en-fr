#!/usr/bin/env python3
"""Regression tests for the title/player-menu CHR patcher."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import title_screen_tools as graphics  # noqa: E402


EXPECTED_LABEL_HASHES = {
    "ITEMS": (
        "0b10bb8f1dc04c7b605f2f28a090647f"
        "2b970506e22dd0580c512c96c6415c02"
    ),
    "ASH": (
        "6190c469afe76c63283044399e9ee5e2"
        "b7796b05eeed296135af417e51de77a7"
    ),
    "HMS": (
        "f9febc788e590a7c0ffde0b95816ca7"
        "1ea5327c2063a96476a3a39d422c8bf10"
    ),
    "SAVE": (
        "503480da92ca0201fbada11b6562ead9"
        "6b59ea80969d3f2ffe84f2fabf74fd41"
    ),
}
EXPECTED_JAUNE_TILES_SHA256 = (
    "4040c84de53f2c181cb9673bbf1d46da"
    "b815c8c39cce7774e9e5b2d0e3eb5f35"
)
EXPECTED_ENGLISH_TITLE_TILES_SHA256 = (
    "8c021c6dc3811bc12cbda9bbbb3b0837"
    "426c4d2dbc86ce45ae41ccdcddfc6640"
)
EXPECTED_MENU_FR_TILES_SHA256 = (
    "6ec2e77ce666b8d4bf9782e2e6f29800"
    "a656a8f62a5aee541fea42789557400a"
)
EXPECTED_ENGLISH_TITLE_MENU_BLOCK_SHA256 = (
    "8674112c1b02e4aeba43b1756655be68"
    "78805fbecf11130552c3b254d59876ae"
)
EXPECTED_FRENCH_TITLE_MENU_BLOCK_SHA256 = (
    "ef28aedb49b5adf9ec778e2ec04eb205"
    "8e705de2d149a6b9729e65ba7e0eee4c"
)


def target_block(rom: bytes, source_name: str) -> bytes:
    layout = graphics.PLAYER_MENU_LABELS[source_name]
    tile_ids = tuple(layout["top"]) + tuple(layout["bottom"])
    return b"".join(
        rom[
            graphics.PLAYER_MENU_PT0_FILE + tile_id * 16
            : graphics.PLAYER_MENU_PT0_FILE + (tile_id + 1) * 16
        ]
        for tile_id in tile_ids
    )




@unittest.skipUnless(
    (ROM_DIR / "Pokemon Yellow English 9-23-2015.nes").is_file()
    , "canonical title ROM absent",
)
class TitleAndLoadMenuGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()


    def test_yellow_version_title_and_credits_are_reproducible(self) -> None:
        yellow = (ROM_DIR / "Pokemon Yellow English 9-23-2015.nes").read_bytes()
        first = bytearray(self.base)
        graphics.patch_english_yellow_title(first, yellow)
        second = bytearray(self.base)
        graphics.patch_english_yellow_title(second, yellow)
        self.assertEqual(first, second)
        cursor_offset = (
            graphics.TITLE_PT1_FILE
            + graphics.TITLE_MENU_CURSOR_TILE_ID * 16
        )
        cursor = bytes.fromhex("001c2241415f2e1c00001c363e1e0c00")
        self.assertNotEqual(cursor, bytes(16))
        self.assertEqual(first[cursor_offset : cursor_offset + 16], cursor)
        self.assertEqual(
            hashlib.sha256(first).hexdigest(),
            "ec12aa2329098684e29b1b9fd1734b6c"
            "55c34903f382b0bdd20bdd7055c63b9e",
        )
        self.assertEqual(
            len(graphics.english_title_changed_offsets(self.base, yellow)),
            480,
        )

    def title_menu_block(self, rom: bytes) -> bytes:
        target_offsets = [
            *(
                graphics.TITLE_PT0_FILE + tile_id * 16
                for tile_id in graphics.TITLE_LOGO_TILE_IDS
            ),
            *(
                graphics.TITLE_PT1_FILE + tile_id * 16
                for tile_id in graphics.MENU_TILE_IDS
            ),
        ]
        return b"".join(
            rom[offset:offset + 16]
            for offset in sorted(target_offsets)
        )










@unittest.skipUnless(
    (ROM_DIR / "Pokemon Yellow English 9-23-2015.nes").is_file(),
    "canonical English base absent",
)
class MesenEnglishPlayerMenuProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.english_rom = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()
        cls.source = (
            TOOLS_DIR / "mesen_player_menu_probe.lua"
        ).read_text(encoding="utf-8")
        cls.wrapper = (
            TOOLS_DIR / "mesen_player_menu_en_probe.lua"
        ).read_text(encoding="utf-8")

    @staticmethod
    def rolling_checksum(payload: bytes) -> int:
        checksum = 0
        for value in payload:
            checksum = (checksum * 257 + value) & 0xFFFFFFFF
        return checksum

    def test_probe_pins_all_original_english_label_tiles(self) -> None:
        for source_name, layout in graphics.PLAYER_MENU_LABELS.items():
            tile_ids = tuple(layout["top"]) + tuple(layout["bottom"])
            payload = b"".join(
                self.english_rom[
                    graphics.PLAYER_MENU_PT0_FILE + tile_id * 16
                    : graphics.PLAYER_MENU_PT0_FILE + (tile_id + 1) * 16
                ]
                for tile_id in tile_ids
            )
            expected = self.rolling_checksum(payload)
            with self.subTest(label=source_name):
                self.assertIn(f"0x{expected:08X}", self.source)

    def test_probe_pins_full_english_chr_and_exact_marker(self) -> None:
        chr_data = graphics.player_menu_chr_from_rom(self.english_rom)
        expected = self.rolling_checksum(chr_data)
        self.assertIn(f"0x{expected:08X}", self.source)
        self.assertIn("POKEMON_PLAYER_MENU_EN_PASS", self.source)
        self.assertNotIn("emu.write(", self.source)
        self.assertIn(
            'POKEMON_PLAYER_MENU_PROFILE = "en-US"',
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
