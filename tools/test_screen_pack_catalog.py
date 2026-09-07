#!/usr/bin/env python3
"""Tests for the strict mapper-163 screen-pack catalog."""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

import chr_asset_pipeline as pipeline  # noqa: E402
import screen_pack_catalog as catalog  # noqa: E402


SOURCE_ROM = (
    PROJECT_DIR
    / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
)
CURRENT_ROM = PROJECT_DIR / "Pokemon_Jaune_FR_repacked_title.nes"
CURRENT_ROM_SHA256 = (
    "1fefecbfa7084d19abfa5a89c389e75"
    "f4c0a307dee3b0bf41fde49a7ebf62d5b"
)


def cpu_pointer(pair_base: int, file_offset: int) -> int:
    return catalog.CPU_BASE + file_offset - pair_base


def synthetic_rom() -> bytes:
    header = bytearray(catalog.INES_HEADER_SIZE)
    header[:4] = b"NES\x1a"
    header[4] = 128
    header[5] = 0
    header[6] = 0x33
    header[7] = 0xA0
    data = bytearray(header)
    data.extend(bytes(128 * 0x4000))

    pair_base = (
        catalog.INES_HEADER_SIZE + 16 * catalog.PAIR_SIZE
    )
    record_offset = pair_base + 0x100
    pointer_table_offset = record_offset + 0x1C
    pointer_count = 9
    descriptor_offset = pointer_table_offset + pointer_count * 2
    tilemap_offset = descriptor_offset + 11
    attribute_offset = (
        tilemap_offset + 2 * catalog.TILEMAP_LENGTH
    )
    screen_group_end = (
        tilemap_offset + 2 * catalog.SCREEN_STRIDE
    )
    chr_offset = screen_group_end + 0x100

    data[record_offset + 0x12] = 2
    data[record_offset + 0x13] = 1
    pointers = [
        descriptor_offset,
        chr_offset,
        tilemap_offset,
        tilemap_offset + catalog.TILEMAP_LENGTH,
        attribute_offset,
        attribute_offset + catalog.ATTRIBUTE_LENGTH,
        chr_offset + 0x110,
        chr_offset + 0x100,
        screen_group_end,
    ]
    for index, file_offset in enumerate(pointers):
        struct.pack_into(
            "<H",
            data,
            pointer_table_offset + index * 2,
            cpu_pointer(pair_base, file_offset),
        )

    data[descriptor_offset : descriptor_offset + 8] = bytes(
        [0x00, 0x03, 0x00, 0x00, 0x80, 0x00, 0x80, 0x00]
    )
    struct.pack_into(
        "<H",
        data,
        descriptor_offset + 8,
        cpu_pointer(pair_base, chr_offset + 0x120),
    )
    data[descriptor_offset + 10] = 0xFF
    return bytes(data)


class ScreenPackCatalogTests(unittest.TestCase):
    def test_synthetic_record_and_pipeline_assets(self) -> None:
        data = synthetic_rom()
        records = catalog.scan_screen_pack_records(
            data,
            first_pair=16,
            last_pair=16,
        )
        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertEqual(record["id"], "pair16_pack00")
        self.assertEqual(
            record["dimensions"],
            {"columns": 2, "rows": 1, "screen_count": 2},
        )
        self.assertEqual(record["descriptors"]["length"], 11)
        self.assertEqual(record["descriptors"]["record_count"], 1)
        self.assertIsNone(record["chr_source"]["length"])
        self.assertEqual(
            [item["relation"] for item in record["extra_pointers"]],
            [
                "inside_optional_chr_4k_view",
                "inside_optional_chr_4k_view",
                "screen_group_end",
            ],
        )

        assets = catalog.build_pipeline_assets(records)
        self.assertEqual(len(assets), 4)
        self.assertEqual(
            set(assets[0]),
            {"id", "path", "offset", "length", "kind"},
        )
        self.assertEqual(assets[0]["length"], 960)
        self.assertEqual(assets[1]["length"], 64)
        self.assertEqual(assets[0]["kind"], "raw")
        self.assertNotIn("descriptors", assets[0]["id"])
        self.assertFalse(any("chr" in item["id"] for item in assets))

    def test_broken_stride_is_not_accepted(self) -> None:
        data = bytearray(synthetic_rom())
        pair_base = (
            catalog.INES_HEADER_SIZE + 16 * catalog.PAIR_SIZE
        )
        pointer_table_offset = pair_base + 0x100 + 0x1C
        second_tilemap_pointer = catalog.u16le(
            data,
            pointer_table_offset + 3 * 2,
        )
        struct.pack_into(
            "<H",
            data,
            pointer_table_offset + 3 * 2,
            second_tilemap_pointer + 1,
        )
        with self.assertRaisesRegex(
            catalog.CatalogError,
            "no valid screen-pack record",
        ):
            catalog.scan_screen_pack_records(
                bytes(data),
                first_pair=16,
                last_pair=16,
            )

    def test_synthetic_manifest_is_accepted_by_pipeline(self) -> None:
        data = synthetic_rom()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            rom_path = root / "synthetic.nes"
            rom_path.write_bytes(data)
            built = catalog.build_catalog(
                rom_path,
                first_pair=16,
                last_pair=16,
                expected_records=1,
            )
            manifest = catalog.build_pipeline_manifest(built)
            manifest_path = root / "manifest.json"
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )
            loaded = pipeline.load_manifest(manifest_path)
            self.assertEqual(len(loaded.assets), 4)
            self.assertTrue(all(asset.kind == "raw" for asset in loaded.assets))

    @unittest.skipUnless(SOURCE_ROM.exists(), "source ROM missing")
    def test_reference_rom_has_96_records_and_832_assets(self) -> None:
        built = catalog.build_catalog(SOURCE_ROM)
        self.assertEqual(built["record_count"], 96)
        self.assertEqual(built["pipeline_asset_count"], 832)
        self.assertEqual(
            {record["pair"] for record in built["records"]},
            set(range(16, 49)),
        )
        self.assertEqual(
            sum(
                record["dimensions"]["screen_count"]
                for record in built["records"]
            ),
            416,
        )
        self.assertEqual(
            sum(asset["length"] for asset in built["pipeline_assets"]),
            425_984,
        )
        first = built["records"][0]
        self.assertEqual(first["record_offset"], "0x080010")
        self.assertEqual(first["descriptors"]["offset"], "0x080046")
        self.assertEqual(
            first["chr_source"]["target_offset"],
            "0x081C8F",
        )
        self.assertEqual(
            first["screens"][0]["tilemap"]["offset"],
            "0x08006F",
        )
        player_menu = next(
            record
            for record in built["records"]
            if record["record_offset"] == "0x13A104"
        )
        self.assertEqual(
            player_menu["chr_source"]["target_offset"],
            "0x13B17B",
        )
        self.assertEqual(
            player_menu["screen_group"],
            {
                "offset": "0x13A17B",
                "length": 4096,
                "screen_stride": 1024,
            },
        )

    @unittest.skipUnless(
        SOURCE_ROM.exists() and CURRENT_ROM.exists(),
        "source ROM or final candidate missing",
    )
    def test_record_structure_is_unchanged_in_current_rom(self) -> None:
        source = catalog.build_catalog(SOURCE_ROM)
        current = catalog.build_catalog(CURRENT_ROM)
        self.assertEqual(
            current["rom"]["sha256"],
            CURRENT_ROM_SHA256,
        )
        self.assertEqual(source["records"], current["records"])
        self.assertEqual(
            source["pipeline_assets"],
            current["pipeline_assets"],
        )


if __name__ == "__main__":
    unittest.main()
