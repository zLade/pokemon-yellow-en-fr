#!/usr/bin/env python3
"""Certify and explicitly qualify the Route 1 uninitialized-read diagnostic.

The diagnostic is evidence of an inherited engine quirk, not evidence that
the reads are harmless.  It binds the live Mesen trace to the exact SRAM copy
routine and proves that the same routine bytes occur in the Chinese, English
and final French ROMs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "pokemon-yellow-nes-route1-uninitialized-diagnostic/v1"
CLASSIFICATION = "inherited_source_engine_quirk_unresolved"
SAFETY_CONCLUSION = "harmlessness_not_proven"
DEFAULT_DIAGNOSTIC_DIR = Path(
    "build/runtime-proof-final-1fefecbf-uninitialized-dendy"
)
DEFAULT_ROUTE1_DIR = Path("build/runtime-proof-final-1fefecbf-route1")

ROM_SPECS = {
    "chinese_source": (
        Path("Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"),
        "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed",
    ),
    "english_translation_base": (
        Path("Pokemon Yellow English 9-23-2015.nes"),
        "d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b",
    ),
    "english_canonical": (
        Path("yellow.nes"),
        "69520103102677b33b47c15fae804dc1a742347a9ee1b02a9195e795eb6e431b",
    ),
    "french_final": (
        Path("Pokemon_Jaune_FR_repacked_title.nes"),
        "1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b",
    ),
}
FINAL_ROM_SHA256 = ROM_SPECS["french_final"][1]
MESEN_SHA256 = (
    "8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7"
)
INPUT_SHA256 = (
    "ee79b39f3556a2acc316545614d77c910dc17b34e67ca7bbc17f803c13c46d9b"
)
PROBE_PATH = Path("tools/mesen_route1_uninitialized_probe.lua")
PROBE_SHA256 = (
    "bdd096e31f6a98ae72ad103ef966a8ee9af1f936647e14dec1c2cf524aecd24c"
)
STDOUT_SHA256 = (
    "35f94351df7a81fccca39020ba0480015033017a04a24528b9281a0708bb0e40"
)
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
EXPECTED_MARKER = "POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_PASS"

# File offsets include the 16-byte iNES header.  The routine loads a source
# pointer from $077C/$077D, then copies 16 * 256 bytes through $2007.
ROUTINE_FILE_OFFSET = 0x00F899
ROUTINE_SAVE_OFFSET = 0x000889
ROUTINE_BYTES = bytes.fromhex(
    "A200BD7C078502E8BD7C078503"
    "A210A000B1028D0720C8D0F8E603CAD0F3"
)
ROUTINE_SHA256 = (
    "0c3a6bcc368da9142765fc577a45f8220a0940da195b2af8e62435892564386d"
)
READ_PC = 0x689C
READ_MAPPED_OFFSET = 0x089C
READ_FRAME = 13142
READ_SOURCE_POINTER = 0x0105
RECONSTRUCTED_INITIAL_POINTER = 0xF305
READ_SP = 0xF4

LOCAL_MODULES = (
    Path("tools/campaign/dialogue_targets.lua"),
    Path("tools/campaign/engine.lua"),
    Path("tools/campaign/input_queue.lua"),
    Path("tools/campaign/memory_guard.lua"),
    Path("tools/campaign/mesen_campaign_prototype.lua"),
    Path("tools/campaign/ram_map.lua"),
    Path("tools/mesen_fm3_route1_viridian_after_prototype.lua"),
    Path("tools/mesen_fm3_route1_viridian_trace.lua"),
)

EXPECTED_SCREENSHOT_CATALOG_SHA256 = (
    "4cd9bb63cb03c800b4b9e6cd9109d5ef137416f1c694286f9d748c2ff9a24f66"
)
EXPECTED_REGIONAL_WARNINGS = {
    "dendy": (0x0161, 0x01C6),
    "ntsc": (0x0161, 0x01C7),
    "pal": (0x0161, 0x01C6),
}

DIAGNOSTIC_RE = re.compile(
    r"\[CPU\] Uninitialized memory read: \$([0-9A-Fa-f]{4})\Z"
)
TRACE_RE = re.compile(
    r"POKEMON_UNINIT_READ_TRACE address=\$([0-9A-Fa-f]{4}) "
    r"pc=\$([0-9A-Fa-f]{4}) mapped_offset=\$([0-9A-Fa-f]{6}) "
    r"mapped_type=(\w+) a=\$([0-9A-Fa-f]{2}) "
    r"x=\$([0-9A-Fa-f]{2}) y=\$([0-9A-Fa-f]{2}) "
    r"sp=\$([0-9A-Fa-f]{2}) source_pointer=\$([0-9A-Fa-f]{4}) "
    r"absolute_frame=(\d+) converted=(.*)\Z"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_fields(text: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.lstrip("\ufeff").strip()
        if key in fields:
            errors.append(f"duplicate manifest field: {key}")
        else:
            fields[key] = value.strip()
    return fields, errors


def _parse_trace(line: str) -> dict[str, int | str] | None:
    match = TRACE_RE.fullmatch(line)
    if match is None:
        return None
    (
        address,
        pc,
        mapped_offset,
        mapped_type,
        accumulator,
        x,
        y,
        sp,
        source_pointer,
        frame,
        converted,
    ) = match.groups()
    return {
        "address": int(address, 16),
        "pc": int(pc, 16),
        "mapped_offset": int(mapped_offset, 16),
        "mapped_type": mapped_type,
        "a": int(accumulator, 16),
        "x": int(x, 16),
        "y": int(y, 16),
        "sp": int(sp, 16),
        "source_pointer": int(source_pointer, 16),
        "absolute_frame": int(frame, 10),
        "converted": converted,
    }


def validate_routine_payloads(
    rom_payloads: Mapping[str, tuple[bytes, str]],
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    records: dict[str, Any] = {}
    windows: list[bytes] = []
    for label, (payload, expected_hash) in rom_payloads.items():
        actual_hash = sha256_bytes(payload)
        window = payload[
            ROUTINE_FILE_OFFSET : ROUTINE_FILE_OFFSET + len(ROUTINE_BYTES)
        ]
        window_hash = sha256_bytes(window)
        if actual_hash != expected_hash:
            errors.append(f"{label}: unexpected full ROM SHA-256")
        if window != ROUTINE_BYTES or window_hash != ROUTINE_SHA256:
            errors.append(f"{label}: inherited routine window differs")
        windows.append(window)
        records[label] = {
            "sha256": actual_hash,
            "expected_sha256": expected_hash,
            "routine_sha256": window_hash,
            "routine_matches": window == ROUTINE_BYTES,
        }
    if len(set(windows)) != 1:
        errors.append("Chinese, English and French routine windows differ")
    return records, errors


def validate_stdout(text: str) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    lines = text.splitlines()
    warning_addresses: list[int] = []
    trace_records: list[dict[str, int | str]] = []
    malformed_debug: list[str] = []
    for line in lines:
        if "Uninitialized memory read" in line:
            match = DIAGNOSTIC_RE.fullmatch(line)
            if match is None:
                malformed_debug.append(line)
            else:
                warning_addresses.append(int(match.group(1), 16))
        if line.startswith("POKEMON_UNINIT_READ_TRACE"):
            record = _parse_trace(line)
            if record is None:
                errors.append(f"malformed trace line: {line}")
            else:
                trace_records.append(record)

    expected_warnings = list(range(0x0161, 0x01C7))
    if warning_addresses != expected_warnings:
        errors.append("Dendy warning range is not the exact $0161..$01C6 sequence")
    if malformed_debug:
        errors.append("one or more FullDebug diagnostic lines are malformed")

    late = {
        int(record["address"]): record
        for record in trace_records
        if record["pc"] == READ_PC
    }
    expected_late_y = {0x0161: 0x5C, 0x01C6: 0xC1, 0x01C7: 0xC2}
    if set(late) != set(expected_late_y):
        errors.append("instrumented SRAM-loop boundary traces are incomplete")
    for address, expected_y in expected_late_y.items():
        record = late.get(address)
        if record is None:
            continue
        expected = {
            "mapped_offset": READ_MAPPED_OFFSET,
            "mapped_type": "nesSaveRam",
            "x": 0x02,
            "y": expected_y,
            "sp": READ_SP,
            "source_pointer": READ_SOURCE_POINTER,
            "absolute_frame": READ_FRAME,
            "converted": "address=2204,memType=50",
        }
        for key, value in expected.items():
            if record.get(key) != value:
                errors.append(
                    f"trace ${address:04X}: {key}={record.get(key)!r}, "
                    f"expected {value!r}"
                )

    early_c7 = [
        record
        for record in trace_records
        if record["address"] == 0x01C7 and record["pc"] == 0x7F04
    ]
    if len(early_c7) != 1 or early_c7[0]["absolute_frame"] != 9947:
        errors.append("the earlier initialized $01C7 access is not certified")
    if len(trace_records) != 4:
        errors.append(f"expected exactly 4 instrumented traces, got {len(trace_records)}")
    if any(record["mapped_type"] != "nesSaveRam" for record in trace_records):
        errors.append("one or more traced reads are not mapped to NES save RAM")

    terminal_lines = [line for line in lines if EXPECTED_MARKER in line.split()]
    if len(terminal_lines) != 1 or lines[-1:] != terminal_lines:
        errors.append("terminal Route 1 PASS marker is missing or not final")
    else:
        required_tokens = {
            "region=Dendy",
            "writes_to_game=0",
            "bootstrap=campaign_prototype",
            "state_driven=true",
            "viridian_aligned=true",
            "parcel_route_done=false",
            "dialogues=none",
            "absolute_end=13845",
        }
        if not required_tokens.issubset(terminal_lines[0].split()):
            errors.append("terminal Route 1 scope tokens differ")

    return {
        "warning_count": len(warning_addresses),
        "warning_first": (
            f"0x{warning_addresses[0]:04X}" if warning_addresses else None
        ),
        "warning_last": (
            f"0x{warning_addresses[-1]:04X}" if warning_addresses else None
        ),
        "trace_records": trace_records,
        "terminal_output": terminal_lines[0] if len(terminal_lines) == 1 else None,
    }, errors


def _screenshot_catalog(paths: list[Path]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        payload = path.read_bytes()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"not a PNG: {path.name}")
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_bytes(payload).encode("ascii"))
        digest.update(b"\n")
        total_bytes += len(payload)
    return digest.hexdigest(), total_bytes


def validate_regional_warnings(route1_dir: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    records: dict[str, Any] = {}
    for slug, (first, last) in EXPECTED_REGIONAL_WARNINGS.items():
        path = route1_dir / slug / "mesen.stdout.txt"
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{slug}: cannot read certified stdout: {exc}")
            continue
        addresses = [
            int(match.group(1), 16)
            for line in text.splitlines()
            if (match := DIAGNOSTIC_RE.fullmatch(line)) is not None
        ]
        expected = list(range(first, last + 1))
        if addresses != expected:
            errors.append(f"{slug}: certified warning range changed")
        records[slug] = {
            "count": len(addresses),
            "first": f"0x{addresses[0]:04X}" if addresses else None,
            "last": f"0x{addresses[-1]:04X}" if addresses else None,
            "stdout_sha256": sha256_file(path),
        }
    return records, errors


def build_report(
    root: Path = ROOT,
    diagnostic_dir: Path | None = None,
    route1_dir: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    diagnostic_dir = diagnostic_dir or root / DEFAULT_DIAGNOSTIC_DIR
    route1_dir = route1_dir or root / DEFAULT_ROUTE1_DIR
    errors: list[str] = []

    rom_payloads: dict[str, tuple[bytes, str]] = {}
    for label, (relative, expected_hash) in ROM_SPECS.items():
        try:
            rom_payloads[label] = ((root / relative).read_bytes(), expected_hash)
        except OSError as exc:
            errors.append(f"{label}: cannot read ROM: {exc}")
    routine_records, routine_errors = validate_routine_payloads(rom_payloads)
    errors.extend(routine_errors)

    probe_path = root / PROBE_PATH
    try:
        probe_hash = sha256_file(probe_path)
    except OSError as exc:
        probe_hash = None
        errors.append(f"cannot hash diagnostic probe: {exc}")
    if probe_hash != PROBE_SHA256:
        errors.append("diagnostic probe SHA-256 differs")

    manifest_path = diagnostic_dir / "mesen_run_manifest.txt"
    stdout_path = diagnostic_dir / "mesen.stdout.txt"
    stderr_path = diagnostic_dir / "mesen.stderr.txt"
    try:
        manifest_text = manifest_path.read_text(encoding="utf-8-sig")
        stdout_bytes = stdout_path.read_bytes()
        stderr_bytes = stderr_path.read_bytes()
    except OSError as exc:
        manifest_text = ""
        stdout_bytes = b""
        stderr_bytes = b""
        errors.append(f"cannot read diagnostic run evidence: {exc}")
    fields, manifest_errors = _manifest_fields(manifest_text)
    errors.extend(manifest_errors)

    expected_fields = {
        "Mesen executable SHA-256": MESEN_SHA256,
        "ROM SHA-256 before": FINAL_ROM_SHA256,
        "ROM SHA-256 after": FINAL_ROM_SHA256,
        "Region": "Dendy",
        "Expected effective region": "Dendy",
        "Strict hardware profile": "True",
        "Full NES debug-stop profile": "True",
        "Lua scenario SHA-256 before": PROBE_SHA256,
        "Lua scenario SHA-256 after": PROBE_SHA256,
        "Scenario input SHA-256 before": INPUT_SHA256,
        "Scenario input SHA-256 after": INPUT_SHA256,
        "Expected marker": EXPECTED_MARKER,
        "Expected marker observed": "True",
        "Expected effective region observed": "True",
        "Mesen process exit code": "0",
        "Mesen stdout SHA-256": STDOUT_SHA256,
        "Mesen stderr SHA-256": EMPTY_SHA256,
        "Timed out": "False",
        "Screenshots": "65",
        "Result": "PASS",
        "Lua local module count": str(len(LOCAL_MODULES)),
    }
    for key, expected in expected_fields.items():
        if fields.get(key) != expected:
            errors.append(
                f"manifest {key}: {fields.get(key)!r}, expected {expected!r}"
            )

    stdout_hash = sha256_bytes(stdout_bytes)
    stderr_hash = sha256_bytes(stderr_bytes)
    if stdout_hash != STDOUT_SHA256 or stdout_hash != fields.get(
        "Mesen stdout SHA-256"
    ):
        errors.append("diagnostic stdout hash differs")
    if stderr_hash != EMPTY_SHA256 or stderr_hash != fields.get(
        "Mesen stderr SHA-256"
    ):
        errors.append("diagnostic stderr is not the certified empty stream")
    stdout_record, stdout_errors = validate_stdout(
        stdout_bytes.decode("utf-8", errors="replace")
    )
    errors.extend(stdout_errors)
    if fields.get("Mesen terminal output") != stdout_record["terminal_output"]:
        errors.append("manifest terminal output differs from actual stdout")

    module_records: list[dict[str, Any]] = []
    for index, relative in enumerate(LOCAL_MODULES, start=1):
        try:
            actual_hash = sha256_file(root / relative)
        except OSError as exc:
            actual_hash = None
            errors.append(f"cannot hash Lua module {relative}: {exc}")
        manifest_path_value = fields.get(f"Lua local module {index} path", "")
        normalized_path = manifest_path_value.replace("\\", "/")
        before = fields.get(f"Lua local module {index} SHA-256 before")
        after = fields.get(f"Lua local module {index} SHA-256 after")
        matches = (
            normalized_path.endswith(str(relative).replace("\\", "/"))
            and actual_hash is not None
            and actual_hash == before == after
        )
        if not matches:
            errors.append(f"Lua module {index} is not bound to {relative}")
        module_records.append(
            {"path": str(relative), "sha256": actual_hash, "matches": matches}
        )

    save_paths = sorted(
        diagnostic_dir.glob("isolated-*/save-data/*.sav")
    )
    save_record: dict[str, Any] = {"files": len(save_paths)}
    if len(save_paths) != 1:
        errors.append(f"expected exactly one diagnostic SRAM file, got {len(save_paths)}")
    else:
        save_payload = save_paths[0].read_bytes()
        save_window = save_payload[
            ROUTINE_SAVE_OFFSET : ROUTINE_SAVE_OFFSET + len(ROUTINE_BYTES)
        ]
        save_record.update(
            {
                "path": str(save_paths[0].relative_to(root)),
                "bytes": len(save_payload),
                "sha256": sha256_bytes(save_payload),
                "routine_offset": f"0x{ROUTINE_SAVE_OFFSET:06X}",
                "routine_sha256": sha256_bytes(save_window),
                "routine_matches": save_window == ROUTINE_BYTES,
            }
        )
        if len(save_payload) != 8192 or save_window != ROUTINE_BYTES:
            errors.append("diagnostic SRAM does not contain the inherited routine")
        if save_payload[READ_MAPPED_OFFSET - 2 : READ_MAPPED_OFFSET] != b"\xB1\x02":
            errors.append("SRAM instruction before traced PC is not LDA ($02),Y")
        if save_payload[READ_MAPPED_OFFSET : READ_MAPPED_OFFSET + 3] != b"\x8D\x07\x20":
            errors.append("SRAM traced PC is not followed by STA $2007")

    screenshot_paths = sorted(diagnostic_dir.glob("*.png"))
    try:
        screenshot_hash, screenshot_bytes = _screenshot_catalog(screenshot_paths)
    except (OSError, ValueError) as exc:
        screenshot_hash = None
        screenshot_bytes = 0
        errors.append(f"cannot validate diagnostic screenshots: {exc}")
    if (
        len(screenshot_paths) != 65
        or screenshot_hash != EXPECTED_SCREENSHOT_CATALOG_SHA256
        or screenshot_bytes <= 0
    ):
        errors.append("diagnostic screenshot catalogue differs from Route 1 proof")

    regional_records, regional_errors = validate_regional_warnings(route1_dir)
    errors.extend(regional_errors)

    report = {
        "schema": SCHEMA,
        "result": "PASS" if not errors else "FAIL",
        "classification": CLASSIFICATION,
        "safety_conclusion": SAFETY_CONCLUSION,
        "claims": {
            "routine_identical_in_chinese_english_french": not routine_errors,
            "runtime_cpu_read_confirmed": not stdout_errors,
            "offending_routine_introduced_by_french_translation": False,
            "same_trigger_observed_in_chinese_runtime": False,
            "translation_trigger_regression_excluded": False,
            "harmlessness_proven": False,
        },
        "routine": {
            "rom_file_offset": f"0x{ROUTINE_FILE_OFFSET:06X}",
            "sram_copy_offset": f"0x{ROUTINE_SAVE_OFFSET:06X}",
            "bytes": len(ROUTINE_BYTES),
            "sha256": ROUTINE_SHA256,
            "hex": ROUTINE_BYTES.hex().upper(),
            "roms": routine_records,
        },
        "runtime": {
            "diagnostic_directory": str(diagnostic_dir.relative_to(root)),
            "probe_sha256": probe_hash,
            "stdout_sha256": stdout_hash,
            "stderr_sha256": stderr_hash,
            "read_pc": f"0x{READ_PC:04X}",
            "mapped_memory": "nesSaveRam",
            "mapped_offset": f"0x{READ_MAPPED_OFFSET:06X}",
            "absolute_frame": READ_FRAME,
            "source_pointer_at_read": f"0x{READ_SOURCE_POINTER:04X}",
            "reconstructed_initial_source_pointer": (
                f"0x{RECONSTRUCTED_INITIAL_POINTER:04X}"
            ),
            "copy_pages": 16,
            "copy_bytes": 4096,
            "destination_register": "0x2007",
            "stdout": stdout_record,
            "sram": save_record,
            "lua_modules": module_records,
            "screenshots": {
                "files": len(screenshot_paths),
                "bytes": screenshot_bytes,
                "catalog_sha256": screenshot_hash,
            },
        },
        "regional_full_debug": regional_records,
        "qualification": {
            "inherited": True,
            "inherited_scope": "offending_engine_routine_bytes",
            "actual_cpu_reads": True,
            "probe_generated_reads": False,
            "unresolved": True,
            "reason": (
                "The original engine copies 4096 bytes through $2007 from a "
                "source pointer that wraps across CPU address $0000; bytes in "
                "the stack page are read before initialization. Identical "
                "routine bytes prove inheritance, but do not prove the read "
                "values are harmless on every hardware/startup state."
            ),
        },
        "errors": errors,
    }
    return report


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            temporary_name = handle.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--diagnostic-dir", type=Path)
    parser.add_argument("--route1-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    diagnostic_dir = args.diagnostic_dir
    if diagnostic_dir is not None and not diagnostic_dir.is_absolute():
        diagnostic_dir = root / diagnostic_dir
    route1_dir = args.route1_dir
    if route1_dir is not None and not route1_dir.is_absolute():
        route1_dir = root / route1_dir
    report = build_report(root, diagnostic_dir, route1_dir)
    if args.output is not None:
        output = args.output if args.output.is_absolute() else root / args.output
        write_report(report, output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
