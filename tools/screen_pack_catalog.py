#!/usr/bin/env python3
"""Catalog structurally bounded screen-pack assets in NJ046 mapper-163 ROMs.

The records used in PRG pairs 16 through 48 contain:

* two screen-grid dimensions at record offsets ``+0x12`` and ``+0x13``;
* a pointer table at ``+0x1C``;
* a CHR source pointer at ``+0x1E``;
* ``N`` contiguous 32x30 tilemaps, followed by ``N`` contiguous 8x8
  attribute tables, where ``N`` is the product of the dimensions.

The static record does not encode the length of the CHR source.  Consequently
the reusable pipeline asset list contains only the 960-byte tilemaps and
64-byte attribute tables.  CHR pointers and descriptor tables remain present
in the machine-readable catalog for later runtime-backed analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CATALOG_SCHEMA = "mapper163-screen-pack-catalog/v1"
MANIFEST_SCHEMA = "mapper163-chr-assets/v1"
INES_HEADER_SIZE = 16
PAIR_SIZE = 0x8000
CPU_BASE = 0x8000
DEFAULT_FIRST_PAIR = 16
DEFAULT_LAST_PAIR = 48
DEFAULT_EXPECTED_RECORDS = 96
TILEMAP_LENGTH = 32 * 30
ATTRIBUTE_LENGTH = 8 * 8
SCREEN_STRIDE = TILEMAP_LENGTH + ATTRIBUTE_LENGTH
OPTIONAL_CHR_VIEW_LENGTH = 0x1000


class CatalogError(ValueError):
    """A validation error that makes a catalog unsafe to generate."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex_offset(value: int, width: int = 6) -> str:
    return f"0x{value:0{width}X}"


def u16le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def ines_info(data: bytes) -> dict[str, int | bool]:
    if len(data) < INES_HEADER_SIZE or data[:4] != b"NES\x1a":
        raise CatalogError("fichier iNES invalide")
    prg_length = data[4] * 0x4000
    chr_length = data[5] * 0x2000
    expected_length = INES_HEADER_SIZE + prg_length + chr_length
    if len(data) != expected_length:
        raise CatalogError(
            f"taille ROM {len(data)}, attendue {expected_length}"
        )
    return {
        "mapper": (data[6] >> 4) | (data[7] & 0xF0),
        "prg_length": prg_length,
        "chr_length": chr_length,
        "battery": bool(data[6] & 0x02),
    }


