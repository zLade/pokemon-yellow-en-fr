#!/usr/bin/env python3
"""Generate the complete editable CHR catalogue for Pokemon Yellow NJ046.

The cartridge is mapper 163 with CHR-RAM.  Its graphics therefore live in
PRG-ROM source blocks rather than in an iNES CHR-ROM payload.  This generator
describes:

* the 587 self-describing sprite/portrait packages in PRG banks 50..62;
* the raw screen bundles referenced by the tables in banks 5, 14 and 15;
* 416 strictly bounded 32x30 tilemaps and their 416 attribute tables from
  the screen-pack records in PRG pairs 16..48;
* the raw ASCII UI font and two independently observed 4 KiB CHR pages.

The JSON output is accepted directly by ``chr_asset_pipeline.py``.  It keeps
the deliberately small five-field asset records required by that pipeline;
all reverse-engineering metadata is written to a companion CSV.

HZK16 at file offset 0x040010 is intentionally excluded: its split 1-bpp
layout requires a dedicated codec and is not an ordinary NES ``.chr`` asset.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import struct
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chr_asset_pipeline as pipeline
import screen_pack_catalog


ROM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ROM = ROM_DIR / "Pokemon_Jaune_FR_repacked_title.nes"
CURRENT_ROM_SHA256 = (
    "1fefecbfa7084d19abfa5a89c389e75"
    "f4c0a307dee3b0bf41fde49a7ebf62d5b"
)
DEFAULT_IPS_BASE_ROM = ROM_DIR / "yellow.nes"
DEFAULT_OUTPUT_DIR = (
    ROM_DIR / "build" / "chr-catalog" / "current-1fefecbf"
)
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "chr-assets.manifest.json"
DEFAULT_METADATA = DEFAULT_OUTPUT_DIR / "chr-assets.metadata.csv"

INES_HEADER_SIZE = 0x10
PRG_BANK_SIZE = 0x8000
CPU_BANK_BASE = 0x8000
HZK16_EXCLUDED_OFFSET = 0x040010

PACKAGE_BANK_COUNTS = {
    50: 62,
    51: 49,
    52: 55,
    53: 62,
    54: 43,
    55: 58,
    56: 59,
    57: 56,
    58: 28,
    59: 27,
    60: 28,
    61: 29,
    62: 31,
}
EXPECTED_PACKAGE_COUNT = 587
EXPECTED_PACKAGE_TILE_COUNT = 22_790
EXPECTED_PACKAGE_CHR_BYTES = 0x59060
EXPECTED_VARIANT_COUNTS = {
    "one_tilemap": 280,
    "two_tilemaps": 298,
    "three_tilemaps": 9,
}
EXPECTED_SCREEN_PACK_RECORD_COUNT = 96
EXPECTED_SCREEN_PACK_ASSET_COUNT = 832


@dataclass(frozen=True)
class ScreenTable:
    bank: int
    cpu_address: int
    group_count: int


SCREEN_TABLES = (
    ScreenTable(bank=5, cpu_address=0x801D, group_count=7),
    ScreenTable(bank=14, cpu_address=0x8013, group_count=5),
    ScreenTable(bank=15, cpu_address=0x9051, group_count=4),
)

SCREEN_COMPONENTS = (
    ("chr0", 0x1000, "chr", ".chr"),
    ("chr1", 0x1000, "chr", ".chr"),
    ("nametable", 0x0400, "raw", ".bin"),
    ("palette", 0x0020, "raw", ".bin"),
)

SCREEN_SEMANTICS = {
    (5, 0): "player_menu_base",
    (14, 0): "title_screen",
    (15, 0): "intro_professor_portrait",
    (15, 1): "intro_player_portrait",
    (15, 2): "intro_screen_2_unresolved",
    (15, 3): "intro_screen_3_unresolved",
}

KNOWN_SCREEN_PATHS = {
    (5, 0): "player_menu",
    (14, 0): "title_screen",
    (15, 0): "intro_professor",
    (15, 1): "intro_player",
}

PACKAGE_SEMANTICS = {
    # Proven by an exact tile/palette/OAM reconstruction of the intro frame.
    (62, 25): "intro_pikachu",
}

FIXED_CHR_ASSETS = (
    {
        "id": "ui-ascii-font",
        "path": "fonts/ui_ascii_font.chr",
        "offset": 0x078210,
        "length": 0x0600,
        "semantic": "ASCII UI font, 96 tiles from space through tilde",
        "bank": 15,
        "cpu_pointer": 0x8200,
    },
    {
        "id": "player-menu-pt1",
        "path": "screens/player_menu/pt1.chr",
        "offset": 0x13B17B,
        "length": 0x1000,
        "semantic": "player menu second 4 KiB pattern source",
        "bank": 39,
        "cpu_pointer": 0xB16B,
    },
    {
        "id": "runtime-bank39-page-ccd1",
        "path": "screens/overworld/runtime_bank39_page_ccd1.chr",
        "offset": 0x13CCD1,
        "length": 0x1000,
        "semantic": (
            "runtime-loaded room/menu CHR page; exact screen identity unresolved"
        ),
        "bank": 39,
        "cpu_pointer": 0xCCC1,
    },
)

SEMANTIC_CHR_ALIASES = (
    {
        "id": "intro-professor-portrait",
        "path": "screens/intro_professor/portrait.chr",
        "offset": 0x07CE31,
        "length": 0x01C0,
        "semantic": "Professor Oak/Chen intro portrait, tiles 0 through 27",
        "bank": 15,
        "cpu_pointer": 0xCE21,
        "component": "portrait_chr",
        "notes": (
            "exact visible portrait subset of screen-b15-g00-chr0"
        ),
    },
    {
        "id": "intro-player-portrait",
        "path": "screens/intro_player/portrait.chr",
        "offset": 0x07D4A1,
        "length": 0x0210,
        "semantic": "intro player portrait and its immediate UI tiles",
        "bank": 15,
        "cpu_pointer": 0xD491,
        "component": "portrait_chr",
        "notes": (
            "exact reconstructed 33-tile subset of "
            "screen-b15-g01-chr0"
        ),
    },
    {
        "id": "intro-pikachu-sprite",
        "path": "sprites/intro/pikachu.chr",
        "offset": 0x1F64F1,
        "length": 0x02E0,
        "semantic": "intro Pikachu sprite, 46 raw NES 2bpp tiles",
        "bank": 62,
        "cpu_pointer": 0xE4E1,
        "component": "sprite_chr",
        "notes": (
            "exact alias of pkg-b62-025 payload; package pointer is $E474"
        ),
    },
)

CSV_FIELDS = (
    "id",
    "path",
    "offset",
    "end_offset_exclusive",
    "length",
    "kind",
    "sha256",
    "family",
    "semantic",
    "bank",
    "index",
    "component",
    "cpu_pointer",
    "chunk_offset",
    "chunk_length",
    "width_tiles",
    "height_tiles",
    "tile_count",
    "variant",
    "tilemap_count",
    "tilemap0_file_offset",
    "tilemap1_file_offset",
    "tilemap2_file_offset",
    "palette_file_offset",
    "palette_length",
    "chr_relative_offset",
    "overlap_count",
    "recompile_policy",
    "notes",
)


class CatalogError(ValueError):
    """The ROM layout does not match the reverse-engineered format."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_default_rom_binding(path: Path, data: bytes) -> None:
    """Require a deliberate update when the repository's current ROM moves."""
    if path.resolve() != DEFAULT_ROM.resolve():
        return
    actual = sha256(data)
    if actual != CURRENT_ROM_SHA256:
        raise CatalogError(
            "the default CHR ROM is not the expected current snapshot: "
            f"{actual} instead of {CURRENT_ROM_SHA256}"
        )


