#!/usr/bin/env python3
"""Bind controller-only campaign text reads to reviewed final payloads."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from tools.prepare_critical_restoration_runtime import CASES


EXPECTED_REGIONS = ("Dendy", "Ntsc", "Pal")
CRITICAL_RIVAL_BATTLE_KEYS = (
    "MAIN:0x0301F9",  # fainted
    "MAIN:0x030262",  # sent out
    "MAIN:0x0302BF",  # used
    "MAIN:0x030AB5",  # experience gained
    "MAIN:0x030ADB",  # defeated
    "MAIN:0x035F05",  # trainer wants to fight
    "MAIN:0x035F3D",  # prize/reward fragment
    "MAIN:0x0387A0",  # rival's post-battle dialogue
)


class RuntimeTextReadError(ValueError):
    """Runtime traces do not prove the declared final payload coverage."""


def _manifest_value(lines: Sequence[str], label: str, path: Path) -> str:
    prefix = label + ":"
    values = [line[len(prefix) :].strip() for line in lines if line.startswith(prefix)]
    if len(values) != 1:
        raise RuntimeTextReadError(
            f"{path}: expected one {label!r}, found {len(values)}"
        )
    return values[0]


def read_ranges(path: Path) -> tuple[tuple[int, int], ...]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if lines[:2] != [
        "PRG offsets exclude the 16-byte iNES header.",
        "start_hex\tend_inclusive_hex\tbyte_count",
    ]:
        raise RuntimeTextReadError(f"{path}: unexpected range header")
    ranges: list[tuple[int, int]] = []
    previous_end = -1
    for line_number, line in enumerate(lines[2:], start=3):
        if not line:
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            raise RuntimeTextReadError(f"{path}:{line_number}: malformed range")
        start, end, declared_count = int(fields[0], 16), int(fields[1], 16), int(fields[2])
        if start > end or start <= previous_end:
            raise RuntimeTextReadError(
                f"{path}:{line_number}: overlapping/unsorted range"
            )
        if declared_count != end - start + 1:
            raise RuntimeTextReadError(f"{path}:{line_number}: wrong byte count")
        ranges.append((start, end))
        previous_end = end
    if not ranges:
        raise RuntimeTextReadError(f"{path}: empty PRG read trace")
    return tuple(ranges)


def covered_bytes(ranges: Sequence[tuple[int, int]], start: int, end: int) -> int:
    covered = 0
    for range_start, range_end in ranges:
        if range_end < start:
            continue
        if range_start > end:
            break
        covered += max(0, min(end, range_end) - max(start, range_start) + 1)
    return covered


def payload_ranges(
    manifest: Mapping[str, object],
) -> dict[str, tuple[tuple[int, int], ...]]:
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 1912:
        raise RuntimeTextReadError("pointer manifest must contain 1912 records")
    grouped: dict[str, set[tuple[int, int]]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise RuntimeTextReadError("pointer manifest record is not an object")
        key = str(record.get("stable_key", ""))
        target = int(str(record.get("final_target", "")), 16)
        length = int(record.get("payload_length", 0))
        if not key or target < 16 or length <= 0:
            raise RuntimeTextReadError(f"invalid pointer record for {key!r}")
        # Mesen's nesPrgRom offsets omit the 16-byte iNES header.
        grouped.setdefault(key, set()).add((target - 16, target - 16 + length - 1))
    return {key: tuple(sorted(values)) for key, values in grouped.items()}


def fully_read_keys(
    ranges: Sequence[tuple[int, int]],
    targets: Mapping[str, Sequence[tuple[int, int]]],
) -> set[str]:
    result: set[str] = set()
    for key, alternatives in targets.items():
        if any(
            covered_bytes(ranges, start, end) == end - start + 1
            for start, end in alternatives
        ):
            result.add(key)
    return result


def _key_value_lines(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.startswith("payload="):
            continue
        key, value = line.split("=", 1)
        if key in values:
            raise RuntimeTextReadError(f"{path}: duplicate field {key}")
        values[key] = value
    return lines, values


def validate_critical_restorations(
    mesen_root: Path,
    manifest: Mapping[str, object],
    rom_hash: str,
) -> dict[str, object]:
    records = manifest.get("records")
    assert isinstance(records, list)
    restoration_records = {
        str(record["stable_key"]): record
        for record in records
        if isinstance(record, dict) and record.get("kind") == "restoration"
    }
    expected_by_group: dict[str, list[str]] = {"pair6": [], "pair7": []}
    for group, stable_key, _harness in CASES:
        expected_by_group[group].append(stable_key)
        if stable_key not in restoration_records:
            raise RuntimeTextReadError(
                f"critical restoration {stable_key} absent from pointer manifest"
            )

    result_by_region: dict[str, dict[str, object]] = {
        region: {} for region in EXPECTED_REGIONS
    }
    payload_pattern = re.compile(
        r"^payload=(?P<key>\S+) harness=0x(?P<harness>[0-9A-Fa-f]{6}) "
        r"target=0x(?P<target>[0-9A-Fa-f]{6}) length=(?P<length>\d+) "
        r"unique_reads=(?P<unique>\d+)/(?P<expected>\d+) events=(?P<events>\d+)$"
    )
    for group in ("pair6", "pair7"):
        filename = f"critical_restorations_{group}_validation.txt"
        paths = sorted(mesen_root.rglob(filename))
        if len(paths) != len(EXPECTED_REGIONS):
            raise RuntimeTextReadError(
                f"found {len(paths)} {group} restoration reports, expected 3"
            )
        marker = f"POKEMON_CRITICAL_RESTORATIONS_{group.upper()}_PASS"
        for path in paths:
            scenario_manifest = path.parent / "mesen_run_manifest.txt"
            if not scenario_manifest.is_file():
                raise RuntimeTextReadError(f"missing scenario manifest for {path}")
            scenario_lines = scenario_manifest.read_text(
                encoding="utf-8-sig"
            ).splitlines()
            region = _manifest_value(scenario_lines, "Region", scenario_manifest)
            if region not in EXPECTED_REGIONS or group in result_by_region.get(region, {}):
                raise RuntimeTextReadError(
                    f"unexpected/duplicate {group} restoration region {region}"
                )
            required_scenario = {
                "ROM SHA-256 before": rom_hash,
                "ROM SHA-256 after": rom_hash,
                "Expected marker": marker,
                "Expected marker observed": "True",
                "Strict hardware profile": "True",
                "Full NES debug-stop profile": "True",
                "Result": "PASS",
            }
            for label, expected in required_scenario.items():
                actual = _manifest_value(scenario_lines, label, scenario_manifest)
                if "SHA-256" in label:
                    actual = actual.casefold()
                if actual != expected:
                    raise RuntimeTextReadError(
                        f"{scenario_manifest}: {label} is not {expected}"
                    )

            lines, values = _key_value_lines(path)
            required_report = {
                "schema": "nj046-en2-critical-restoration-runtime-result/v1",
                "group": group,
                "candidate_sha256": rom_hash,
                "mode": "assisted_transient_prg_pointer_patch",
                "writes_to_game_ram": "0",
                "payload_count": str(len(expected_by_group[group])),
                "restored": "true",
                "result": "PASS",
            }
            for label, expected in required_report.items():
                actual = values.get(label, "")
                if label == "candidate_sha256":
                    actual = actual.casefold()
                if actual != expected:
                    raise RuntimeTextReadError(
                        f"{path}: {label} is not {expected}"
                    )
            patch_writes = int(values.get("patch_writes", "-1"))
            restore_writes = int(values.get("restore_writes", "-2"))
            if patch_writes <= 0 or patch_writes != restore_writes:
                raise RuntimeTextReadError(
                    f"{path}: transient pointer writes were not symmetrically restored"
                )

            observed: dict[str, dict[str, int]] = {}
            for line in lines:
                match = payload_pattern.match(line)
                if match is None:
                    continue
                key = match.group("key")
                if key in observed:
                    raise RuntimeTextReadError(f"{path}: duplicate payload {key}")
                record = restoration_records.get(key)
                if record is None:
                    raise RuntimeTextReadError(f"{path}: unknown payload {key}")
                target = int(match.group("target"), 16)
                length = int(match.group("length"))
                unique = int(match.group("unique"))
                expected_reads = int(match.group("expected"))
                events = int(match.group("events"))
                if target != int(str(record["final_target"]), 16):
                    raise RuntimeTextReadError(f"{path}: wrong target for {key}")
                if length != int(record["payload_length"]):
                    raise RuntimeTextReadError(f"{path}: wrong length for {key}")
                if unique != length + 1 or expected_reads != length + 1 or events <= 0:
                    raise RuntimeTextReadError(f"{path}: incomplete reads for {key}")
                observed[key] = {
                    "target": target,
                    "payload_length": length,
                    "unique_reads_with_terminator": unique,
                    "read_events": events,
                }
            if set(observed) != set(expected_by_group[group]):
                raise RuntimeTextReadError(
                    f"{path}: wrong critical payload set "
                    f"{sorted(observed)}"
                )
            result_by_region[region][group] = {
                "result": "PASS",
                "mode": "assisted_transient_prg_pointer_patch",
                "pointers_restored": True,
                "payloads": {
                    key: observed[key] for key in expected_by_group[group]
                },
            }
    for region in EXPECTED_REGIONS:
        if set(result_by_region[region]) != {"pair6", "pair7"}:
            raise RuntimeTextReadError(
                f"{region}: incomplete critical restoration evidence"
            )
    return {
        "result": "PASS",
        "payload_count": len(CASES),
        "mode": "assisted_transient_prg_pointer_patch",
        "writes_to_game_ram": 0,
        "regions": result_by_region,
    }


def validate_runtime_text_reads(
    pointer_manifest_path: Path,
    mesen_root: Path,
) -> dict[str, object]:
    manifest = json.loads(pointer_manifest_path.read_text(encoding="utf-8"))
    if manifest.get("result") != "PASS":
        raise RuntimeTextReadError("pointer manifest is not PASS")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, dict) or not isinstance(inputs.get("rom"), dict):
        raise RuntimeTextReadError("pointer manifest has no ROM provenance")
    rom_hash = str(inputs["rom"].get("sha256", "")).casefold()
    if len(rom_hash) != 64:
        raise RuntimeTextReadError("pointer manifest ROM SHA-256 is invalid")
    targets = payload_ranges(manifest)
    missing_declared = sorted(set(CRITICAL_RIVAL_BATTLE_KEYS) - set(targets))
    if missing_declared:
        raise RuntimeTextReadError(
            "critical battle keys absent from pointer manifest: "
            + ", ".join(missing_declared)
        )

    battle_paths = sorted(mesen_root.rglob("campaign_english_prg_reads_battle.tsv"))
    if len(battle_paths) != len(EXPECTED_REGIONS):
        raise RuntimeTextReadError(
            f"found {len(battle_paths)} campaign battle traces, expected 3"
        )
    by_region: dict[str, dict[str, object]] = {}
    for battle_path in battle_paths:
        scenario_dir = battle_path.parent
        all_path = scenario_dir / "campaign_english_prg_reads_all.tsv"
        summary_path = scenario_dir / "campaign_english_text_trace_summary.txt"
        scenario_manifest_path = scenario_dir / "mesen_run_manifest.txt"
        for required in (all_path, summary_path, scenario_manifest_path):
            if not required.is_file():
                raise RuntimeTextReadError(f"missing campaign evidence {required}")
        scenario_lines = scenario_manifest_path.read_text(
            encoding="utf-8-sig"
        ).splitlines()
        region = _manifest_value(scenario_lines, "Region", scenario_manifest_path)
        if region not in EXPECTED_REGIONS or region in by_region:
            raise RuntimeTextReadError(f"unexpected/duplicate campaign region {region}")
        required_fields = {
            "ROM SHA-256 before": rom_hash,
            "ROM SHA-256 after": rom_hash,
            "Expected marker": "POKEMON_CAMPAIGN_ENGLISH_TRACE_PASS",
            "Expected marker observed": "True",
            "Strict hardware profile": "True",
            "Full NES debug-stop profile": "True",
            "Result": "PASS",
        }
        for label, expected in required_fields.items():
            actual = _manifest_value(scenario_lines, label, scenario_manifest_path)
            if "SHA-256" in label:
                actual = actual.casefold()
            if actual != expected:
                raise RuntimeTextReadError(
                    f"{scenario_manifest_path}: {label} is not {expected}"
                )

        summary_lines = summary_path.read_text(encoding="utf-8-sig").splitlines()
        for required in (
            "mode=controller_only_read_trace",
            "writes_to_game=0",
            "campaign_status=completed",
            "campaign_endpoint=outside_lab_stable",
            "battle_seen=true",
        ):
            if required not in summary_lines:
                raise RuntimeTextReadError(f"{summary_path}: missing {required}")

        all_ranges = read_ranges(all_path)
        battle_ranges = read_ranges(battle_path)
        all_keys = fully_read_keys(all_ranges, targets)
        battle_keys = fully_read_keys(battle_ranges, targets)
        missing_critical = sorted(set(CRITICAL_RIVAL_BATTLE_KEYS) - battle_keys)
        if missing_critical:
            raise RuntimeTextReadError(
                f"{region}: critical battle payloads not fully read: "
                + ", ".join(missing_critical)
            )
        by_region[region] = {
            "all_fully_read_payloads": len(all_keys),
            "battle_fully_read_payloads": len(battle_keys),
            "critical_battle_payloads": list(CRITICAL_RIVAL_BATTLE_KEYS),
            "all_fully_read_keys": sorted(all_keys),
            "battle_fully_read_keys": sorted(battle_keys),
        }

    if set(by_region) != set(EXPECTED_REGIONS):
        raise RuntimeTextReadError("campaign traces do not cover all regions")
    critical_restorations = validate_critical_restorations(
        mesen_root,
        manifest,
        rom_hash,
    )
    return {
        "schema": "nj046-en2-runtime-text-read-gate/v1",
        "result": "PASS",
        "candidate_sha256": rom_hash,
        "mode": "controller_only_prg_read_trace",
        "writes_to_game": 0,
        "critical_rival_battle_keys": list(CRITICAL_RIVAL_BATTLE_KEYS),
        "regions": {region: by_region[region] for region in EXPECTED_REGIONS},
        "critical_restorations": critical_restorations,
        "scope_limit": (
            "The forced rival battle and early campaign are traced; this is "
            "not exhaustive dynamic coverage of all 1,929 payloads."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-manifest", type=Path, required=True)
    parser.add_argument("--mesen-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_runtime_text_reads(
            args.pointer_manifest.resolve(), args.mesen_root.resolve()
        )
    except (RuntimeTextReadError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"English runtime text reads: FAIL\n{exc}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("English runtime text reads: PASS (Dendy/NTSC/PAL)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