def scan_screen_pack_records(
    data: bytes,
    *,
    first_pair: int = DEFAULT_FIRST_PAIR,
    last_pair: int = DEFAULT_LAST_PAIR,
) -> list[dict[str, Any]]:
    """Return every screen-pack record satisfying the complete static shape.

    A candidate is accepted only when all pointers resolve inside its 32 KiB
    PRG pair, tilemaps advance by exactly 960 bytes, attributes advance by
    exactly 64 bytes, the two groups are contiguous, and the descriptor area
    consists of ten-byte records followed by ``0xFF``.
    """

    records: list[dict[str, Any]] = []
    for pair in range(first_pair, last_pair + 1):
        pair_base = INES_HEADER_SIZE + pair * PAIR_SIZE
        pair_end = pair_base + PAIR_SIZE
        if pair_end > len(data):
            raise CatalogError(f"paire PRG {pair} hors ROM")

        def to_file(cpu_pointer: int) -> int | None:
            if CPU_BASE <= cpu_pointer <= 0xFFFF:
                return pair_base + cpu_pointer - CPU_BASE
            return None

        pair_records: list[dict[str, Any]] = []
        for record_offset in range(pair_base, pair_end - 0x20):
            columns = data[record_offset + 0x12]
            rows = data[record_offset + 0x13]
            screen_count = columns * rows
            if not (
                1 <= columns <= 8
                and 1 <= rows <= 8
                and 1 <= screen_count <= 16
            ):
                continue

            pointer_table_offset = record_offset + 0x1C
            descriptor_cpu = u16le(data, pointer_table_offset)
            descriptor_offset = to_file(descriptor_cpu)
            if (
                descriptor_offset is None
                or descriptor_offset <= pointer_table_offset
                or descriptor_offset > pair_end
                or (descriptor_offset - pointer_table_offset) % 2
            ):
                continue

            pointer_count = (
                descriptor_offset - pointer_table_offset
            ) // 2
            required_pointer_count = 2 + 2 * screen_count
            if not required_pointer_count <= pointer_count <= 32:
                continue

            cpu_pointers = [
                u16le(data, pointer_table_offset + 2 * index)
                for index in range(pointer_count)
            ]
            maybe_targets = [to_file(value) for value in cpu_pointers]
            if any(
                value is None or not pair_base <= value < pair_end
                for value in maybe_targets
            ):
                continue
            targets = [int(value) for value in maybe_targets]

            tilemap_offsets = targets[2 : 2 + screen_count]
            attribute_offsets = targets[
                2 + screen_count : 2 + 2 * screen_count
            ]
            if any(
                right - left != TILEMAP_LENGTH
                for left, right in zip(
                    tilemap_offsets,
                    tilemap_offsets[1:],
                )
            ):
                continue
            if any(
                right - left != ATTRIBUTE_LENGTH
                for left, right in zip(
                    attribute_offsets,
                    attribute_offsets[1:],
                )
            ):
                continue
            if (
                attribute_offsets[0]
                != tilemap_offsets[0]
                + screen_count * TILEMAP_LENGTH
            ):
                continue

            descriptor_length = tilemap_offsets[0] - descriptor_offset
            if (
                descriptor_length < 1
                or descriptor_length % 10 != 1
                or data[tilemap_offsets[0] - 1] != 0xFF
            ):
                continue

            descriptor_record_count = (descriptor_length - 1) // 10
            descriptor_payloads = []
            for index in range(descriptor_record_count):
                pointer_at = descriptor_offset + index * 10 + 8
                cpu_pointer = u16le(data, pointer_at)
                target = to_file(cpu_pointer)
                descriptor_payloads.append(
                    {
                        "index": index,
                        "pointer_offset": hex_offset(pointer_at),
                        "cpu_pointer": f"0x{cpu_pointer:04X}",
                        "target_offset": (
                            None if target is None else hex_offset(target)
                        ),
                    }
                )

            group_offset = tilemap_offsets[0]
            group_length = screen_count * SCREEN_STRIDE
            chr_offset = targets[1]
            extra_cpu_pointers = cpu_pointers[required_pointer_count:]
            extra_file_pointers = targets[required_pointer_count:]
            repeated_extra_offsets: dict[int, list[int]] = defaultdict(list)
            for index, target in enumerate(extra_file_pointers):
                repeated_extra_offsets[target].append(index)

            extras = []
            for index, (cpu_pointer, target) in enumerate(
                zip(extra_cpu_pointers, extra_file_pointers)
            ):
                if target == group_offset + group_length:
                    relation = "screen_group_end"
                elif (
                    chr_offset
                    <= target
                    < chr_offset + OPTIONAL_CHR_VIEW_LENGTH
                ):
                    relation = "inside_optional_chr_4k_view"
                elif group_offset <= target < group_offset + group_length:
                    relation = "inside_screen_group"
                else:
                    relation = "other"
                same_target_indices = repeated_extra_offsets[target]
                extras.append(
                    {
                        "index": index,
                        "cpu_pointer": f"0x{cpu_pointer:04X}",
                        "target_offset": hex_offset(target),
                        "relation": relation,
                        "same_target_extra_indices": (
                            same_target_indices
                            if len(same_target_indices) > 1
                            else []
                        ),
                    }
                )

            pack_index = len(pair_records)
            pack_id = f"pair{pair:02d}_pack{pack_index:02d}"
            screens = []
            for index, (tilemap_offset, attribute_offset) in enumerate(
                zip(tilemap_offsets, attribute_offsets)
            ):
                screens.append(
                    {
                        "index": index,
                        "tilemap": {
                            "id": (
                                f"{pack_id}_screen{index:02d}_tilemap"
                            ),
                            "offset": hex_offset(tilemap_offset),
                            "length": TILEMAP_LENGTH,
                            "kind": "raw",
                        },
                        "attributes": {
                            "id": (
                                f"{pack_id}_screen{index:02d}_attributes"
                            ),
                            "offset": hex_offset(attribute_offset),
                            "length": ATTRIBUTE_LENGTH,
                            "kind": "raw",
                        },
                    }
                )

            pair_records.append(
                {
                    "id": pack_id,
                    "pair": pair,
                    "pair_file_base": hex_offset(pair_base),
                    "record_offset": hex_offset(record_offset),
                    "dimensions": {
                        "columns": columns,
                        "rows": rows,
                        "screen_count": screen_count,
                    },
                    "pointer_table": {
                        "offset": hex_offset(pointer_table_offset),
                        "length": pointer_count * 2,
                        "pointer_count": pointer_count,
                    },
                    "descriptors": {
                        "id": f"{pack_id}_descriptors",
                        "offset": hex_offset(descriptor_offset),
                        "length": descriptor_length,
                        "record_count": descriptor_record_count,
                        "kind": "raw",
                        "payload_pointers": descriptor_payloads,
                    },
                    "chr_source": {
                        "pointer_offset": hex_offset(
                            pointer_table_offset + 2
                        ),
                        "cpu_pointer": f"0x{cpu_pointers[1]:04X}",
                        "target_offset": hex_offset(chr_offset),
                        "length": None,
                        "note": (
                            "Le record borne le pointeur, pas la longueur."
                        ),
                    },
                    "screen_group": {
                        "offset": hex_offset(group_offset),
                        "length": group_length,
                        "screen_stride": SCREEN_STRIDE,
                    },
                    "screens": screens,
                    "extra_pointers": extras,
                }
            )
        if not pair_records:
            raise CatalogError(
                f"aucun record screen-pack valide dans la paire {pair}"
            )
        records.extend(pair_records)
    return records


