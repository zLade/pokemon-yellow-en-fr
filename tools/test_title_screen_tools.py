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
EXPECTED_SECONDARY_LABEL_HASHES = {
    "NAME": (
        "2e78e9e0ef8bdd57d9dcb15086f65f98"
        "5c8644a62db033ee7ddcdfe377b5ccc5"
    ),
    "MONEY": (
        "b6a389cce3353275eb0460827505eb4a"
        "9dcfa04af843eccbd677a4cd975403a8"
    ),
    "POKEDEX": (
        "385481a5689db9937cb157f6aec6b790"
        "969bcd059a7ff4618cf604b84508b9db"
    ),
    "SAVING": (
        "e1fde1e0f219a7b08d69ebd868a8829"
        "b412c06210304ec9cac98ad8e1cfec264"
    ),
    "PLAYER_NAME": (
        "27ab2d15998f9dfdbeab4f35f26c3f71"
        "dd8972052b6006b9e2c7f6278aeb405b"
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
EXPECTED_FRENCH_BOTTOM_TITLE_TILES_SHA256 = (
    "6a83ec769258865d01059c7d2a368f36f"
    "78c11206c2bb451da7230ff3644a577"
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
        if not all((ROM_DIR / name).is_file() for name in ("yellow.nes", "Pokemon Yellow English 9-23-2015.nes")):
            raise unittest.SkipTest("ROMs sources absentes")
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
        with self.assertRaisesRegex(ValueError, "Tilemap ITEMS inattendu"):
            graphics.patch_french_player_menu_labels(candidate)


class SecondaryMenuGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not all((ROM_DIR / name).is_file() for name in ("yellow.nes", "Pokemon Yellow English 9-23-2015.nes")):
            raise unittest.SkipTest("ROMs sources absentes")
        cls.base = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()

    @staticmethod
    def label_block(
        rom: bytes,
        chr_file: int,
        layout: dict[str, object],
    ) -> bytes:
        tile_ids = tuple(layout["top"]) + tuple(layout["bottom"])
        return b"".join(
            rom[chr_file + tile_id * 16 : chr_file + (tile_id + 1) * 16]
            for tile_id in tile_ids
        )

    def patched_rom(self) -> bytes:
        candidate = bytearray(self.base)
        graphics.patch_french_status_screen_labels(candidate)
        graphics.patch_french_saving_screen_label(candidate)
        return bytes(candidate)

    def test_status_and_saving_labels_are_french(self) -> None:
        patched = self.patched_rom()
        for source_name, layout in graphics.STATUS_SCREEN_LABELS.items():
            with self.subTest(label=source_name):
                self.assertEqual(
                    hashlib.sha256(
                        self.label_block(
                            patched,
                            graphics.STATUS_SCREEN_CHR_FILE,
                            layout,
                        )
                    ).hexdigest(),
                    EXPECTED_SECONDARY_LABEL_HASHES[source_name],
                )
        self.assertEqual(
            hashlib.sha256(
                self.label_block(
                    patched,
                    graphics.SAVING_SCREEN_CHR_FILE,
                    graphics.SAVING_SCREEN_LABEL,
                )
            ).hexdigest(),
            EXPECTED_SECONDARY_LABEL_HASHES["SAVING"],
        )

    def test_badges_and_saving_dots_are_preserved(self) -> None:
        patched = self.patched_rom()
        badges = (
            0xC0, 0xC1, 0xC2, 0xC3, 0x9A,
            0xC7, 0xC8, 0xC9, 0xCA, 0xA3,
        )
        for tile_id in badges:
            start = graphics.STATUS_SCREEN_CHR_FILE + tile_id * 16
            self.assertEqual(patched[start : start + 16], self.base[start : start + 16])
        dots = graphics.SAVING_SCREEN_CHR_FILE + 0x10 * 16
        self.assertEqual(patched[dots : dots + 16], self.base[dots : dots + 16])

    def test_sacha_recycles_blank_tile_and_preserves_portrait(self) -> None:
        patched = self.patched_rom()
        layout = graphics.STATUS_SCREEN_PLAYER_NAME
        target_ids = tuple(layout["target_top"])
        target_block = b"".join(
            patched[
                graphics.STATUS_SCREEN_CHR_FILE + tile_id * 16
                : graphics.STATUS_SCREEN_CHR_FILE + (tile_id + 1) * 16
            ]
            for tile_id in target_ids
        )
        self.assertEqual(
            hashlib.sha256(target_block).hexdigest(),
            EXPECTED_SECONDARY_LABEL_HASHES["PLAYER_NAME"],
        )
        portrait_ids = (0x8F, 0x90, 0x91, 0x92, 0x93, 0x94)
        for tile_id in portrait_ids:
            start = graphics.STATUS_SCREEN_CHR_FILE + tile_id * 16
            self.assertEqual(
                patched[start : start + 16],
                self.base[start : start + 16],
            )
        row = int(layout["row"])
        column = int(layout["column"])
        nt = graphics.STATUS_SCREEN_NT_FILE
        self.assertEqual(
            tuple(patched[nt + row * 32 + column : nt + row * 32 + column + 3]),
            tuple(layout["target_top"]),
        )
        self.assertEqual(
            tuple(
                patched[
                    nt + (row + 1) * 32 + column
                    : nt + (row + 1) * 32 + column + 3
                ]
            ),
            tuple(layout["target_bottom"]),
        )
        blank_offset = (
            nt
            + int(layout["duplicate_blank_row"]) * 32
            + int(layout["duplicate_blank_column"])
        )
        self.assertEqual(patched[blank_offset], 0x78)

    def test_secondary_patch_is_idempotent(self) -> None:
        candidate = bytearray(self.patched_rom())
        before = bytes(candidate)
        graphics.patch_french_status_screen_labels(candidate)
        graphics.patch_french_saving_screen_label(candidate)
        self.assertEqual(bytes(candidate), before)

    def test_unexpected_secondary_tilemap_is_rejected(self) -> None:
        candidate = bytearray(self.base)
        layout = graphics.STATUS_SCREEN_LABELS["NAME"]
        offset = (
            graphics.STATUS_SCREEN_NT_FILE
            + int(layout["row"]) * 32
            + int(layout["column"])
        )
        candidate[offset] ^= 0xFF
        with self.assertRaisesRegex(ValueError, "Tilemap NAME inattendu"):
            graphics.patch_french_status_screen_labels(candidate)


class TitleAndLoadMenuGraphicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not all((ROM_DIR / name).is_file() for name in ("yellow.nes", "Pokemon Yellow English 9-23-2015.nes")):
            raise unittest.SkipTest("ROMs sources absentes")
        cls.base = (
            ROM_DIR / "Pokemon Yellow English 9-23-2015.nes"
        ).read_bytes()

    def patched_rom(self) -> bytes:
        candidate = bytearray(self.base)
        graphics.restore_english_title_tiles(candidate, self.base)
        graphics.patch_french_menu_tiles(candidate)
        return bytes(candidate)

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
        with self.assertRaisesRegex(ValueError, "référence incompatible"):
            graphics.restore_english_title_tiles(
                bytearray(self.base),
                self.base[:-1],
            )

    def test_shared_title_credits_are_reproducible(self) -> None:
        first = bytearray(self.base)
        second = bytearray(self.base)
        cursor_offset = (
            graphics.TITLE_PT1_FILE
            + graphics.TITLE_MENU_CURSOR_TILE_ID * 16
        )
        cursor_before = bytes(self.base[cursor_offset : cursor_offset + 16])
        graphics.patch_title_credits(first)
        graphics.patch_title_credits(second)
        self.assertEqual(bytes(first), bytes(second))
        self.assertNotEqual(cursor_before, bytes(16))
        self.assertEqual(
            bytes(first[cursor_offset : cursor_offset + 16]),
            cursor_before,
        )
        self.assertEqual(
            graphics.ENGLISH_TITLE_CREDITS,
            "LUIGA2009, ZLADE, CHPEXO",
        )
        changed = {
            offset
            for offset, (before, after) in enumerate(zip(self.base, first))
            if before != after
        }
        self.assertTrue(changed)
        self.assertTrue(
            all(
                graphics.TITLE_PT1_FILE <= offset < graphics.TITLE_NT_FILE + 0x400
                for offset in changed
            )
        )

    def test_french_bottom_title_uses_centered_jaune_banner(self) -> None:
        first = bytearray(self.base)
        second = bytearray(self.base)
        cursor_offset = (
            graphics.TITLE_PT1_FILE
            + graphics.TITLE_MENU_CURSOR_TILE_ID * 16
        )
        cursor_before = bytes(first[cursor_offset : cursor_offset + 16])
        graphics.patch_french_bottom_title_label(first)
        graphics.patch_french_bottom_title_label(second)
        self.assertEqual(first, second)
        self.assertEqual(
            hashlib.sha256(
                b"".join(graphics.FRENCH_BOTTOM_TITLE_TILES)
            ).hexdigest(),
            EXPECTED_FRENCH_BOTTOM_TITLE_TILES_SHA256,
        )
        nt_offset = graphics.TITLE_NT_FILE + (
            graphics.FRENCH_BOTTOM_TITLE_NT_ROW * 32
            + graphics.FRENCH_BOTTOM_TITLE_NT_COLUMN
        )
        self.assertEqual(
            first[
                nt_offset
                : nt_offset + graphics.FRENCH_BOTTOM_TITLE_NT_WIDTH
            ],
            graphics.FRENCH_BOTTOM_TITLE_TILEMAP,
        )
        self.assertEqual(
            bytes(first[cursor_offset : cursor_offset + 16]),
            cursor_before,
        )




if __name__ == "__main__":
    unittest.main()
