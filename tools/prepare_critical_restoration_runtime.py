#!/usr/bin/env python3
"""Prepare the final-target map for assisted critical restoration rendering."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, Mapping, Sequence


CASES = (
    ("pair6", "RESTORED:0x033195", 0x03018D),
    ("pair6", "RESTORED:0x0331D1", 0x03018F),
    ("pair6", "RESTORED:0x0348F1", 0x030191),
)
HEADER = (
    "group",
    "stable_key",
    "harness_reference_hex",
    "target_file_offset_hex",
    "target_prg_offset_hex",
    "target_cpu_address_hex",
    "payload_length",
    "payload_sha256",
    "payload_hex",
)


class CriticalRestorationRuntimeError(ValueError):
    """The final pointer graph cannot support the assisted runtime probes."""


def pair_for_file_offset(offset: int) -> int:
    if offset < 16:
        raise CriticalRestorationRuntimeError("offset precedes iNES PRG data")
    return (offset - 16) // 0x8000


def _record_by_key(manifest: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 1912:
        raise CriticalRestorationRuntimeError(
            "pointer manifest must contain exactly 1912 records"
        )
    result: dict[str, Mapping[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise CriticalRestorationRuntimeError("pointer record is not an object")
        key = str(record.get("stable_key", ""))
        if key in result:
            # Multiple ordinary references may share a stable key, but every
            # restoration has exactly one structural source reference.
            if key.startswith("RESTORED:"):
                raise CriticalRestorationRuntimeError(
                    f"duplicate restoration record {key}"
                )
            continue
        result[key] = record
    return result


def build_rows(manifest: Mapping[str, object], rom: bytes) -> list[dict[str, str]]:
    inputs = manifest.get("inputs")
    if manifest.get("result") != "PASS" or not isinstance(inputs, dict):
        raise CriticalRestorationRuntimeError("pointer manifest is not PASS")
    rom_input = inputs.get("rom")
    if not isinstance(rom_input, dict):
        raise CriticalRestorationRuntimeError("pointer manifest has no ROM input")
    records = _record_by_key(manifest)
    rows: list[dict[str, str]] = []
    for group, stable_key, harness_reference in CASES:
        record = records.get(stable_key)
        if record is None:
            raise CriticalRestorationRuntimeError(f"missing {stable_key}")
        if record.get("kind") != "restoration":
            raise CriticalRestorationRuntimeError(f"{stable_key} is not a restoration")
        target = int(str(record.get("final_target", "")), 16)
        length = int(record.get("payload_length", 0))
        if length <= 0 or target + length >= len(rom):
            raise CriticalRestorationRuntimeError(f"invalid target for {stable_key}")
        if pair_for_file_offset(target) != pair_for_file_offset(harness_reference):
            raise CriticalRestorationRuntimeError(
                f"{stable_key} target cannot be reached by harness pointer "
                f"0x{harness_reference:06X}"
            )
        payload = rom[target : target + length]
        if rom[target + length] != 0x0D:
            raise CriticalRestorationRuntimeError(
                f"{stable_key} final payload is not terminated"
            )
        expected_sha = str(record.get("payload_sha256", "")).casefold()
        import hashlib

        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_sha != expected_sha:
            raise CriticalRestorationRuntimeError(
                f"{stable_key} payload hash differs from pointer manifest"
            )
        pair = pair_for_file_offset(target)
        pair_start = 16 + pair * 0x8000
        cpu_address = 0x8000 + target - pair_start
        rows.append(
            {
                "group": group,
                "stable_key": stable_key,
                "harness_reference_hex": f"0x{harness_reference:06X}",
                "target_file_offset_hex": f"0x{target:06X}",
                "target_prg_offset_hex": f"0x{target - 16:06X}",
                "target_cpu_address_hex": f"0x{cpu_address:04X}",
                "payload_length": str(length),
                "payload_sha256": actual_sha,
                "payload_hex": payload.hex(),
            }
        )
    return rows


def render(manifest: Mapping[str, object], rows: Sequence[Mapping[str, str]]) -> str:
    rom_input = manifest["inputs"]["rom"]  # type: ignore[index]
    lines = [
        "schema\tnj046-en2-critical-restoration-runtime/v1",
        f"candidate_sha256\t{rom_input['sha256']}",  # type: ignore[index]
        "\t".join(HEADER),
    ]
    lines.extend("\t".join(row[field] for field in HEADER) for row in rows)
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--pointer-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = json.loads(args.pointer_manifest.read_text(encoding="utf-8"))
        rows = build_rows(manifest, args.rom.read_bytes())
        output = render(manifest, rows)
    except (CriticalRestorationRuntimeError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Critical restoration runtime map: FAIL\n{exc}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output, encoding="utf-8", newline="\n")
    print(f"Critical restoration runtime map: PASS ({len(rows)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
