#!/usr/bin/env python3
"""Regression tests for ``generate_chr_asset_manifest.py``."""

from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import chr_asset_pipeline as pipeline  # noqa: E402
import generate_chr_asset_manifest as catalog  # noqa: E402


@unittest.skipUnless(
    catalog.DEFAULT_ROM.is_file() and catalog.DEFAULT_IPS_BASE_ROM.is_file(),
    "ROM finale ou base IPS absente",
)
class ChrAssetManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom_data = catalog.DEFAULT_ROM.read_bytes()
        cls.base_data = catalog.DEFAULT_IPS_BASE_ROM.read_bytes()
        cls.manifest, cls.rows, cls.stats = catalog.build_catalog(
            cls.rom_data,
            ips_base_data=cls.base_data,
        )

    def test_default_rom_is_the_hash_bound_current_release(self) -> None:
        self.assertEqual(
            catalog.DEFAULT_ROM,
            catalog.ROM_DIR / "Pokemon_Jaune_FR_repacked_title.nes",
        )
        self.assertEqual(
            catalog.sha256(self.rom_data),
            catalog.CURRENT_ROM_SHA256,
        )
        catalog.validate_default_rom_binding(
            catalog.DEFAULT_ROM,
            self.rom_data,
        )

        modified = bytearray(self.rom_data)
        modified[-1] ^= 0xFF
        with self.assertRaisesRegex(
            catalog.CatalogError,
            "snapshot courant attendu",
        ):
            catalog.validate_default_rom_binding(
                catalog.DEFAULT_ROM,
                bytes(modified),
            )

    def test_complete_package_catalog(self) -> None:
        self.assertEqual(self.stats["package_count"], 587)
        self.assertEqual(self.stats["package_tile_count"], 22_790)
        self.assertEqual(self.stats["package_chr_bytes"], 0x59060)
        self.assertEqual(
            self.stats["variant_counts"],
            {
                "one_tilemap": 280,
                "two_tilemaps": 298,
                "three_tilemaps": 9,
            },
        )
        package_rows = [
            row for row in self.rows
            if row["family"] == "sprite_package"
        ]
        self.assertEqual(len(package_rows), 587)

    def test_known_intro_pikachu_anchor(self) -> None:
        pikachu = next(
            row for row in self.rows
            if (
                row["semantic"] == "intro_pikachu"
                and row["family"] == "sprite_package"
            )
        )
        self.assertEqual(pikachu["id"], "pkg-b62-025")
        self.assertEqual(pikachu["chunk_offset"], "0x1F6484")
        self.assertEqual(pikachu["offset"], "0x1F64F1")
        self.assertEqual(pikachu["length"], 0x2E0)
        self.assertEqual(pikachu["cpu_pointer"], "0xE474")

    def test_pipeline_compatible_five_field_assets(self) -> None:
        self.assertEqual(self.manifest["schema"], pipeline.SCHEMA)
        expected_fields = {"id", "path", "offset", "length", "kind"}
        self.assertTrue(self.manifest["assets"])
        self.assertTrue(
            all(set(asset) == expected_fields for asset in self.manifest["assets"])
        )
        self.assertEqual(len(self.manifest["assets"]), 1_489)

    def test_screen_bundles_fixed_assets_and_hzk_exclusion(self) -> None:
        self.assertEqual(self.stats["screen_component_count"], 64)
        self.assertEqual(self.stats["fixed_chr_count"], 3)
        self.assertEqual(self.stats["semantic_alias_count"], 3)
        self.assertEqual(self.stats["strict_screen_pack_count"], 96)
        self.assertEqual(
            self.stats["strict_screen_pack_asset_count"],
            832,
        )
        self.assertFalse(self.stats["hzk16_included"])
        for asset in self.manifest["assets"]:
            start = int(asset["offset"], 16)
            end = start + asset["length"]
            self.assertFalse(start <= catalog.HZK16_EXCLUDED_OFFSET < end)

    def test_strict_screen_pack_assets_are_raw_and_bounded(self) -> None:
        rows = [
            row
            for row in self.rows
            if row["family"] == "strict_screen_pack"
        ]
        self.assertEqual(len(rows), 832)
        self.assertEqual(
            sum(row["component"] == "tilemap" for row in rows),
            416,
        )
        self.assertEqual(
            sum(row["component"] == "attributes" for row in rows),
            416,
        )
        self.assertTrue(all(row["kind"] == "raw" for row in rows))
        self.assertTrue(
            all(
                row["length"] in (960, 64)
                for row in rows
            )
        )

    def test_named_paths_and_precise_semantic_aliases(self) -> None:
        assets_by_id = {
            asset["id"]: asset for asset in self.manifest["assets"]
        }
        self.assertEqual(
            assets_by_id["screen-b14-g00-chr0"]["path"],
            "screens/title_screen/chr0.chr",
        )
        self.assertEqual(
            assets_by_id["screen-b05-g00-chr0"]["path"],
            "screens/player_menu/chr0.chr",
        )
        self.assertEqual(
            assets_by_id["screen-b15-g00-chr0"]["path"],
            "screens/intro_professor/chr0.chr",
        )
        self.assertEqual(
            assets_by_id["screen-b15-g01-chr0"]["path"],
            "screens/intro_player/chr0.chr",
        )
        self.assertEqual(
            assets_by_id["screen-b05-g01-chr0"]["path"],
            "screens/b05/g01/chr0.chr",
        )
        self.assertEqual(
            assets_by_id["ui-ascii-font"]["path"],
            "fonts/ui_ascii_font.chr",
        )
        self.assertEqual(
            assets_by_id["player-menu-pt1"]["path"],
            "screens/player_menu/pt1.chr",
        )
        self.assertEqual(
            assets_by_id["runtime-bank39-page-ccd1"]["path"],
            "screens/overworld/runtime_bank39_page_ccd1.chr",
        )

        expected_aliases = {
            "intro-professor-portrait": (0x07CE31, 0x01C0),
            "intro-player-portrait": (0x07D4A1, 0x0210),
            "intro-pikachu-sprite": (0x1F64F1, 0x02E0),
        }
        rows_by_id = {row["id"]: row for row in self.rows}
        for asset_id, (offset, length) in expected_aliases.items():
            asset = assets_by_id[asset_id]
            row = rows_by_id[asset_id]
            self.assertEqual(int(asset["offset"], 16), offset)
            self.assertEqual(asset["length"], length)
            self.assertEqual(row["family"], "semantic_alias")
            self.assertEqual(
                row["recompile_policy"],
                "baseline_aware_overlap_merge",
            )

    def test_csv_has_one_row_per_asset(self) -> None:
        csv_data = catalog.metadata_csv_bytes(self.rows).decode("utf-8")
        decoded = list(csv.DictReader(io.StringIO(csv_data)))
        self.assertEqual(len(decoded), len(self.manifest["assets"]))
        self.assertEqual(decoded[0]["id"], self.manifest["assets"][0]["id"])


if __name__ == "__main__":
    unittest.main()