def hex_offset(value: int) -> str:
    return f"0x{value:06X}"


def cpu_to_file(bank: int, cpu_pointer: int) -> int:
    if not 0 <= bank < 64:
        raise CatalogError(f"PRG bank out of range: {bank}")
    if not CPU_BANK_BASE <= cpu_pointer <= 0xFFFF:
        raise CatalogError(
            f"CPU pointer outside window $8000-$FFFF: ${cpu_pointer:04X}"
        )
    return (
        INES_HEADER_SIZE
        + bank * PRG_BANK_SIZE
        + cpu_pointer
        - CPU_BANK_BASE
    )


def read_u16(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 2 > len(data):
        raise CatalogError(f"u16 read outside ROM at {hex_offset(offset)}")
    return struct.unpack_from("<H", data, offset)[0]


def empty_metadata() -> dict[str, Any]:
    return {field: "" for field in CSV_FIELDS}


def append_asset(
    data: bytes,
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    asset_id: str,
    path: str,
    offset: int,
    length: int,
    kind: str,
    metadata: dict[str, Any],
) -> None:
    if offset < INES_HEADER_SIZE or offset + length > len(data):
        raise CatalogError(
            f"{asset_id}: range {hex_offset(offset)}+{length} outside ROM"
        )
    if kind == "chr" and length % 16:
        raise CatalogError(
            f"{asset_id}: CHR size {length} not a multiple of 16"
        )

    asset = {
        "id": asset_id,
        "path": path,
        "offset": hex_offset(offset),
        "length": length,
        "kind": kind,
    }
    row = empty_metadata()
    row.update(asset)
    row.update(metadata)
    row["end_offset_exclusive"] = hex_offset(offset + length)
    row["sha256"] = sha256(data[offset : offset + length])
    row["overlap_count"] = 0
    assets.append(asset)
    rows.append(row)


def parse_sprite_packages(
    data: bytes,
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    package_count = 0
    tile_count_total = 0
    chr_bytes_total = 0
    variant_counts = {name: 0 for name in EXPECTED_VARIANT_COUNTS}
    bank_counts: dict[int, int] = {}

    for bank, expected_count in PACKAGE_BANK_COUNTS.items():
        bank_file = INES_HEADER_SIZE + bank * PRG_BANK_SIZE
        first_pointer = read_u16(data, bank_file)
        table_delta = first_pointer - CPU_BANK_BASE
        if table_delta < 1 or (table_delta - 1) % 2:
            raise CatalogError(
                f"bank {bank}: first pointer ${first_pointer:04X} "
                "incompatible with table+marker"
            )
        pointer_count = (table_delta - 1) // 2
        if pointer_count != expected_count:
            raise CatalogError(
                f"bank {bank}: {pointer_count} pointers, "
                f"{expected_count} expected"
            )

        marker_offset = cpu_to_file(bank, first_pointer) - 1
        if data[marker_offset] != 0x40:
            raise CatalogError(
                f"bank {bank}: missing marker 0x40 at "
                f"{hex_offset(marker_offset)}"
            )

        pointers = [
            read_u16(data, bank_file + index * 2)
            for index in range(pointer_count)
        ]
        if pointers != sorted(set(pointers)):
            raise CatalogError(
                f"bank {bank}: pointers are not strictly increasing"
            )

        for index, cpu_pointer in enumerate(pointers):
            chunk_offset = cpu_to_file(bank, cpu_pointer)
            if chunk_offset + 7 > len(data):
                raise CatalogError(
                    f"b{bank}#{index}: truncated package header"
                )

            width, height, tiles, chr_relative, palette_relative = data[
                chunk_offset : chunk_offset + 5
            ]
            area = width * height
            first_map_relative = data[chunk_offset + 5]
            if not width or not height or not tiles:
                raise CatalogError(
                    f"b{bank}#{index}: zero dimensions/nTiles"
                )

            if first_map_relative == 6:
                variant = "one_tilemap"
                tilemap_count = 1
                tilemap_relatives = (6, None, None)
                expected_palette_relative = 6 + area
            elif first_map_relative == 7:
                variant = "two_tilemaps"
                tilemap_count = 2
                second_map_relative = data[chunk_offset + 6]
                expected_second_map_relative = 7 + area
                if second_map_relative != expected_second_map_relative:
                    raise CatalogError(
                        f"b{bank}#{index}: second tilemap +"
                        f"0x{second_map_relative:02X}, expected +"
                        f"0x{expected_second_map_relative:02X}"
                    )
                tilemap_relatives = (7, second_map_relative, None)
                expected_palette_relative = 7 + area * 2
            elif first_map_relative == 8:
                variant = "three_tilemaps"
                tilemap_count = 3
                second_map_relative = data[chunk_offset + 6]
                third_map_relative = data[chunk_offset + 7]
                expected_second_map_relative = 8 + area
                expected_third_map_relative = 8 + area * 2
                if second_map_relative != expected_second_map_relative:
                    raise CatalogError(
                        f"b{bank}#{index}: second tilemap +"
                        f"0x{second_map_relative:02X}, expected +"
                        f"0x{expected_second_map_relative:02X}"
                    )
                if third_map_relative != expected_third_map_relative:
                    raise CatalogError(
                        f"b{bank}#{index}: third tilemap +"
                        f"0x{third_map_relative:02X}, expected +"
                        f"0x{expected_third_map_relative:02X}"
                    )
                tilemap_relatives = (
                    8,
                    second_map_relative,
                    third_map_relative,
                )
                expected_palette_relative = 8 + area * 3
            else:
                raise CatalogError(
                    f"b{bank}#{index}: unknown variant "
                    f"(map0=0x{first_map_relative:02X})"
                )

            expected_chr_relative = expected_palette_relative + 4
            if palette_relative != expected_palette_relative:
                raise CatalogError(
                    f"b{bank}#{index}: palette +"
                    f"0x{palette_relative:02X}, expected +"
                    f"0x{expected_palette_relative:02X}"
                )
            if chr_relative != expected_chr_relative:
                raise CatalogError(
                    f"b{bank}#{index}: CHR +0x{chr_relative:02X}, "
                    f"expected +0x{expected_chr_relative:02X}"
                )

            chr_length = tiles * 16
            chunk_length = chr_relative + chr_length
            chunk_end = chunk_offset + chunk_length
            bank_end = bank_file + PRG_BANK_SIZE
            if chunk_end > bank_end:
                raise CatalogError(
                    f"b{bank}#{index}: package exceeds its bank"
                )
            if index + 1 < pointer_count:
                next_offset = cpu_to_file(bank, pointers[index + 1])
                if chunk_end != next_offset:
                    raise CatalogError(
                        f"b{bank}#{index}: end {hex_offset(chunk_end)}, "
                        f"next pointer {hex_offset(next_offset)}"
                    )

            chr_offset = chunk_offset + chr_relative
            palette_offset = chunk_offset + palette_relative
            semantic = PACKAGE_SEMANTICS.get((bank, index), "unresolved")
            asset_id = f"pkg-b{bank:02d}-{index:03d}"
            append_asset(
                data,
                assets,
                rows,
                asset_id=asset_id,
                path=f"packages/b{bank:02d}/{index:03d}.chr",
                offset=chr_offset,
                length=chr_length,
                kind="chr",
                metadata={
                    "family": "sprite_package",
                    "semantic": semantic,
                    "bank": bank,
                    "index": index,
                    "component": "chr_payload",
                    "cpu_pointer": f"0x{cpu_pointer:04X}",
                    "chunk_offset": hex_offset(chunk_offset),
                    "chunk_length": chunk_length,
                    "width_tiles": width,
                    "height_tiles": height,
                    "tile_count": tiles,
                    "variant": variant,
                    "tilemap_count": tilemap_count,
                    "tilemap0_file_offset": hex_offset(
                        chunk_offset + tilemap_relatives[0]
                    ),
                    "tilemap1_file_offset": (
                        ""
                        if tilemap_relatives[1] is None
                        else hex_offset(
                            chunk_offset + tilemap_relatives[1]
                        )
                    ),
                    "tilemap2_file_offset": (
                        ""
                        if tilemap_relatives[2] is None
                        else hex_offset(
                            chunk_offset + tilemap_relatives[2]
                        )
                    ),
                    "palette_file_offset": hex_offset(palette_offset),
                    "palette_length": 4,
                    "chr_relative_offset": (
                        f"0x{chr_relative:02X}"
                    ),
                    "recompile_policy": (
                        "direct_same_size; rebuild pointer table if resized"
                    ),
                    "notes": (
                        "raw NES 2bpp; descriptor/tilemap/palette are outside "
                        "this .chr asset"
                    ),
                },
            )

            package_count += 1
            tile_count_total += tiles
            chr_bytes_total += chr_length
            variant_counts[variant] += 1

        bank_counts[bank] = pointer_count

    if package_count != EXPECTED_PACKAGE_COUNT:
        raise CatalogError(
            f"{package_count} packages, {EXPECTED_PACKAGE_COUNT} expected"
        )
    if tile_count_total != EXPECTED_PACKAGE_TILE_COUNT:
        raise CatalogError(
            f"{tile_count_total} tiles, "
            f"{EXPECTED_PACKAGE_TILE_COUNT} expected"
        )
    if chr_bytes_total != EXPECTED_PACKAGE_CHR_BYTES:
        raise CatalogError(
            f"0x{chr_bytes_total:X} CHR bytes, "
            f"0x{EXPECTED_PACKAGE_CHR_BYTES:X} expected"
        )
    if variant_counts != EXPECTED_VARIANT_COUNTS:
        raise CatalogError(
            f"variants {variant_counts}, "
            f"{EXPECTED_VARIANT_COUNTS} expected"
        )

    return {
        "package_count": package_count,
        "package_tile_count": tile_count_total,
        "package_chr_bytes": chr_bytes_total,
        "variant_counts": variant_counts,
        "bank_counts": bank_counts,
    }


def parse_screen_bundles(
    data: bytes,
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> int:
    component_count = 0
    for table in SCREEN_TABLES:
        table_offset = cpu_to_file(table.bank, table.cpu_address)
        for group in range(table.group_count):
            pointer_offset = table_offset + group * 8
            pointers = [
                read_u16(data, pointer_offset + component * 2)
                for component in range(4)
            ]
            semantic = SCREEN_SEMANTICS.get(
                (table.bank, group),
                "unresolved_screen_bundle",
            )
            named_path = KNOWN_SCREEN_PATHS.get((table.bank, group))
            screen_path = (
                f"screens/{named_path}"
                if named_path is not None
                else f"screens/b{table.bank:02d}/g{group:02d}"
            )

            for component_index, component_spec in enumerate(
                SCREEN_COMPONENTS
            ):
                component, length, kind, extension = component_spec
                cpu_pointer = pointers[component_index]
                offset = cpu_to_file(table.bank, cpu_pointer)
                notes = (
                    "raw source referenced by a four-pointer screen bundle"
                )
                if kind == "chr":
                    notes += (
                        "; 4 KiB ranges deliberately overlap some adjacent "
                        "screen resources"
                    )
                if (table.bank, group) == (14, 0):
                    notes += (
                        "; title slot0 is PT1 and slot1 is PT0 because of "
                        "the mapper 163 scanline split"
                    )

                asset_id = (
                    f"screen-b{table.bank:02d}-g{group:02d}-{component}"
                )
                append_asset(
                    data,
                    assets,
                    rows,
                    asset_id=asset_id,
                    path=f"{screen_path}/{component}{extension}",
                    offset=offset,
                    length=length,
                    kind=kind,
                    metadata={
                        "family": "screen_bundle",
                        "semantic": semantic,
                        "bank": table.bank,
                        "index": group,
                        "component": component,
                        "cpu_pointer": f"0x{cpu_pointer:04X}",
                        "chunk_offset": hex_offset(pointer_offset),
                        "chunk_length": 8,
                        "width_tiles": (
                            16 if kind == "chr" else ""
                        ),
                        "height_tiles": (
                            16 if kind == "chr" else ""
                        ),
                        "tile_count": (
                            length // 16 if kind == "chr" else ""
                        ),
                        "variant": "four_pointer_screen_bundle",
                        "tilemap_count": (
                            1 if component == "nametable" else ""
                        ),
                        "palette_file_offset": (
                            hex_offset(offset)
                            if component == "palette"
                            else ""
                        ),
                        "palette_length": (
                            length if component == "palette" else ""
                        ),
                        "recompile_policy": (
                            "baseline_aware_overlap_merge"
                        ),
                        "notes": notes,
                    },
                )
                component_count += 1
    return component_count


def append_fixed_assets(
    data: bytes,
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> int:
    for spec in FIXED_CHR_ASSETS:
        append_asset(
            data,
            assets,
            rows,
            asset_id=spec["id"],
            path=spec["path"],
            offset=spec["offset"],
            length=spec["length"],
            kind="chr",
            metadata={
                "family": "fixed_chr",
                "semantic": spec["semantic"],
                "bank": spec["bank"],
                "component": "chr_payload",
                "cpu_pointer": f"0x{spec['cpu_pointer']:04X}",
                "width_tiles": 16,
                "height_tiles": spec["length"] // (16 * 16),
                "tile_count": spec["length"] // 16,
                "variant": "raw_nes_2bpp",
                "recompile_policy": "direct_same_size",
                "notes": "raw NES 2bpp source block",
            },
        )
    return len(FIXED_CHR_ASSETS)


def append_semantic_aliases(
    data: bytes,
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> int:
    for spec in SEMANTIC_CHR_ALIASES:
        append_asset(
            data,
            assets,
            rows,
            asset_id=spec["id"],
            path=spec["path"],
            offset=spec["offset"],
            length=spec["length"],
            kind="chr",
            metadata={
                "family": "semantic_alias",
                "semantic": spec["semantic"],
                "bank": spec["bank"],
                "component": spec["component"],
                "cpu_pointer": f"0x{spec['cpu_pointer']:04X}",
                "width_tiles": 16,
                "height_tiles": (
                    spec["length"] // (16 * 16)
                    if spec["length"] % (16 * 16) == 0
                    else ""
                ),
                "tile_count": spec["length"] // 16,
                "variant": "raw_nes_2bpp_subset_alias",
                "recompile_policy": "baseline_aware_overlap_merge",
                "notes": spec["notes"],
            },
        )
    return len(SEMANTIC_CHR_ALIASES)


def append_strict_screen_pack_assets(
    data: bytes,
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> tuple[int, int]:
    """Append only the statically bounded layouts from PRG pairs 16..48.

    ``screen_pack_catalog`` also records every CHR source pointer, but those
    records do not encode a CHR length.  The unbounded 4 KiB interpretations
    therefore remain catalog-only and are never added here.
    """

    records = screen_pack_catalog.scan_screen_pack_records(data)
    if len(records) != EXPECTED_SCREEN_PACK_RECORD_COUNT:
        raise CatalogError(
            f"{len(records)} screen-packs, "
            f"{EXPECTED_SCREEN_PACK_RECORD_COUNT} expected"
        )
    pipeline_assets = screen_pack_catalog.build_pipeline_assets(records)
    if len(pipeline_assets) != EXPECTED_SCREEN_PACK_ASSET_COUNT:
        raise CatalogError(
            f"{len(pipeline_assets)} screen-pack assets, "
            f"{EXPECTED_SCREEN_PACK_ASSET_COUNT} expected"
        )
    pipeline_by_id = {
        asset["id"]: asset
        for asset in pipeline_assets
    }

    for record in records:
        for screen in record["screens"]:
            for role in ("tilemap", "attributes"):
                block = screen[role]
                pipeline_asset = pipeline_by_id[block["id"]]
                is_tilemap = role == "tilemap"
                append_asset(
                    data,
                    assets,
                    rows,
                    asset_id=pipeline_asset["id"],
                    path=pipeline_asset["path"],
                    offset=int(pipeline_asset["offset"], 16),
                    length=pipeline_asset["length"],
                    kind=pipeline_asset["kind"],
                    metadata={
                        "family": "strict_screen_pack",
                        "semantic": "unresolved_screen_layout",
                        "bank": record["pair"],
                        "index": screen["index"],
                        "component": role,
                        "chunk_offset": record["record_offset"],
                        "chunk_length": record["screen_group"]["length"],
                        "width_tiles": 32 if is_tilemap else 8,
                        "height_tiles": 30 if is_tilemap else 8,
                        "variant": (
                            "32x30_tilemap"
                            if is_tilemap
                            else "8x8_attribute_table"
                        ),
                        "tilemap_count": 1 if is_tilemap else "",
                        "recompile_policy": "direct_same_size",
                        "notes": (
                            "strictly bounded by the mapper-163 screen-pack "
                            "pointer table; associated CHR pointer is "
                            "catalogued separately and has no asserted length"
                        ),
                    },
                )
    return len(records), len(pipeline_assets)


def annotate_overlaps(
    assets: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> int:
    counts = [0] * len(assets)
    overlap_pairs = 0
    ranges = [
        (int(asset["offset"], 16), int(asset["offset"], 16) + asset["length"])
        for asset in assets
    ]
    for left_index, (left_start, left_end) in enumerate(ranges):
        for right_index in range(left_index + 1, len(ranges)):
            right_start, right_end = ranges[right_index]
            if max(left_start, right_start) >= min(left_end, right_end):
                continue
            counts[left_index] += 1
            counts[right_index] += 1
            overlap_pairs += 1
    for row, count in zip(rows, counts, strict=True):
        row["overlap_count"] = count
    return overlap_pairs


def validate_unique_assets(assets: list[dict[str, Any]]) -> None:
    ids = [asset["id"] for asset in assets]
    paths = [asset["path"] for asset in assets]
    if len(ids) != len(set(ids)):
        raise CatalogError("duplicate asset IDs")
    if len(paths) != len(set(paths)):
        raise CatalogError("duplicate asset paths")
    for asset in assets:
        start = int(asset["offset"], 16)
        end = start + asset["length"]
        if start <= HZK16_EXCLUDED_OFFSET < end:
            raise CatalogError(
                f"{asset['id']} overlaps HZK16, which must remain excluded"
            )


def build_catalog(
    rom_data: bytes,
    *,
    ips_base_data: bytes | None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    header = pipeline.parse_mapper163_header(rom_data)
    assets: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    package_stats = parse_sprite_packages(rom_data, assets, rows)
    screen_component_count = parse_screen_bundles(rom_data, assets, rows)
    fixed_count = append_fixed_assets(rom_data, assets, rows)
    semantic_alias_count = append_semantic_aliases(rom_data, assets, rows)
    (
        strict_screen_pack_count,
        strict_screen_pack_asset_count,
    ) = append_strict_screen_pack_assets(rom_data, assets, rows)
    validate_unique_assets(assets)
    overlap_pairs = annotate_overlaps(assets, rows)

    manifest: dict[str, Any] = {
        "schema": pipeline.SCHEMA,
        "source_sha256": sha256(rom_data),
        "assets": assets,
    }
    if ips_base_data is not None:
        if len(ips_base_data) != len(rom_data):
            raise CatalogError(
                "the IPS base ROM size differs from the source ROM"
            )
        manifest["ips_base_sha256"] = sha256(ips_base_data)

    stats = {
        **package_stats,
        "screen_component_count": screen_component_count,
        "fixed_chr_count": fixed_count,
        "semantic_alias_count": semantic_alias_count,
        "strict_screen_pack_count": strict_screen_pack_count,
        "strict_screen_pack_asset_count": strict_screen_pack_asset_count,
        "asset_count": len(assets),
        "overlap_pair_count": overlap_pairs,
        "mapper": header["mapper"],
        "prg_bytes": header["prg_bytes"],
        "hzk16_included": False,
    }
    return manifest, rows, stats


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def metadata_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=CSV_FIELDS,
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the complete manifest of CHR-RAM sources in PRG-ROM."
        ),
    )
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument(
        "--ips-base-rom",
        type=Path,
        default=DEFAULT_IPS_BASE_ROM,
        help=(
            "base ROM whose SHA-256 will be recorded in ips_base_sha256"
        ),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--metadata-csv",
        type=Path,
        default=DEFAULT_METADATA,
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate and summarize the catalog without writing files",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        rom_data = args.rom.read_bytes()
        validate_default_rom_binding(args.rom, rom_data)
        ips_base_data = (
            None
            if args.ips_base_rom is None
            else args.ips_base_rom.read_bytes()
        )
        manifest, rows, stats = build_catalog(
            rom_data,
            ips_base_data=ips_base_data,
        )
        if not args.check:
            atomic_write(args.manifest, canonical_json_bytes(manifest))
            atomic_write(args.metadata_csv, metadata_csv_bytes(rows))

        print("Mapper 163 CHR catalog: PASS")
        print(f"- ROM SHA-256 : {manifest['source_sha256']}")
        print(f"- Packages : {stats['package_count']}")
        print(f"- Packaged tiles : {stats['package_tile_count']}")
        print(
            f"- Packaged CHR bytes : 0x{stats['package_chr_bytes']:X}"
        )
        print(
            f"- Variants : {stats['variant_counts']['one_tilemap']} "
            "with 1 tilemap, "
            f"{stats['variant_counts']['two_tilemaps']} with 2 tilemaps, "
            f"{stats['variant_counts']['three_tilemaps']} with 3 tilemaps"
        )
        print(
            f"- Screen bundle components : "
            f"{stats['screen_component_count']}"
        )
        print(f"- Fixed CHR assets : {stats['fixed_chr_count']}")
        print(f"- Semantic aliases : {stats['semantic_alias_count']}")
        print(
            "- Strict screen-packs : "
            f"{stats['strict_screen_pack_count']} records, "
            f"{stats['strict_screen_pack_asset_count']} tilemaps/attributes"
        )
        print(f"- Manifested assets : {stats['asset_count']}")
        print(f"- Overlapping pairs : {stats['overlap_pair_count']}")
        print("- HZK16: excluded")
        if not args.check:
            print(f"- Manifest : {args.manifest.resolve()}")
            print(f"- Metadata : {args.metadata_csv.resolve()}")
        return 0
    except (OSError, CatalogError, pipeline.PipelineError) as exc:
        print(f"Mapper 163 CHR catalog: FAIL ({exc})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
