#!/usr/bin/env python3
"""Verify Mesen battery persistence and one-byte corruption recovery evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SAVE_SIZE = 0x2000
PRIMARY_SIZE = 0x0800
BACKUP_OFFSET = 0x0C00
MUTATION_RELATIVE_OFFSET = 0x0050
SAVE_MAGIC_OFFSET = 0x1C21
SAVE_MAGIC = bytes.fromhex("AA 55 A5 5A")
MESEN_SHA256 = (
    "8ef403d6b9af32075416193914d7993ce8480b347fe1f20a0cfd9815374933e7"
)

PHASES = {
    "01-fresh-control": (
        "POKEMON_BATTERY_CONTROL_PASS",
        "mesen_battery_control_probe.lua",
    ),
    "02-create-save": (
        "POKEMON_BATTERY_CREATE_PASS",
        "mesen_battery_create_probe.lua",
    ),
    "03-reload-save": (
        "POKEMON_BATTERY_LOAD_PASS",
        "mesen_battery_load_probe.lua",
    ),
    "04-primary-corrupt": (
        "POKEMON_BATTERY_CORRUPTION_OBSERVED",
        "mesen_battery_corruption_probe.lua",
    ),
    "05-backup-corrupt": (
        "POKEMON_BATTERY_CORRUPTION_OBSERVED",
        "mesen_battery_corruption_probe.lua",
    ),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def display_path(path: Path, base: Path = ROOT) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())


def manifest_fields(text: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    errors: list[str] = []
    for line in text.lstrip("\ufeff").splitlines()[1:]:
        if ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key in fields:
            errors.append(f"duplicate manifest field: {key}")
        fields[key] = value.strip()
    return fields, errors


def read_bytes(path: Path, errors: list[str]) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read {path}: {exc}")
        return b""


def differing_offsets(first: bytes, second: bytes) -> list[int]:
    if len(first) != len(second):
        return list(range(max(len(first), len(second))))
    return [
        index
        for index, (left, right) in enumerate(zip(first, second))
        if left != right
    ]


def verify_phase(
    *,
    run_dir: Path,
    slug: str,
    expected_marker: str,
    expected_script: str,
    rom_sha256: str,
    region: str,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    phase_dir = run_dir / slug
    manifest_path = phase_dir / "mesen_run_manifest.txt"
    stdout_path = phase_dir / "mesen.stdout.txt"
    stderr_path = phase_dir / "mesen.stderr.txt"
    manifest = read_bytes(manifest_path, errors)
    stdout = read_bytes(stdout_path, errors)
    stderr = read_bytes(stderr_path, errors)
    fields, field_errors = manifest_fields(
        manifest.decode("utf-8-sig", errors="replace")
    )
    errors.extend(f"{slug}: {error}" for error in field_errors)

    expected_fields = {
        "Mesen executable SHA-256": MESEN_SHA256,
        "ROM SHA-256 before": rom_sha256,
        "ROM SHA-256 after": rom_sha256,
        "iNES mapper": "163",
        "Region": region,
        "Expected effective region": region,
        "Strict hardware profile": "True",
        "Full NES debug-stop profile": "True",
        "Expected marker": expected_marker,
        "Expected marker observed": "True",
        "Expected effective region observed": "True",
        "Mesen process exit code": "0",
        "Timed out": "False",
        "Result": "PASS",
    }
    for key, expected in expected_fields.items():
        if fields.get(key) != expected:
            errors.append(
                f"{slug}: manifest {key}={fields.get(key)!r}, "
                f"expected {expected!r}"
            )
    if fields.get("Mesen stdout SHA-256") != sha256_bytes(stdout):
        errors.append(f"{slug}: stdout SHA-256 differs")
    if fields.get("Mesen stderr SHA-256") != sha256_bytes(stderr):
        errors.append(f"{slug}: stderr SHA-256 differs")
    if stderr:
        errors.append(f"{slug}: Mesen stderr is not empty")
    stdout_text = stdout.decode("utf-8", errors="replace")
    if expected_marker not in stdout_text:
        errors.append(f"{slug}: stdout marker is absent")
    terminal = fields.get("Mesen terminal output", "")
    if terminal not in stdout_text.replace("\r", "").replace("\n", " "):
        errors.append(f"{slug}: terminal output differs from stdout")

    script_path = ROOT / "tools" / expected_script
    script_hash = sha256_path(script_path)
    if not fields.get("Lua scenario", "").replace("\\", "/").endswith(
        f"/tools/{expected_script}"
    ):
        errors.append(f"{slug}: unexpected Lua scenario path")
    if fields.get("Lua scenario SHA-256 before") != script_hash:
        errors.append(f"{slug}: Lua scenario hash differs from live source")
    if fields.get("Lua scenario SHA-256 after") != script_hash:
        errors.append(f"{slug}: Lua scenario changed during run")
    if slug.endswith("corrupt") and "memoryInjection=false" not in stdout_text:
        errors.append(f"{slug}: no-injection observation is absent")

    return {
        "result": "PASS" if not errors else "FAIL",
        "manifest": display_path(manifest_path),
        "manifest_sha256": sha256_bytes(manifest),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "marker": expected_marker,
    }, errors


def verify_run(
    run_dir: Path,
    rom_path: Path,
) -> tuple[dict[str, Any], list[str]]:
    run_dir = run_dir.resolve()
    rom_path = rom_path.resolve()
    errors: list[str] = []
    rom = read_bytes(rom_path, errors)
    rom_sha256 = sha256_bytes(rom)
    top_path = run_dir / "battery_persistence_manifest.txt"
    top_bytes = read_bytes(top_path, errors)
    top, top_field_errors = manifest_fields(
        top_bytes.decode("utf-8-sig", errors="replace")
    )
    errors.extend(top_field_errors)
    region = top.get("Region", "")

    top_expected = {
        "ROM SHA-256": rom_sha256,
        "iNES mapper": "163",
        "Battery/save-RAM bytes": str(SAVE_SIZE),
        "Strict hardware profile": "True",
        "Full NES debug-stop profile": "True",
        "Corruption relative offset": (
            f"0x{MUTATION_RELATIVE_OFFSET:04X}"
        ),
        "Corruption fixture changed bytes per case": "1",
        "Primary-corrupt initial SRAM equals fixture": "true",
        "Backup-corrupt initial SRAM equals fixture": "true",
        "Primary corruption restored from valid backup": "true",
        "Primary-corrupt CONT equals valid resumed room": "true",
        "Backup-corrupt CONT equals fresh fallback": "true",
        "Corruption scenarios use memory injection": "false",
        "Result": "PASS",
    }
    for key, expected in top_expected.items():
        if top.get(key) != expected:
            errors.append(
                f"suite manifest {key}={top.get(key)!r}, expected {expected!r}"
            )
    if region not in {"Dendy", "Ntsc", "Pal"}:
        errors.append(f"unexpected region: {region!r}")

    phases: dict[str, Any] = {}
    for slug, (marker, script) in PHASES.items():
        phase, phase_errors = verify_phase(
            run_dir=run_dir,
            slug=slug,
            expected_marker=marker,
            expected_script=script,
            rom_sha256=rom_sha256,
            region=region,
        )
        phases[slug] = phase
        errors.extend(phase_errors)

    baseline_path = run_dir / "evidence" / "created-save-before-reload.sav"
    primary_fixture_path = (
        run_dir / "evidence" / "primary-corrupt-before-launch.sav"
    )
    backup_fixture_path = (
        run_dir / "evidence" / "backup-corrupt-before-launch.sav"
    )
    baseline = read_bytes(baseline_path, errors)
    primary_fixture = read_bytes(primary_fixture_path, errors)
    backup_fixture = read_bytes(backup_fixture_path, errors)
    for label, payload in (
        ("baseline", baseline),
        ("primary fixture", primary_fixture),
        ("backup fixture", backup_fixture),
    ):
        if len(payload) != SAVE_SIZE:
            errors.append(f"{label} size={len(payload)}, expected={SAVE_SIZE}")
    if len(baseline) == SAVE_SIZE:
        if baseline[:PRIMARY_SIZE] != baseline[
            BACKUP_OFFSET : BACKUP_OFFSET + PRIMARY_SIZE
        ]:
            errors.append("baseline primary and backup blocks differ")
        if baseline[SAVE_MAGIC_OFFSET : SAVE_MAGIC_OFFSET + 4] != SAVE_MAGIC:
            errors.append("baseline save magic differs")

    expected_primary_diff = [MUTATION_RELATIVE_OFFSET]
    expected_backup_diff = [BACKUP_OFFSET + MUTATION_RELATIVE_OFFSET]
    if differing_offsets(baseline, primary_fixture) != expected_primary_diff:
        errors.append("primary corruption fixture is not the exact one-byte case")
    if differing_offsets(baseline, backup_fixture) != expected_backup_diff:
        errors.append("backup corruption fixture is not the exact one-byte case")
    if top.get("Created save SHA-256 before reload") != sha256_bytes(baseline):
        errors.append("baseline save SHA-256 differs from suite manifest")
    if top.get("Primary-corrupt fixture SHA-256") != sha256_bytes(
        primary_fixture
    ):
        errors.append("primary fixture SHA-256 differs from suite manifest")
    if top.get("Backup-corrupt fixture SHA-256") != sha256_bytes(
        backup_fixture
    ):
        errors.append("backup fixture SHA-256 differs from suite manifest")

    primary_initial = read_bytes(
        run_dir
        / "04-primary-corrupt"
        / "battery_corruption_initial_sram.bin",
        errors,
    )
    primary_final = read_bytes(
        run_dir
        / "04-primary-corrupt"
        / "battery_corruption_final_sram.bin",
        errors,
    )
    backup_initial = read_bytes(
        run_dir
        / "05-backup-corrupt"
        / "battery_corruption_initial_sram.bin",
        errors,
    )
    backup_final = read_bytes(
        run_dir
        / "05-backup-corrupt"
        / "battery_corruption_final_sram.bin",
        errors,
    )
    if primary_initial != primary_fixture:
        errors.append("primary fixture differs from first-frame SRAM")
    if backup_initial != backup_fixture:
        errors.append("backup fixture differs from first-frame SRAM")
    if len(primary_final) != SAVE_SIZE:
        errors.append("primary-corrupt final SRAM has wrong size")
    else:
        if primary_final[:PRIMARY_SIZE] != primary_final[
            BACKUP_OFFSET : BACKUP_OFFSET + PRIMARY_SIZE
        ]:
            errors.append("primary-corrupt block was not restored from backup")
        if (
            primary_final[MUTATION_RELATIVE_OFFSET]
            != baseline[MUTATION_RELATIVE_OFFSET]
        ):
            errors.append("primary-corrupt selected byte was not restored")
    if len(backup_final) != SAVE_SIZE:
        errors.append("backup-corrupt final SRAM has wrong size")

    resumed = read_bytes(
        run_dir / "03-reload-save" / "battery_load_resumed_room.png",
        errors,
    )
    created = read_bytes(
        run_dir / "02-create-save" / "battery_create_4000.png",
        errors,
    )
    primary_screen = read_bytes(
        run_dir / "04-primary-corrupt" / "battery_corruption_final.png",
        errors,
    )
    fallback = read_bytes(
        run_dir / "01-fresh-control" / "battery_control_final.png",
        errors,
    )
    backup_screen = read_bytes(
        run_dir / "05-backup-corrupt" / "battery_corruption_final.png",
        errors,
    )
    if not resumed or not fallback:
        errors.append("runtime comparison screenshots are empty")
    if created != resumed or primary_screen != resumed:
        errors.append("valid/primary-recovery resumed-room screens differ")
    if backup_screen != fallback:
        errors.append("backup-corrupt screen differs from fresh fallback")
    if fallback == resumed:
        errors.append("fresh fallback unexpectedly equals resumed room")

    report = {
        "schema": "pokemon-yellow-nes-mesen-battery-corruption/v1",
        "result": "PASS" if not errors else "FAIL",
        "run_directory": display_path(run_dir),
        "rom": display_path(rom_path),
        "rom_sha256": rom_sha256,
        "region": region,
        "mesen_sha256": MESEN_SHA256,
        "strict_hardware": True,
        "full_debug_stop": True,
        "corruption": {
            "relative_offset": f"0x{MUTATION_RELATIVE_OFFSET:04X}",
            "primary_file_offset": f"0x{MUTATION_RELATIVE_OFFSET:04X}",
            "backup_file_offset": (
                f"0x{BACKUP_OFFSET + MUTATION_RELATIVE_OFFSET:04X}"
            ),
            "changed_bytes_per_case": 1,
        },
        "observations": {
            "primary_corruption": "restored_from_backup_and_resumed",
            "backup_corruption": "rejected_to_new_game_fallback",
            "memory_injection": False,
        },
        "phases": phases,
        "artifact_hashes": {
            str(path.relative_to(run_dir)): sha256_path(path)
            for path in sorted(run_dir.rglob("*"))
            if path.is_file()
            and (
                path.name == "mesen_run_manifest.txt"
                or path.name.startswith("battery_")
                or path.parent.name == "evidence"
            )
        },
        "scope_limits": [
            "one deterministic single-byte mismatch at relative offset 0x0050",
            "newly-created early-game save only",
            "does not prove every multi-byte, truncated, or power-loss pattern",
            "Mesen 2.2.1 evidence; physical mapper-163 hardware not tested",
        ],
        "errors": errors,
    }
    return report, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--rom",
        type=Path,
        default=ROOT / "build/en/Pokemon_Yellow_EN.nes",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report, errors = verify_run(args.run_dir, args.rom)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if errors:
        for error in errors[:50]:
            print(f"ERROR: {error}")
        return 1
    print(
        "Mesen battery corruption evidence PASS "
        f"region={report['region']} run={args.run_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