def build_pipeline_assets(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return pipeline entries for the strictly bounded graphical blocks.

    For the reference ROM this returns exactly 832 entries: 416 tilemaps and
    416 attribute tables.  Descriptor tables and unbounded CHR pointers are
    intentionally excluded.
    """

    assets = []
    for record in records:
        for screen in record["screens"]:
            for role in ("tilemap", "attributes"):
                block = screen[role]
                assets.append(
                    {
                        "id": block["id"],
                        "path": (
                            f"screen-packs/{role}/{block['id']}.bin"
                        ),
                        "offset": block["offset"],
                        "length": block["length"],
                        "kind": block["kind"],
                    }
                )
    return assets


def bounded_descriptor_assets(
    records: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return bounded descriptor blocks for auditing, not graphic editing."""

    assets = []
    for record in records:
        descriptor = record["descriptors"]
        assets.append(
            {
                "id": descriptor["id"],
                "path": (
                    "screen-packs/descriptors/"
                    f"{descriptor['id']}.bin"
                ),
                "offset": descriptor["offset"],
                "length": descriptor["length"],
                "kind": "raw",
            }
        )
    return assets


def physical_overlaps_with_optional_chr_views(
    records: Iterable[dict[str, Any]],
    pipeline_assets: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Describe overlaps without asserting that every CHR pointer spans 4 KiB."""

    record_list = list(records)
    ranges = [
        (
            asset["id"],
            int(asset["offset"], 16),
            int(asset["offset"], 16) + asset["length"],
            "pipeline_asset",
        )
        for asset in pipeline_assets
    ]
    ranges.extend(
        (
            f'{record["id"]}_optional_chr_4k',
            int(record["chr_source"]["target_offset"], 16),
            int(record["chr_source"]["target_offset"], 16)
            + OPTIONAL_CHR_VIEW_LENGTH,
            "optional_chr_view",
        )
        for record in record_list
    )
    ranges.sort(key=lambda item: (item[1], item[2], item[0]))
    overlaps = []
    for index, left in enumerate(ranges):
        for right in ranges[index + 1 :]:
            if right[1] >= left[2]:
                break
            start = max(left[1], right[1])
            end = min(left[2], right[2])
            if start < end:
                overlaps.append(
                    {
                        "left": left[0],
                        "right": right[0],
                        "offset": hex_offset(start),
                        "length": end - start,
                        "left_class": left[3],
                        "right_class": right[3],
                    }
                )
    return overlaps


def content_duplicates(
    data: bytes,
    pipeline_assets: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group byte-identical assets stored at distinct physical offsets."""

    groups: dict[tuple[str, int, str], list[str]] = defaultdict(list)
    for asset in pipeline_assets:
        role = (
            "attributes"
            if asset["id"].endswith("_attributes")
            else "tilemap"
        )
        offset = int(asset["offset"], 16)
        length = asset["length"]
        digest = sha256(data[offset : offset + length])
        groups[(role, length, digest)].append(asset["id"])
    duplicates = []
    for (role, length, digest), asset_ids in sorted(groups.items()):
        if len(asset_ids) > 1:
            duplicates.append(
                {
                    "role": role,
                    "length": length,
                    "sha256": digest,
                    "asset_ids": asset_ids,
                }
            )
    return duplicates


def build_catalog(
    rom_path: str | Path,
    *,
    first_pair: int = DEFAULT_FIRST_PAIR,
    last_pair: int = DEFAULT_LAST_PAIR,
    expected_records: int | None = DEFAULT_EXPECTED_RECORDS,
) -> dict[str, Any]:
    """Build a reusable catalog containing both records and pipeline assets."""

    path = Path(rom_path)
    data = path.read_bytes()
    info = ines_info(data)
    if info["mapper"] != 163:
        raise CatalogError(f"mapper {info['mapper']}, attendu 163")
    if info["chr_length"] != 0:
        raise CatalogError("CHR-ROM non nulle; CHR-RAM attendue")

    records = scan_screen_pack_records(
        data,
        first_pair=first_pair,
        last_pair=last_pair,
    )
    if expected_records is not None and len(records) != expected_records:
        raise CatalogError(
            f"{len(records)} records, attendu {expected_records}"
        )
    pipeline_assets = build_pipeline_assets(records)
    descriptors = bounded_descriptor_assets(records)
    return {
        "schema": CATALOG_SCHEMA,
        "rom": {
            "path": str(path),
            "size": len(data),
            "sha256": sha256(data),
            **info,
        },
        "pair_range": {
            "first": first_pair,
            "last": last_pair,
        },
        "record_count": len(records),
        "pipeline_asset_count": len(pipeline_assets),
        "descriptor_asset_count": len(descriptors),
        "records": records,
        "pipeline_assets": pipeline_assets,
        "bounded_descriptor_assets": descriptors,
        "physical_overlaps_with_optional_chr_views": (
            physical_overlaps_with_optional_chr_views(
                records,
                pipeline_assets,
            )
        ),
        "content_duplicates": content_duplicates(
            data,
            pipeline_assets,
        ),
    }


def build_pipeline_manifest(
    catalog: dict[str, Any],
) -> dict[str, Any]:
    """Return a manifest accepted by ``chr_asset_pipeline.py``."""

    source_hash = catalog["rom"]["sha256"]
    return {
        "schema": MANIFEST_SCHEMA,
        "source_sha256": source_hash,
        "ips_base_sha256": source_hash,
        "assets": catalog["pipeline_assets"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Catalogue les tilemaps/attributs strictement bornés des "
            "screen-packs mapper 163."
        )
    )
    parser.add_argument("rom", type=Path)
    parser.add_argument(
        "--first-pair",
        type=int,
        default=DEFAULT_FIRST_PAIR,
    )
    parser.add_argument(
        "--last-pair",
        type=int,
        default=DEFAULT_LAST_PAIR,
    )
    parser.add_argument(
        "--expect-records",
        type=int,
        default=DEFAULT_EXPECTED_RECORDS,
    )
    parser.add_argument(
        "--manifest",
        action="store_true",
        help="émet seulement le manifeste strict pour chr_asset_pipeline.py",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    catalog = build_catalog(
        args.rom,
        first_pair=args.first_pair,
        last_pair=args.last_pair,
        expected_records=args.expect_records,
    )
    result = (
        build_pipeline_manifest(catalog)
        if args.manifest
        else catalog
    )
    encoded = (
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    )
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
