#!/usr/bin/env python3
"""Manifest-driven CHR asset export and recompilation for mapper 163 ROMs.

The ROM uses CHR-RAM, so the editable graphics are PRG-ROM source blocks
rather than a conventional iNES CHR-ROM payload.  Assets may intentionally
overlap.  Recompilation is baseline-aware: only bytes changed relative to an
asset's exported baseline propose a write.  An unchanged alias therefore does
not overwrite a neighbouring edit, while contradictory edits to the same
physical byte are rejected.

Manifest format (JSON):

{
  "schema": "mapper163-chr-assets/v1",
  "source_sha256": "<64 hex digits>",
  "ips_base_sha256": "<optional 64 hex digits>",
  "assets": [
    {
      "id": "title_pt0",
      "path": "title/pt0.chr",
      "offset": "0x070FFB",
      "length": 4096,
      "kind": "chr"
    }
  ]
}

``kind`` is either ``chr`` (raw NES 8x8 2-bpp tiles, length divisible by
16) or ``raw``.  Paths are POSIX-style and always relative to the pack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA = "mapper163-chr-assets/v1"
LOCK_SCHEMA = "mapper163-chr-assets-lock/v1"
MAPPER = 163
INES_HEADER_SIZE = 16
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
ASSET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HEX_OFFSET_RE = re.compile(r"^0x[0-9A-Fa-f]+$")
ASSET_KINDS = {"chr", "raw"}


class PipelineError(ValueError):
    """A validation failure that must prevent artifact creation."""


@dataclass(frozen=True)
class Asset:
    asset_id: str
    path: PurePosixPath
    offset: int
    length: int
    kind: str

    @property
    def end(self) -> int:
        return self.offset + self.length


@dataclass(frozen=True)
class Manifest:
    source_sha256: str
    ips_base_sha256: str | None
    assets: tuple[Asset, ...]
    file_sha256: str


@dataclass(frozen=True)
class AssetState:
    asset: Asset
    baseline: bytes
    work: bytes


@dataclass(frozen=True)
class PreparedPack:
    manifest: Manifest
    source: bytes
    source_path: Path
    pack_dir: Path
    states: tuple[AssetState, ...]
    lock: dict[str, Any]


@dataclass(frozen=True)
class MergeResult:
    patched: bytes
    report: dict[str, Any]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PipelineError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_bytes(raw: bytes, label: str) -> Any:
    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PipelineError(f"{label} invalid JSON: {exc}") from exc


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _validate_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise PipelineError(f"{field} must be a hexadecimal SHA-256")
    return value.lower()


def _parse_safe_relative_path(value: Any, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise PipelineError(f"{field} must be a nonempty relative path")
    if "\\" in value or ":" in value:
        raise PipelineError(
            f"{field} must use a relative POSIX path without a drive"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise PipelineError(f"{field} escapes the pack: {value!r}")
    return path


def _parse_offset(value: Any, field: str) -> int:
    if not isinstance(value, str) or not HEX_OFFSET_RE.fullmatch(value):
        raise PipelineError(f"{field} must have the form 0x1234")
    return int(value, 16)


def load_manifest(path: str | Path) -> Manifest:
    manifest_path = Path(path)
    raw = manifest_path.read_bytes()
    value = _load_json_bytes(raw, "manifest")
    if not isinstance(value, dict):
        raise PipelineError("the manifest must be a JSON object")

    allowed_top = {
        "schema",
        "source_sha256",
        "ips_base_sha256",
        "assets",
    }
    unknown = sorted(set(value) - allowed_top)
    if unknown:
        raise PipelineError(
            "unknown manifest field(s): " + ", ".join(unknown)
        )
    if value.get("schema") != SCHEMA:
        raise PipelineError(
            f"manifest schema {value.get('schema')!r}, expected {SCHEMA!r}"
        )

    source_hash = _validate_sha256(
        value.get("source_sha256"),
        "source_sha256",
    )
    ips_base_value = value.get("ips_base_sha256")
    ips_base_hash = (
        None
        if ips_base_value is None
        else _validate_sha256(ips_base_value, "ips_base_sha256")
    )

    raw_assets = value.get("assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise PipelineError("assets must be a nonempty list")

    assets: list[Asset] = []
    seen_ids: set[str] = set()
    seen_paths: set[PurePosixPath] = set()
    allowed_asset = {"id", "path", "offset", "length", "kind"}
    for index, item in enumerate(raw_assets):
        label = f"assets[{index}]"
        if not isinstance(item, dict):
            raise PipelineError(f"{label} must be an object")
        unknown_asset = sorted(set(item) - allowed_asset)
        missing_asset = sorted(allowed_asset - set(item))
        if unknown_asset:
            raise PipelineError(
                f"{label}: unknown field(s): "
                + ", ".join(unknown_asset)
            )
        if missing_asset:
            raise PipelineError(
                f"{label}: missing field(s): "
                + ", ".join(missing_asset)
            )

        asset_id = item["id"]
        if (
            not isinstance(asset_id, str)
            or not ASSET_ID_RE.fullmatch(asset_id)
        ):
            raise PipelineError(f"{label}.id invalid: {asset_id!r}")
        if asset_id in seen_ids:
            raise PipelineError(f"duplicate asset ID: {asset_id}")
        seen_ids.add(asset_id)

        relative_path = _parse_safe_relative_path(
            item["path"],
            f"{label}.path",
        )
        if relative_path in seen_paths:
            raise PipelineError(f"duplicate asset path: {relative_path}")
        seen_paths.add(relative_path)

        offset = _parse_offset(item["offset"], f"{label}.offset")
        length = item["length"]
        if (
            isinstance(length, bool)
            or not isinstance(length, int)
            or length <= 0
        ):
            raise PipelineError(f"{label}.length must be a positive integer")
        kind = item["kind"]
        if not isinstance(kind, str) or kind not in ASSET_KINDS:
            raise PipelineError(
                f"{label}.kind {kind!r}, expected 'chr' or 'raw'"
            )
        if kind == "chr" and length % 16:
            raise PipelineError(
                f"{label}: a CHR asset must be a multiple of 16 bytes"
            )

        assets.append(
            Asset(
                asset_id=asset_id,
                path=relative_path,
                offset=offset,
                length=length,
                kind=kind,
            )
        )

    return Manifest(
        source_sha256=source_hash,
        ips_base_sha256=ips_base_hash,
        assets=tuple(assets),
        file_sha256=sha256(raw),
    )


def parse_mapper163_header(data: bytes) -> dict[str, int | bool]:
    if len(data) < INES_HEADER_SIZE or data[:4] != b"NES\x1A":
        raise PipelineError("missing iNES header")
    header = data[:INES_HEADER_SIZE]
    if (header[7] & 0x0C) == 0x08:
        raise PipelineError("NES 2.0 is not supported by this pipeline")
    mapper = (header[6] >> 4) | (header[7] & 0xF0)
    prg_bytes = header[4] * 0x4000
    chr_bytes = header[5] * 0x2000
    trainer = bool(header[6] & 0x04)
    if mapper != MAPPER:
        raise PipelineError(f"mapper {mapper}, expected {MAPPER}")
    if trainer:
        raise PipelineError("iNES trainer is not supported")
    if chr_bytes != 0:
        raise PipelineError(
            "CHR-ROM present; the pipeline targets CHR-RAM sources in PRG"
        )
    if prg_bytes <= 0:
        raise PipelineError("zero PRG size")
    expected_size = INES_HEADER_SIZE + prg_bytes
    if len(data) != expected_size:
        raise PipelineError(
            f"ROM size {len(data)}, expected {expected_size} according to the header"
        )
    return {
        "mapper": mapper,
        "prg_bytes": prg_bytes,
        "chr_bytes": chr_bytes,
        "trainer": trainer,
        "file_bytes": len(data),
    }


def _validate_source(
    data: bytes,
    expected_sha256: str,
) -> dict[str, int | bool]:
    header = parse_mapper163_header(data)
    actual_hash = sha256(data)
    if actual_hash != expected_sha256:
        raise PipelineError(
            "unexpected source ROM SHA-256: "
            f"{actual_hash} instead of {expected_sha256}"
        )
    return header


def _validate_asset_bounds(
    assets: Iterable[Asset],
    rom_size: int,
) -> None:
    for asset in assets:
        if asset.offset < INES_HEADER_SIZE:
            raise PipelineError(
                f"asset {asset.asset_id}: offset inside the iNES header"
            )
        if asset.end > rom_size:
            raise PipelineError(
                f"asset {asset.asset_id}: range "
                f"0x{asset.offset:06X}-0x{asset.end:06X} outside ROM"
            )


def _asset_overlaps(assets: Iterable[Asset]) -> list[dict[str, Any]]:
    ordered = list(assets)
    overlaps: list[dict[str, Any]] = []
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            start = max(left.offset, right.offset)
            end = min(left.end, right.end)
            if start >= end:
                continue
            overlaps.append(
                {
                    "left": left.asset_id,
                    "right": right.asset_id,
                    "offset": f"0x{start:06X}",
                    "length": end - start,
                }
            )
    return overlaps


def _safe_join(root: Path, relative: PurePosixPath) -> Path:
    root_resolved = root.resolve()
    candidate = root.joinpath(*relative.parts)
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(root_resolved):
        raise PipelineError(f"path escapes the pack: {relative}")
    return candidate


def _atomic_write(path: Path, data: bytes) -> None:
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


def _publish_directory(temporary: Path, destination: Path) -> None:
    """Publish an exported pack, tolerating short OneDrive scan locks.

    A same-directory rename is the normal atomic path.  OneDrive can
    transiently keep a freshly populated directory open on Windows/WSL and
    return ``EACCES`` for that rename, so retry briefly and then use a guarded
    copy fallback.  A failed fallback never leaves a partial destination.
    """

    for attempt in range(8):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError:
            if attempt == 7:
                break
            time.sleep(0.1 * (attempt + 1))

    try:
        shutil.copytree(temporary, destination)
    except Exception:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise
    shutil.rmtree(temporary)


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    body = chunk_type + payload
    return (
        len(payload).to_bytes(4, "big")
        + body
        + (zlib.crc32(body) & 0xFFFFFFFF).to_bytes(4, "big")
    )


def render_chr_png(
    data: bytes,
    *,
    tiles_per_row: int = 16,
    scale: int = 2,
) -> bytes:
    """Render raw NES 2-bpp tiles to a deterministic grayscale PNG."""
    if not data or len(data) % 16:
        raise PipelineError("CHR rendering: size is not a multiple of 16")
    if tiles_per_row <= 0 or scale <= 0:
        raise PipelineError("CHR rendering: invalid geometry")

    tile_count = len(data) // 16
    columns = min(tiles_per_row, tile_count)
    rows = (tile_count + columns - 1) // columns
    width = columns * 8 * scale
    height = rows * 8 * scale
    pixels = bytearray([255] * (width * height))
    palette = (255, 170, 85, 0)

    for tile_index in range(tile_count):
        tile = data[tile_index * 16 : (tile_index + 1) * 16]
        tile_x = (tile_index % columns) * 8
        tile_y = (tile_index // columns) * 8
        for y in range(8):
            low = tile[y]
            high = tile[y + 8]
            for x in range(8):
                shift = 7 - x
                color = ((low >> shift) & 1) | (
                    ((high >> shift) & 1) << 1
                )
                gray = palette[color]
                pixel_x = (tile_x + x) * scale
                pixel_y = (tile_y + y) * scale
                for sy in range(scale):
                    row_start = (pixel_y + sy) * width + pixel_x
                    pixels[row_start : row_start + scale] = bytes(
                        [gray] * scale
                    )

    scanlines = bytearray()
    for y in range(height):
        scanlines.append(0)
        scanlines.extend(pixels[y * width : (y + 1) * width])
    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,
        0,
        0,
        0,
        0,
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _lock_asset_entry(asset: Asset, baseline: bytes) -> dict[str, Any]:
    return {
        "id": asset.asset_id,
        "path": asset.path.as_posix(),
        "offset": f"0x{asset.offset:06X}",
        "length": asset.length,
        "kind": asset.kind,
        "baseline_sha256": sha256(baseline),
    }


def export_pack(
    manifest_path: str | Path,
    rom_path: str | Path,
    out_dir: str | Path,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    source_path = Path(rom_path)
    source = source_path.read_bytes()
    header = _validate_source(source, manifest.source_sha256)
    _validate_asset_bounds(manifest.assets, len(source))

    destination = Path(out_dir)
    if destination.exists():
        raise PipelineError(
            f"export directory already exists: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            dir=destination.parent,
        )
    )
    try:
        lock_assets: list[dict[str, Any]] = []
        for asset in manifest.assets:
            block = source[asset.offset : asset.end]
            baseline_path = _safe_join(
                temporary / "baseline",
                asset.path,
            )
            work_path = _safe_join(temporary / "work", asset.path)
            baseline_path.parent.mkdir(parents=True, exist_ok=True)
            work_path.parent.mkdir(parents=True, exist_ok=True)
            baseline_path.write_bytes(block)
            work_path.write_bytes(block)
            if asset.kind == "chr":
                preview_relative = PurePosixPath(
                    asset.path.as_posix() + ".png"
                )
                preview_path = _safe_join(
                    temporary / "previews",
                    preview_relative,
                )
                preview_path.parent.mkdir(parents=True, exist_ok=True)
                preview_path.write_bytes(render_chr_png(block))
            lock_assets.append(_lock_asset_entry(asset, block))

        (temporary / "previews").mkdir(parents=True, exist_ok=True)
        lock = {
            "schema": LOCK_SCHEMA,
            "manifest_sha256": manifest.file_sha256,
            "source_sha256": sha256(source),
            "source_size": len(source),
            "header": header,
            "assets": lock_assets,
            "overlaps": _asset_overlaps(manifest.assets),
        }
        (temporary / "pack.lock.json").write_bytes(
            _canonical_json_bytes(lock)
        )
        _publish_directory(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    return {
        "result": "PASS",
        "command": "export",
        "pack": str(destination.resolve()),
        "source_sha256": sha256(source),
        "asset_count": len(manifest.assets),
        "overlap_count": len(_asset_overlaps(manifest.assets)),
    }


def _load_lock(pack_dir: Path) -> dict[str, Any]:
    lock_path = pack_dir / "pack.lock.json"
    if not lock_path.is_file():
        raise PipelineError(f"missing lock: {lock_path}")
    value = _load_json_bytes(lock_path.read_bytes(), "lock")
    if not isinstance(value, dict) or value.get("schema") != LOCK_SCHEMA:
        raise PipelineError("invalid lock schema")
    return value


def prepare_pack(
    manifest_path: str | Path,
    pack_dir: str | Path,
    rom_path: str | Path,
) -> PreparedPack:
    manifest = load_manifest(manifest_path)
    source_path = Path(rom_path)
    source = source_path.read_bytes()
    _validate_source(source, manifest.source_sha256)
    _validate_asset_bounds(manifest.assets, len(source))

    pack = Path(pack_dir)
    lock = _load_lock(pack)
    if lock.get("manifest_sha256") != manifest.file_sha256:
        raise PipelineError("the manifest does not match the lock")
    if lock.get("source_sha256") != sha256(source):
        raise PipelineError("the source ROM does not match the lock")
    if lock.get("source_size") != len(source):
        raise PipelineError("the ROM size does not match the lock")

    raw_lock_assets = lock.get("assets")
    if not isinstance(raw_lock_assets, list):
        raise PipelineError("missing asset list in the lock")
    lock_by_id: dict[str, dict[str, Any]] = {}
    for item in raw_lock_assets:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise PipelineError("invalid asset entry in the lock")
        asset_id = item["id"]
        if asset_id in lock_by_id:
            raise PipelineError(f"duplicate asset in the lock: {asset_id}")
        lock_by_id[asset_id] = item
    if set(lock_by_id) != {asset.asset_id for asset in manifest.assets}:
        raise PipelineError("lock assets differ from the manifest")

    states: list[AssetState] = []
    for asset in manifest.assets:
        item = lock_by_id[asset.asset_id]
        expected_metadata = {
            "path": asset.path.as_posix(),
            "offset": f"0x{asset.offset:06X}",
            "length": asset.length,
            "kind": asset.kind,
        }
        for key, expected in expected_metadata.items():
            if item.get(key) != expected:
                raise PipelineError(
                    f"asset {asset.asset_id}: {key} in the lock is inconsistent"
                )

        baseline_path = _safe_join(pack / "baseline", asset.path)
        work_path = _safe_join(pack / "work", asset.path)
        if not baseline_path.is_file():
            raise PipelineError(
                f"asset {asset.asset_id}: missing baseline"
            )
        if not work_path.is_file():
            raise PipelineError(f"asset {asset.asset_id}: missing work file")
        baseline = baseline_path.read_bytes()
        work = work_path.read_bytes()
        if len(baseline) != asset.length:
            raise PipelineError(
                f"asset {asset.asset_id}: baseline size "
                f"{len(baseline)}, expected {asset.length}"
            )
        if len(work) != asset.length:
            raise PipelineError(
                f"asset {asset.asset_id}: work size "
                f"{len(work)}, expected {asset.length}"
            )
        expected_baseline_hash = item.get("baseline_sha256")
        if sha256(baseline) != expected_baseline_hash:
            raise PipelineError(
                f"asset {asset.asset_id}: incorrect baseline hash"
            )
        source_block = source[asset.offset : asset.end]
        if baseline != source_block:
            raise PipelineError(
                f"asset {asset.asset_id}: baseline differs from the ROM"
            )
        states.append(
            AssetState(
                asset=asset,
                baseline=baseline,
                work=work,
            )
        )

    expected_overlaps = _asset_overlaps(manifest.assets)
    if lock.get("overlaps") != expected_overlaps:
        raise PipelineError("the lock overlap matrix is inconsistent")

    return PreparedPack(
        manifest=manifest,
        source=source,
        source_path=source_path,
        pack_dir=pack,
        states=tuple(states),
        lock=lock,
    )


def _merge_intervals(
    intervals: Iterable[tuple[int, int]],
) -> list[tuple[int, int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def _changed_ranges(offsets: Iterable[int]) -> list[dict[str, Any]]:
    ordered = sorted(set(offsets))
    if not ordered:
        return []
    ranges: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for offset in ordered[1:]:
        if offset != previous + 1:
            ranges.append((start, previous + 1))
            start = offset
        previous = offset
    ranges.append((start, previous + 1))
    return [
        {"offset": f"0x{start:06X}", "length": end - start}
        for start, end in ranges
    ]


def merge_pack(prepared: PreparedPack) -> MergeResult:
    # offset -> (value, proposing asset ids)
    proposals: dict[int, tuple[int, list[str]]] = {}
    logical_changes = 0
    per_asset_logical: dict[str, int] = {}

    for state in prepared.states:
        changed = 0
        for index, (before, after) in enumerate(
            zip(state.baseline, state.work, strict=True)
        ):
            if before == after:
                continue
            changed += 1
            logical_changes += 1
            absolute = state.asset.offset + index
            existing = proposals.get(absolute)
            if existing is None:
                proposals[absolute] = (after, [state.asset.asset_id])
                continue
            existing_value, owners = existing
            if existing_value != after:
                raise PipelineError(
                    "overlap conflict at "
                    f"0x{absolute:06X}: "
                    f"{'/'.join(owners)} proposes 0x{existing_value:02X}, "
                    f"{state.asset.asset_id} proposes 0x{after:02X}"
                )
            owners.append(state.asset.asset_id)
        per_asset_logical[state.asset.asset_id] = changed

    patched = bytearray(prepared.source)
    for offset, (value, _) in sorted(proposals.items()):
        patched[offset] = value
    patched_bytes = bytes(patched)

    physical_offsets = {
        offset
        for offset, (before, after) in enumerate(
            zip(prepared.source, patched_bytes, strict=True)
        )
        if before != after
    }
    whitelist = _merge_intervals(
        (state.asset.offset, state.asset.end)
        for state in prepared.states
    )
    unexpected = [
        offset
        for offset in physical_offsets
        if not any(start <= offset < end for start, end in whitelist)
    ]
    if unexpected:
        raise PipelineError(
            "diff outside whitelist: "
            + ", ".join(f"0x{offset:06X}" for offset in unexpected[:8])
        )

    assets_report: list[dict[str, Any]] = []
    for state in prepared.states:
        output_block = patched_bytes[
            state.asset.offset : state.asset.end
        ]
        propagated = sum(
            left != right
            for left, right in zip(output_block, state.work, strict=True)
        )
        output_changes = sum(
            left != right
            for left, right in zip(
                output_block,
                state.baseline,
                strict=True,
            )
        )
        assets_report.append(
            {
                "id": state.asset.asset_id,
                "path": state.asset.path.as_posix(),
                "offset": f"0x{state.asset.offset:06X}",
                "length": state.asset.length,
                "kind": state.asset.kind,
                "baseline_sha256": sha256(state.baseline),
                "work_sha256": sha256(state.work),
                "output_sha256": sha256(output_block),
                "logical_changed_bytes": per_asset_logical[
                    state.asset.asset_id
                ],
                "output_changed_bytes": output_changes,
                "propagated_alias_bytes": propagated,
            }
        )

    shared_offsets = sum(
        1 for _, owners in proposals.values() if len(owners) > 1
    )
    whitelist_bytes = sum(end - start for start, end in whitelist)
    report = {
        "schema": "mapper163-chr-assets-report/v1",
        "result": "PASS",
        "source": {
            "path": str(prepared.source_path.resolve()),
            "sha256": sha256(prepared.source),
            "size": len(prepared.source),
        },
        "manifest_sha256": prepared.manifest.file_sha256,
        "pack": str(prepared.pack_dir.resolve()),
        "output_sha256": sha256(patched_bytes),
        "logical_changed_bytes": logical_changes,
        "physical_changed_bytes": len(physical_offsets),
        "shared_proposal_offsets": shared_offsets,
        "whitelist_bytes": whitelist_bytes,
        "changed_ranges": _changed_ranges(physical_offsets),
        "overlaps": _asset_overlaps(prepared.manifest.assets),
        "assets": assets_report,
    }
    return MergeResult(patched=patched_bytes, report=report)


def diff_pack(
    manifest_path: str | Path,
    pack_dir: str | Path,
    rom_path: str | Path,
) -> dict[str, Any]:
    return merge_pack(
        prepare_pack(manifest_path, pack_dir, rom_path)
    ).report


def _validate_reextraction(
    prepared: PreparedPack,
    result: MergeResult,
) -> None:
    report_by_id = {
        item["id"]: item for item in result.report["assets"]
    }
    for state in prepared.states:
        extracted = result.patched[
            state.asset.offset : state.asset.end
        ]
        expected_hash = report_by_id[state.asset.asset_id]["output_sha256"]
        if sha256(extracted) != expected_hash:
            raise PipelineError(
                f"incorrect asset roundtrip for {state.asset.asset_id}"
            )


def verify_pack(
    manifest_path: str | Path,
    pack_dir: str | Path,
    rom_path: str | Path,
) -> dict[str, Any]:
    prepared = prepare_pack(manifest_path, pack_dir, rom_path)
    result = merge_pack(prepared)
    _validate_reextraction(prepared, result)
    return result.report


def build_ips(base: bytes, patched: bytes) -> bytes:
    if len(base) != len(patched):
        raise PipelineError("IPS base and output sizes differ")
    output = bytearray(b"PATCH")
    cursor = 0
    while cursor < len(base):
        while cursor < len(base) and base[cursor] == patched[cursor]:
            cursor += 1
        if cursor >= len(base):
            break
        start = cursor
        while cursor < len(base) and base[cursor] != patched[cursor]:
            cursor += 1
        block = patched[start:cursor]
        block_offset = start
        while block:
            chunk = block[:0xFFFF]
            if block_offset > 0xFFFFFF:
                raise PipelineError("IPS offset exceeds 24 bits")
            output.extend(block_offset.to_bytes(3, "big"))
            output.extend(len(chunk).to_bytes(2, "big"))
            output.extend(chunk)
            block_offset += len(chunk)
            block = block[len(chunk) :]
    output.extend(b"EOF")
    return bytes(output)


def apply_ips(base: bytes, patch: bytes) -> bytes:
    if not patch.startswith(b"PATCH"):
        raise PipelineError("missing IPS signature")
    output = bytearray(base)
    cursor = 5
    while True:
        if patch[cursor : cursor + 3] == b"EOF":
            cursor += 3
            break
        if cursor + 5 > len(patch):
            raise PipelineError("truncated IPS")
        offset = int.from_bytes(patch[cursor : cursor + 3], "big")
        size = int.from_bytes(patch[cursor + 3 : cursor + 5], "big")
        cursor += 5
        if size == 0:
            if cursor + 3 > len(patch):
                raise PipelineError("truncated IPS RLE record")
            repeat = int.from_bytes(patch[cursor : cursor + 2], "big")
            value = patch[cursor + 2]
            cursor += 3
            payload = bytes([value]) * repeat
        else:
            if cursor + size > len(patch):
                raise PipelineError("truncated IPS record")
            payload = patch[cursor : cursor + size]
            cursor += size
        end = offset + len(payload)
        if end > len(output):
            raise PipelineError("IPS record outside ROM")
        output[offset:end] = payload
    if cursor != len(patch):
        raise PipelineError("data after IPS EOF")
    return bytes(output)


def _validate_ips_base(
    data: bytes,
    manifest: Manifest,
    source_size: int,
) -> None:
    parse_mapper163_header(data)
    if len(data) != source_size:
        raise PipelineError("IPS base size differs from the source ROM")
    actual_hash = sha256(data)
    if (
        manifest.ips_base_sha256 is not None
        and actual_hash != manifest.ips_base_sha256
    ):
        raise PipelineError(
            "unexpected IPS base SHA-256: "
            f"{actual_hash} instead of {manifest.ips_base_sha256}"
        )


def _validate_compile_paths(
    prepared: PreparedPack,
    manifest_path: str | Path,
    ips_base_path: Path,
    outputs: dict[str, Path],
) -> None:
    resolved_outputs = {
        label: path.resolve() for label, path in outputs.items()
    }
    output_owners: dict[Path, str] = {}
    for label, path in resolved_outputs.items():
        previous = output_owners.get(path)
        if previous is not None:
            raise PipelineError(
                f"outputs {previous} and {label} are identical: {path}"
            )
        output_owners[path] = label

    protected_inputs = {
        prepared.source_path.resolve(): "ROM source",
        ips_base_path.resolve(): "base IPS",
        Path(manifest_path).resolve(): "manifest",
        (prepared.pack_dir / "pack.lock.json").resolve(): "pack lock",
    }
    pack_root = prepared.pack_dir.resolve()
    for label, path in resolved_outputs.items():
        protected = protected_inputs.get(path)
        if protected is not None:
            raise PipelineError(
                f"output {label} cannot overwrite {protected}"
            )
        if path.is_relative_to(pack_root):
            raise PipelineError(
                f"output {label} cannot be written inside the pack"
            )


def compile_pack(
    manifest_path: str | Path,
    pack_dir: str | Path,
    rom_path: str | Path,
    ips_base_path: str | Path,
    out_rom_path: str | Path,
    out_ips_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    prepared = prepare_pack(manifest_path, pack_dir, rom_path)
    result = merge_pack(prepared)
    _validate_reextraction(prepared, result)

    ips_base_file = Path(ips_base_path)
    ips_base = ips_base_file.read_bytes()
    _validate_ips_base(
        ips_base,
        prepared.manifest,
        len(prepared.source),
    )
    ips = build_ips(ips_base, result.patched)
    if apply_ips(ips_base, ips) != result.patched:
        raise PipelineError("IPS roundtrip differs from the compiled ROM")

    out_rom = Path(out_rom_path)
    out_ips = Path(out_ips_path)
    report_file = Path(report_path)
    _validate_compile_paths(
        prepared,
        manifest_path,
        ips_base_file,
        {
            "ROM": out_rom,
            "IPS": out_ips,
            "rapport": report_file,
        },
    )

    report = dict(result.report)
    report["command"] = "compile"
    report["output"] = {
        "rom_path": str(out_rom.resolve()),
        "rom_sha256": sha256(result.patched),
        "ips_path": str(out_ips.resolve()),
        "ips_sha256": sha256(ips),
        "ips_base_path": str(ips_base_file.resolve()),
        "ips_base_sha256": sha256(ips_base),
        "ips_roundtrip": True,
    }
    report_bytes = _canonical_json_bytes(report)

    _atomic_write(out_rom, result.patched)
    _atomic_write(out_ips, ips)
    _atomic_write(report_file, report_bytes)
    return report


def roundtrip_pack(
    manifest_path: str | Path,
    pack_dir: str | Path,
    rom_path: str | Path,
    ips_base_path: str | Path | None = None,
) -> dict[str, Any]:
    prepared = prepare_pack(manifest_path, pack_dir, rom_path)
    result = merge_pack(prepared)
    _validate_reextraction(prepared, result)

    if ips_base_path is None:
        ips_base = prepared.source
        ips_base_label = str(prepared.source_path.resolve())
    else:
        ips_base_file = Path(ips_base_path)
        ips_base = ips_base_file.read_bytes()
        _validate_ips_base(
            ips_base,
            prepared.manifest,
            len(prepared.source),
        )
        ips_base_label = str(ips_base_file.resolve())
    ips = build_ips(ips_base, result.patched)
    if apply_ips(ips_base, ips) != result.patched:
        raise PipelineError("incorrect IPS roundtrip")

    report = dict(result.report)
    report["command"] = "roundtrip"
    report["roundtrip"] = {
        "assets": True,
        "ips": True,
        "ips_base": ips_base_label,
        "noop": result.patched == prepared.source,
    }
    return report


def _write_optional_report(
    report: dict[str, Any],
    path: str | None,
) -> None:
    if path:
        _atomic_write(Path(path), _canonical_json_bytes(report))


def _print_report(report: dict[str, Any]) -> None:
    print("Mapper 163 CHR asset pipeline: PASS")
    if "source" in report:
        print(f"- Source SHA-256 : {report['source']['sha256']}")
    if "asset_count" in report:
        print(f"- Assets : {report['asset_count']}")
        print(f"- Overlaps : {report['overlap_count']}")
        print(f"- Pack : {report['pack']}")
        return
    print(f"- Assets : {len(report['assets'])}")
    print(f"- Logical changes : {report['logical_changed_bytes']}")
    print(f"- Physical changes : {report['physical_changed_bytes']}")
    print(f"- Physical whitelist : {report['whitelist_bytes']} bytes")
    print(f"- Shared proposals : {report['shared_proposal_offsets']}")
    propagated = sum(
        item["propagated_alias_bytes"] for item in report["assets"]
    )
    print(f"- Bytes propagated into aliases : {propagated}")
    print(f"- Output SHA-256 : {report['output_sha256']}")


def _add_pack_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--rom", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export and recompile mapper 163 CHR assets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser(
        "export",
        help="export baseline/work/previews and create the lock",
    )
    export.add_argument("--manifest", required=True)
    export.add_argument("--rom", required=True)
    export.add_argument("--out", required=True)

    diff = subparsers.add_parser(
        "diff",
        help="compare work files with baselines and simulate merging",
    )
    _add_pack_arguments(diff)
    diff.add_argument("--report")

    verify = subparsers.add_parser(
        "verify",
        help="validate source, lock, assets, overlaps and asset roundtrip",
    )
    _add_pack_arguments(verify)
    verify.add_argument("--report")

    compile_parser = subparsers.add_parser(
        "compile",
        help="compile the ROM, IPS and a JSON report",
    )
    _add_pack_arguments(compile_parser)
    compile_parser.add_argument("--ips-base", required=True)
    compile_parser.add_argument("--out-rom", required=True)
    compile_parser.add_argument("--out-ips", required=True)
    compile_parser.add_argument("--report", required=True)

    roundtrip = subparsers.add_parser(
        "roundtrip",
        help="verify re-extraction and IPS roundtrip without writing",
    )
    _add_pack_arguments(roundtrip)
    roundtrip.add_argument("--ips-base")
    roundtrip.add_argument("--report")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "export":
            report = export_pack(args.manifest, args.rom, args.out)
        elif args.command == "diff":
            report = diff_pack(args.manifest, args.pack, args.rom)
            _write_optional_report(report, args.report)
        elif args.command == "verify":
            report = verify_pack(args.manifest, args.pack, args.rom)
            _write_optional_report(report, args.report)
        elif args.command == "compile":
            report = compile_pack(
                args.manifest,
                args.pack,
                args.rom,
                args.ips_base,
                args.out_rom,
                args.out_ips,
                args.report,
            )
        elif args.command == "roundtrip":
            report = roundtrip_pack(
                args.manifest,
                args.pack,
                args.rom,
                args.ips_base,
            )
            _write_optional_report(report, args.report)
        else:
            parser.error(f"unknown command: {args.command}")
        _print_report(report)
        return 0
    except (OSError, PipelineError) as exc:
        print(f"Mapper 163 CHR asset pipeline: FAIL ({exc})", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
