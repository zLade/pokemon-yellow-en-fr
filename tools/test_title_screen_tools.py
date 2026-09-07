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


class PlayerMenuGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = (ROM_DIR / "yellow.nes").read_bytes()

    def patched_rom(self) -> bytes:
        candidate = bytearray(self.base)
        graphics.patch_french_player_menu_labels(candidate)
        return bytes(candidate)

    def test_generated_label_hashes(self) -> None:
        patched = self.patched_rom()
        for source_name, expected_hash in EXPECTED_LABEL_HASHES.items():
            with self.subTest(label=source_name):
                self.assertEqual(
                    hashlib.sha256(
                        target_block(patched, source_name)
                    ).hexdigest(),
                    expected_hash,
                )

    def test_patch_changes_only_the_28_reserved_tiles(self) -> None:
        patched = self.patched_rom()
        allowed_offsets = {
            graphics.PLAYER_MENU_PT0_FILE + tile_id * 16 + byte_index
            for layout in graphics.PLAYER_MENU_LABELS.values()
            for tile_id in tuple(layout["top"]) + tuple(layout["bottom"])
            for byte_index in range(16)
        }
        changed_offsets = {
            offset
            for offset, (before, after) in enumerate(zip(self.base, patched))
            if before != after
        }
        self.assertEqual(len(changed_offsets), 226)
        self.assertTrue(changed_offsets <= allowed_offsets)

    def test_player_menu_pt0_contract(self) -> None:
        patched = self.patched_rom()
        pt0 = patched[
            graphics.PLAYER_MENU_PT0_FILE
            : graphics.PLAYER_MENU_PT0_FILE + 0x1000
        ]
        self.assertEqual(
            hashlib.sha256(pt0).hexdigest(),
            "8b56d2126e60574cf0c2a4ce75319cd4"
            "83ccbe5b51a726ffd560de039f4cc3fd",
        )

    def test_patch_is_idempotent(self) -> None:
        candidate = bytearray(self.patched_rom())
        before = bytes(candidate)
        graphics.patch_french_player_menu_labels(candidate)
        self.assertEqual(bytes(candidate), before)

    def test_unexpected_tilemap_is_rejected(self) -> None:
        candidate = bytearray(self.base)
        first_layout = graphics.PLAYER_MENU_LABELS["ITEMS"]
        tilemap_offset = (
            graphics.PLAYER_MENU_NT_FILE
            + int(first_layout["row"]) * 32
            + int(first_layout["column"])
        )
        candidate[tilemap_offset] ^= 0xFF
        with self.assertRaisesRegex(ValueError, "Unexpected ITEMS tilemap"):
            graphics.patch_french_player_menu_labels(candidate)


class TitleAndLoadMenuGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()

    def patched_rom(self) -> bytes:
        candidate = bytearray(self.base)
        graphics.restore_english_title_tiles(candidate, self.base)
        graphics.patch_french_menu_tiles(candidate)
        return bytes(candidate)

    def test_yellow_version_title_and_credits_are_reproducible(self) -> None:
        yellow = (ROM_DIR / "yellow.nes").read_bytes()
        first = bytearray(self.base)
        graphics.patch_english_yellow_title(first, yellow)
        second = bytearray(self.base)
        graphics.patch_english_yellow_title(second, yellow)
        self.assertEqual(first, second)
        cursor_offset = (
            graphics.TITLE_PT1_FILE
            + graphics.TITLE_MENU_CURSOR_TILE_ID * 16
        )
        cursor = yellow[cursor_offset : cursor_offset + 16]
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

    def test_generated_graphic_asset_hashes(self) -> None:
        self.assertEqual(
            hashlib.sha256(
                b"".join(graphics.JAUNE_TILES)
            ).hexdigest(),
            EXPECTED_JAUNE_TILES_SHA256,
        )
        self.assertEqual(
            hashlib.sha256(
                b"".join(graphics.MENU_FR_TILES)
            ).hexdigest(),
            EXPECTED_MENU_FR_TILES_SHA256,
        )
        english_title_tiles = b"".join(
            self.base[
                graphics.TITLE_PT0_FILE + tile_id * 16
                : graphics.TITLE_PT0_FILE + (tile_id + 1) * 16
            ]
            for tile_id in graphics.TITLE_LOGO_TILE_IDS
        )
        self.assertEqual(
            hashlib.sha256(english_title_tiles).hexdigest(),
            EXPECTED_ENGLISH_TITLE_TILES_SHA256,
        )

    def test_english_title_patch_changes_only_french_menu_tiles(self) -> None:
        patched = self.patched_rom()
        target_offsets = [
            *(
                graphics.TITLE_PT1_FILE + tile_id * 16
                for tile_id in graphics.MENU_TILE_IDS
            ),
        ]
        allowed_offsets = {
            offset + byte_index
            for offset in target_offsets
            for byte_index in range(16)
        }
        changed_offsets = {
            offset
            for offset, (before, after) in enumerate(
                zip(self.base, patched)
            )
            if before != after
        }
        self.assertEqual(len(changed_offsets), 68)
        self.assertTrue(changed_offsets <= allowed_offsets)

        self.assertEqual(
            hashlib.sha256(self.title_menu_block(patched)).hexdigest(),
            EXPECTED_ENGLISH_TITLE_MENU_BLOCK_SHA256,
        )

    def test_french_title_mode_remains_reproducible(self) -> None:
        candidate = bytearray(self.base)
        graphics.patch_jaune_tiles(candidate)
        graphics.patch_french_menu_tiles(candidate)
        changed_offsets = {
            offset
            for offset, (before, after) in enumerate(
                zip(self.base, candidate)
            )
            if before != after
        }
        self.assertEqual(len(changed_offsets), 141)
        self.assertEqual(
            hashlib.sha256(self.title_menu_block(candidate)).hexdigest(),
            EXPECTED_FRENCH_TITLE_MENU_BLOCK_SHA256,
        )

    def test_restore_english_title_preserves_french_menu(self) -> None:
        candidate = bytearray(self.base)
        graphics.patch_jaune_tiles(candidate)
        graphics.patch_french_menu_tiles(candidate)
        graphics.restore_english_title_tiles(candidate, self.base)
        self.assertEqual(bytes(candidate), self.patched_rom())

    def test_english_title_patch_is_idempotent(self) -> None:
        candidate = bytearray(self.patched_rom())
        before = bytes(candidate)
        graphics.restore_english_title_tiles(candidate, self.base)
        graphics.patch_french_menu_tiles(candidate)
        self.assertEqual(bytes(candidate), before)

    def test_restore_rejects_incompatible_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "Incompatible English reference"):
            graphics.restore_english_title_tiles(
                bytearray(self.base),
                self.base[:-1],
            )


class MesenTitleLanguageProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.english_rom = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()
        cls.yellow_rom = (ROM_DIR / "yellow.nes").read_bytes()
        cls.source = (
            TOOLS_DIR / "mesen_title_en_menu_fr_probe.lua"
        ).read_text(encoding="utf-8")

    def test_probe_pins_exact_english_and_french_tile_payloads(self) -> None:
        expected_tiles = [
            *(
                self.yellow_rom[
                    graphics.TITLE_PT0_FILE + tile_id * 16
                    : graphics.TITLE_PT0_FILE + (tile_id + 1) * 16
                ]
                for tile_id in graphics.TITLE_LOGO_TILE_IDS
            ),
            *graphics.MENU_FR_TILES,
            self.english_rom[
                graphics.TITLE_PT1_FILE
                + graphics.TITLE_MENU_CURSOR_TILE_ID * 16
                : graphics.TITLE_PT1_FILE
                + (graphics.TITLE_MENU_CURSOR_TILE_ID + 1) * 16
            ],
        ]
        for tile in expected_tiles:
            with self.subTest(tile=tile.hex()):
                self.assertIn(
                    f'bytesFromHex("{tile.hex().upper()}")',
                    self.source,
                )

    def test_probe_is_controller_only_and_has_exact_contract(self) -> None:
        self.assertNotIn("emu.write(", self.source)
        for required in (
            "TITLE_EN_MENU_FR_PASS",
            "TITLE_EN_MENU_FR_FAIL",
            "sameFrameAssets=true",
            'writeBinary(prefix .. "_screen.png", screenshot)',
            'exportState("title_en"',
            'exportState("title_menu_fr"',
            "0x21A9",
            "0x21AD",
            "0x2267",
            "0x22AA",
            "menu_cursor_oam=",
            "nesSpriteRam",
        ):
            with self.subTest(required=required):
                self.assertIn(required, self.source)


class MesenEnglishPlayerMenuProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.english_rom = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()
        cls.source = (
            TOOLS_DIR / "mesen_player_menu_french_probe.lua"
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
