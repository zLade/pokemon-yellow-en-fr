#!/usr/bin/env python3
"""Verify the final Route 1 Mesen manifests and consolidate their evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "pokemon-yellow-nes-mesen-route1-matrix/v1"
DEFAULT_MATRIX_DIR = Path("build/runtime-proof-final-1fefecbf-route1")
DEFAULT_OUTPUT_NAME = "route1_matrix.json"

EXPECTED_ROM_SHA256 = (
    "1fefecbfa7084d19abfa5a89c389e75f4c0a307dee3b0bf41fde49a7ebf62d5b"
)
EXPECTED_PROBE_SHA256 = (
    "a9821f9c9304ff05e5e67296a821910eced9fdc5cc894e7f9a5fd171bc52cc2f"
)
EXPECTED_INPUT_SHA256 = (
    "ee79b39f3556a2acc316545614d77c910dc17b34e67ca7bbc17f803c13c46d9b"
)
EXPECTED_MARKER = "POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_PASS"
EXPECTED_REGIONS = (
    ("dendy", "Dendy"),
    ("ntsc", "Ntsc"),
    ("pal", "Pal"),
)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MESEN_SHA256 = (
    "8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7"
)
EXPECTED_STDOUT_SHA256 = {
    "dendy": "861d2d1cbd574d48bad1f903330c0ad67748ccecff31de9422b9a3b0bc97dda3",
    "ntsc": "4b73f67f6cd0f25f201e1f27a07d86f1089e0c64dfa0761d380f96ab71814995",
    "pal": "5d81ad520da8eea528f708eb7dfdb11ef861ced7dfb647f98c20d8c051ed29e1",
}
EXPECTED_SCREENSHOT_CATALOG_SHA256 = {
    "dendy": "4cd9bb63cb03c800b4b9e6cd9109d5ef137416f1c694286f9d748c2ff9a24f66",
    "ntsc": "f43bb37cf9658cc51773589a41878e4a02e89201ce29a1f5632f6ddb8b9690ff",
    "pal": "d1b89d9ed70047148bdc7008863beb15f338698f02dac0621a8e285ee061fedc",
}
EXPECTED_UNINITIALIZED_READ_END = {
    "dendy": 0x01C6,
    "ntsc": 0x01C7,
    "pal": 0x01C6,
}
PROJECT_ARTIFACTS = {
    "rom": (Path("Pokemon_Jaune_FR_repacked_title.nes"), EXPECTED_ROM_SHA256),
    "probe": (
        Path("tools/mesen_fm3_route1_viridian_after_prototype.lua"),
        EXPECTED_PROBE_SHA256,
    ),
    "input": (
        Path("build/campaign-reference/LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin"),
        EXPECTED_INPUT_SHA256,
    ),
    "mesen": (Path("../mesen/portable-2.2.1/Mesen.exe"), EXPECTED_MESEN_SHA256),
}
LOCAL_MODULES = (
    Path("tools/campaign/dialogue_targets.lua"),
    Path("tools/campaign/engine.lua"),
    Path("tools/campaign/input_queue.lua"),
    Path("tools/campaign/memory_guard.lua"),
    Path("tools/campaign/mesen_campaign_prototype.lua"),
    Path("tools/campaign/ram_map.lua"),
    Path("tools/mesen_fm3_route1_viridian_trace.lua"),
)

HASH_FIELDS = {
    "rom": (
        "ROM SHA-256 before",
        "ROM SHA-256 after",
        EXPECTED_ROM_SHA256,
    ),
    "probe": (
        "Lua scenario SHA-256 before",
        "Lua scenario SHA-256 after",
        EXPECTED_PROBE_SHA256,
    ),
    "input": (
        "Scenario input SHA-256 before",
        "Scenario input SHA-256 after",
        EXPECTED_INPUT_SHA256,
    ),
}

REQUIRED_FIELDS = frozenset(
    {
        "Result",
        "Region",
        "Expected effective region",
        "Expected effective region observed",
        "Expected marker",
        "Expected marker observed",
        "Mesen process exit code",
        "Mesen stdout SHA-256",
        "Mesen stderr SHA-256",
        "Mesen terminal output",
        "Timed out",
        "Screenshots",
        "Strict hardware profile",
        "Full NES debug-stop profile",
        *(
            field
            for before, after, _expected in HASH_FIELDS.values()
            for field in (before, after)
        ),
    }
)

SHA256_RE = re.compile(r"[0-9a-fA-F]{64}\Z")


def _parse_required_fields(text: str) -> tuple[dict[str, str], list[str]]:
    """Return unique required key/value pairs and structural errors."""

    fields: dict[str, str] = {}
    errors: list[str] = []
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.lstrip("\ufeff").strip()
        if key not in REQUIRED_FIELDS:
            continue
        if key in fields:
            errors.append(f"duplicate required field: {key}")
            continue
        fields[key] = value.strip()

    for key in sorted(REQUIRED_FIELDS - fields.keys()):
        errors.append(f"missing required field: {key}")
    return fields, errors


def _integer(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value, 10)
    except ValueError:
        return None


def _boolean(value: str | None) -> bool | None:
    if value == "True":
        return True
    if value == "False":
        return False
    return None


def _normal_hash(value: str | None) -> str | None:
    if value is None or SHA256_RE.fullmatch(value) is None:
        return None
    return value.lower()


def verify_manifest_text(
    text: str,
    *,
    slug: str,
    expected_region: str,
) -> dict[str, Any]:
    """Validate one manifest and return its JSON-ready evidence record."""

    fields, errors = _parse_required_fields(text)
    checks: dict[str, bool] = {}

    result = fields.get("Result")
    checks["result_pass"] = result == "PASS"
    if result is not None and not checks["result_pass"]:
        errors.append(f"Result: expected 'PASS', got {result!r}")

    hashes: dict[str, dict[str, str | None]] = {}
    equality_checks: list[bool] = []
    for name, (before_key, after_key, expected) in HASH_FIELDS.items():
        before = _normal_hash(fields.get(before_key))
        after = _normal_hash(fields.get(after_key))
        hashes[name] = {"before": before, "after": after}
        hash_ok = before == expected and after == expected
        checks[f"{name}_sha256"] = hash_ok
        equality_checks.append(before is not None and before == after)
        if fields.get(before_key) is not None and before != expected:
            errors.append(
                f"{before_key}: expected {expected}, got "
                f"{fields[before_key]!r}"
            )
        if fields.get(after_key) is not None and after != expected:
            errors.append(
                f"{after_key}: expected {expected}, got "
                f"{fields[after_key]!r}"
            )
        if before is not None and after is not None and before != after:
            errors.append(f"{name} SHA-256 before/after mismatch")
    checks["before_after_equal"] = all(equality_checks)

    declared_region = fields.get("Region")
    effective_region = fields.get("Expected effective region")
    region_observed = _boolean(
        fields.get("Expected effective region observed")
    )
    terminal_output = fields.get("Mesen terminal output", "")
    terminal_tokens = terminal_output.split()
    checks["region_expected"] = (
        declared_region == expected_region
        and effective_region == expected_region
    )
    if declared_region is not None and declared_region != expected_region:
        errors.append(
            f"Region: expected {expected_region!r}, got {declared_region!r}"
        )
    if effective_region is not None and effective_region != expected_region:
        errors.append(
            "Expected effective region: expected "
            f"{expected_region!r}, got {effective_region!r}"
        )
    checks["region_observed"] = (
        region_observed is True
        and f"region={expected_region}" in terminal_tokens
    )
    if fields.get("Expected effective region observed") is not None:
        if region_observed is not True:
            errors.append("Expected effective region observed must be True")
    if terminal_output and f"region={expected_region}" not in terminal_tokens:
        errors.append(
            f"terminal output does not report region={expected_region}"
        )

    marker = fields.get("Expected marker")
    marker_observed = _boolean(fields.get("Expected marker observed"))
    checks["marker_observed"] = (
        marker == EXPECTED_MARKER
        and marker_observed is True
        and EXPECTED_MARKER in terminal_tokens
    )
    if marker is not None and marker != EXPECTED_MARKER:
        errors.append(
            f"Expected marker: expected {EXPECTED_MARKER!r}, got {marker!r}"
        )
    if fields.get("Expected marker observed") is not None:
        if marker_observed is not True:
            errors.append("Expected marker observed must be True")
    if terminal_output and EXPECTED_MARKER not in terminal_tokens:
        errors.append("terminal output does not contain the expected marker")

    exit_code = _integer(fields.get("Mesen process exit code"))
    checks["exit_code_zero"] = exit_code == 0
    if fields.get("Mesen process exit code") is not None and exit_code != 0:
        errors.append(
            "Mesen process exit code: expected integer 0, got "
            f"{fields['Mesen process exit code']!r}"
        )

    stdout_sha256 = _normal_hash(fields.get("Mesen stdout SHA-256"))
    stderr_sha256 = _normal_hash(fields.get("Mesen stderr SHA-256"))
    checks["recorded_stream_hashes"] = (
        stdout_sha256 is not None
        and stderr_sha256
        == hashlib.sha256(b"").hexdigest()
    )
    if fields.get("Mesen stdout SHA-256") is not None and stdout_sha256 is None:
        errors.append("Mesen stdout SHA-256 is malformed")
    if fields.get("Mesen stderr SHA-256") is not None and stderr_sha256 != hashlib.sha256(b"").hexdigest():
        errors.append("Mesen stderr SHA-256 is not the empty-stream hash")

    timed_out = _boolean(fields.get("Timed out"))
    checks["not_timed_out"] = timed_out is False
    if fields.get("Timed out") is not None and timed_out is not False:
        errors.append("Timed out must be False")

    terminal_map = {
        token.split("=", 1)[0]: token.split("=", 1)[1]
        for token in terminal_tokens
        if "=" in token
    }
    expected_scope = {
        "dialogues": "none",
        "writes_to_game": "0",
        "bootstrap": "campaign_prototype",
        "state_driven": "true",
        "battle_recoveries": "1",
        "viridian_aligned": "true",
        "alignment_dialogues_dismissed": "0",
        "campaign_dialogues_dismissed": "0",
        "parcel_route_done": "false",
    }
    checks["diagnostic_scope_qualified"] = all(
        terminal_map.get(key) == value
        for key, value in expected_scope.items()
    )
    if terminal_output and not checks["diagnostic_scope_qualified"]:
        errors.append(
            "terminal output does not preserve the Route1-only qualification"
        )

    screenshots = _integer(fields.get("Screenshots"))
    checks["screenshots_positive"] = (
        screenshots is not None and screenshots > 0
    )
    if fields.get("Screenshots") is not None and not checks[
        "screenshots_positive"
    ]:
        errors.append(
            f"Screenshots: expected an integer > 0, got {fields['Screenshots']!r}"
        )

    strict_hardware = _boolean(fields.get("Strict hardware profile"))
    checks["strict_hardware"] = strict_hardware is True
    if fields.get("Strict hardware profile") is not None:
        if strict_hardware is not True:
            errors.append("Strict hardware profile must be True")

    full_debug = _boolean(fields.get("Full NES debug-stop profile"))
    checks["full_debug"] = full_debug is True
    if fields.get("Full NES debug-stop profile") is not None:
        if full_debug is not True:
            errors.append("Full NES debug-stop profile must be True")

    manifest_passes = not errors and all(checks.values())
    return {
        "manifest": f"{slug}/mesen_run_manifest.txt",
        "expected_region": expected_region,
        "result": "PASS" if manifest_passes else "FAIL",
        "checks": checks,
        "evidence": {
            "declared_result": result,
            "hashes": hashes,
            "declared_region": declared_region,
            "expected_effective_region": effective_region,
            "expected_effective_region_observed": region_observed,
            "expected_marker": marker,
            "expected_marker_observed": marker_observed,
            "process_exit_code": exit_code,
            "stdout_sha256": stdout_sha256,
            "stderr_sha256": stderr_sha256,
            "timed_out": timed_out,
            "terminal_output": terminal_output,
            "qualification": {
                "scope": "route1_viridian_alignment_only",
                **{key: terminal_map.get(key) for key in expected_scope},
            },
            "screenshots": screenshots,
            "strict_hardware_profile": strict_hardware,
            "full_nes_debug_stop_profile": full_debug,
        },
        "errors": errors,
    }


def _unreadable_record(
    *, slug: str, expected_region: str, error: str
) -> dict[str, Any]:
    return {
        "manifest": f"{slug}/mesen_run_manifest.txt",
        "expected_region": expected_region,
        "result": "FAIL",
        "checks": {},
        "evidence": {},
        "errors": [error],
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _all_manifest_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.lstrip("\ufeff").strip()] = value.strip()
    return fields


def _screenshot_catalog(paths: list[Path]) -> tuple[str, int]:
    digest = hashlib.sha256()
    total_bytes = 0
    for path in paths:
        payload = path.read_bytes()
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError(f"not a PNG: {path.name}")
        file_hash = hashlib.sha256(payload).hexdigest()
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
        total_bytes += len(payload)
    return digest.hexdigest(), total_bytes


def verify_run_files(
    region_dir: Path,
    record_value: dict[str, Any],
    *,
    slug: str,
    project_root: Path,
) -> None:
    """Bind one manifest to its stdout, stderr, screenshots and Lua modules."""
    errors = record_value["errors"]
    checks = record_value["checks"]
    evidence = record_value["evidence"]

    stdout_path = region_dir / "mesen.stdout.txt"
    stderr_path = region_dir / "mesen.stderr.txt"
    try:
        stdout_bytes = stdout_path.read_bytes()
        stderr_bytes = stderr_path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read Mesen streams: {exc}")
        checks["actual_stream_hashes"] = False
        checks["debug_diagnostics_allowlisted"] = False
    else:
        stdout_hash = hashlib.sha256(stdout_bytes).hexdigest()
        stderr_hash = hashlib.sha256(stderr_bytes).hexdigest()
        checks["actual_stream_hashes"] = (
            stdout_hash == evidence.get("stdout_sha256")
            and stdout_hash == EXPECTED_STDOUT_SHA256[slug]
            and stderr_hash == evidence.get("stderr_sha256")
            and stderr_hash == hashlib.sha256(b"").hexdigest()
        )
        if not checks["actual_stream_hashes"]:
            errors.append("actual Mesen stream hashes differ from the certified run")

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        lines = stdout_text.splitlines()
        diagnostic_lines = [
            line for line in lines if "Uninitialized memory read" in line
        ]
        other_debug_lines = [
            line
            for line in lines
            if line.startswith("[") and line not in diagnostic_lines
        ]
        addresses: list[int] = []
        malformed_diagnostics: list[str] = []
        for line in diagnostic_lines:
            match = re.fullmatch(
                r"\[CPU\] Uninitialized memory read: \$([0-9A-Fa-f]{4})",
                line,
            )
            if match is None:
                malformed_diagnostics.append(line)
            else:
                addresses.append(int(match.group(1), 16))
        expected_addresses = list(
            range(0x0161, EXPECTED_UNINITIALIZED_READ_END[slug] + 1)
        )
        terminal_lines = [line for line in lines if EXPECTED_MARKER in line.split()]
        checks["debug_diagnostics_allowlisted"] = (
            not other_debug_lines
            and not malformed_diagnostics
            and addresses == expected_addresses
            and terminal_lines == [evidence.get("terminal_output")]
            and lines[-1:] == terminal_lines
        )
        if not checks["debug_diagnostics_allowlisted"]:
            errors.append("Mesen stdout contains changed or non-allowlisted diagnostics")
        evidence["streams"] = {
            "stdout_sha256": stdout_hash,
            "stderr_sha256": stderr_hash,
            "uninitialized_read_count": len(addresses),
            "uninitialized_read_first": (
                f"0x{addresses[0]:04X}" if addresses else None
            ),
            "uninitialized_read_last": (
                f"0x{addresses[-1]:04X}" if addresses else None
            ),
            "other_debug_lines": len(other_debug_lines),
        }

    screenshot_paths = sorted(region_dir.glob("*.png"))
    try:
        screenshot_hash, screenshot_bytes = _screenshot_catalog(screenshot_paths)
    except (OSError, ValueError) as exc:
        screenshot_hash = None
        screenshot_bytes = 0
        errors.append(f"cannot validate screenshots: {exc}")
    expected_screenshots = evidence.get("screenshots")
    checks["screenshot_catalog"] = (
        len(screenshot_paths) == expected_screenshots
        and screenshot_hash == EXPECTED_SCREENSHOT_CATALOG_SHA256[slug]
        and screenshot_bytes > 0
    )
    if not checks["screenshot_catalog"]:
        errors.append("screenshot catalogue differs from the certified run")
    evidence["screenshot_catalog"] = {
        "files": len(screenshot_paths),
        "bytes": screenshot_bytes,
        "sha256": screenshot_hash,
    }

    manifest_text = (region_dir / "mesen_run_manifest.txt").read_text(
        encoding="utf-8-sig"
    )
    manifest_fields = _all_manifest_fields(manifest_text)
    module_records: list[dict[str, Any]] = []
    modules_ok = True
    for index, relative in enumerate(LOCAL_MODULES, start=1):
        path = project_root / relative
        try:
            actual_hash = _sha256_file(path)
        except OSError as exc:
            actual_hash = None
            errors.append(f"cannot hash Lua module {relative}: {exc}")
        before = _normal_hash(
            manifest_fields.get(f"Lua local module {index} SHA-256 before")
        )
        after = _normal_hash(
            manifest_fields.get(f"Lua local module {index} SHA-256 after")
        )
        module_ok = actual_hash is not None and actual_hash == before == after
        modules_ok = modules_ok and module_ok
        module_records.append(
            {"path": str(relative), "sha256": actual_hash, "matches": module_ok}
        )
    checks["actual_lua_modules"] = modules_ok
    if not modules_ok:
        errors.append("one or more live Lua modules differ from the run manifest")
    evidence["lua_modules"] = module_records

    record_value["result"] = (
        "PASS" if not errors and all(checks.values()) else "FAIL"
    )


def verify_project_artifacts(project_root: Path) -> dict[str, Any]:
    records: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for name, (relative, expected) in PROJECT_ARTIFACTS.items():
        path = project_root / relative
        try:
            actual = _sha256_file(path)
        except OSError as exc:
            actual = None
            errors.append(f"{name}: cannot hash {relative}: {exc}")
        if actual != expected:
            errors.append(f"{name}: expected {expected}, got {actual}")
        records[name] = {
            "path": str(relative),
            "expected_sha256": expected,
            "actual_sha256": actual,
        }
    return {
        "result": "PASS" if not errors else "FAIL",
        "records": records,
        "errors": errors,
    }


def build_matrix_report(
    matrix_dir: Path,
    *,
    verify_files: bool = True,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Read the three fixed region manifests and return one report."""

    regions: dict[str, dict[str, Any]] = {}
    for slug, expected_region in EXPECTED_REGIONS:
        manifest_path = matrix_dir / slug / "mesen_run_manifest.txt"
        try:
            text = manifest_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as exc:
            record = _unreadable_record(
                slug=slug,
                expected_region=expected_region,
                error=f"cannot read manifest: {exc}",
            )
        else:
            record = verify_manifest_text(
                text,
                slug=slug,
                expected_region=expected_region,
            )
            if verify_files:
                verify_run_files(
                    manifest_path.parent,
                    record,
                    slug=slug,
                    project_root=project_root,
                )
        regions[slug] = record

    passed = sum(record["result"] == "PASS" for record in regions.values())
    screenshots = sum(
        record.get("evidence", {}).get("screenshots") or 0
        for record in regions.values()
        if isinstance(record.get("evidence", {}).get("screenshots"), int)
    )
    project_artifacts = (
        verify_project_artifacts(project_root)
        if verify_files
        else {"result": "SKIP", "records": {}, "errors": []}
    )
    all_regions_pass = passed == len(EXPECTED_REGIONS)
    artifacts_pass = project_artifacts["result"] in {"PASS", "SKIP"}
    return {
        "schema": SCHEMA,
        "result": "PASS" if all_regions_pass and artifacts_pass else "FAIL",
        "expectations": {
            "rom_sha256": EXPECTED_ROM_SHA256,
            "probe_sha256": EXPECTED_PROBE_SHA256,
            "input_sha256": EXPECTED_INPUT_SHA256,
            "marker": EXPECTED_MARKER,
            "regions": [region for _slug, region in EXPECTED_REGIONS],
        },
        "regions": regions,
        "project_artifacts": project_artifacts,
        "summary": {
            "regions_expected": len(EXPECTED_REGIONS),
            "regions_passed": passed,
            "screenshots": screenshots,
            "scope": "route1_viridian_alignment_only",
            "parcel_route_done": False,
            "dialogues_exercised": False,
            "project_artifacts_verified": verify_files,
        },
    }


def write_report(report: dict[str, Any], output_path: Path) -> None:
    """Atomically write a deterministic UTF-8 JSON report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as handle:
            handle.write(payload)
            temporary_name = handle.name
        os.replace(temporary_name, output_path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--matrix-dir",
        type=Path,
        default=DEFAULT_MATRIX_DIR,
        help="directory containing dendy/ntsc/pal manifests",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON path (default: <matrix-dir>/route1_matrix.json)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = args.output or args.matrix_dir / DEFAULT_OUTPUT_NAME
    report = build_matrix_report(args.matrix_dir)
    write_report(report, output_path)
    if report["result"] == "PASS":
        print(
            "Route 1 Mesen matrix PASS "
            f"regions={report['summary']['regions_passed']} "
            f"screenshots={report['summary']['screenshots']} "
            f"output={output_path}"
        )
        return 0

    for slug, record in report["regions"].items():
        for error in record["errors"]:
            print(f"ERROR [{slug}]: {error}")
    print(f"Route 1 Mesen matrix FAIL output={output_path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
