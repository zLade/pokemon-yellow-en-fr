#!/usr/bin/env python3
"""Generate and independently validate the repacked text-pointer inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (
    TRANSLATION_BASE_ROM,
    cpu_addr_for_offset,
    pair_for_offset,
    relocated_text_target,
    verified_dialogue_restoration_payloads,
    verified_field_dialogue_pointer_entries,
    verified_pointer_override_entries,
)
from tools.validate_repacked import compute_plan


SCHEMA = "pokemon-yellow-nes-pointer-manifest/v2"
DEFAULT_ROM = "Pokemon_Jaune_FR_repacked_title.nes"
DEFAULT_CSV = "traduction_base.csv"
DEFAULT_OUTPUT = "build/audits/pointer_manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: int) -> str:
    return f"0x{value:06X}"


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256(payload)


def canonical_inventory_commitment(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Commit to every pointer owner derived from the canonical inputs.

    The compact inventory deliberately excludes payload hashes and final
    targets: those are validated separately against the compiled ROM.  Its
    purpose is to make reference-set completeness explicit and independently
    reproducible from the translation CSV and the canonical base ROM.
    """

    entries = [
        {
            "kind": record.get("kind"),
            "reference": record.get("reference"),
            "source_row": record.get("source_row"),
            "source_target": record.get("source_target"),
            "provenance": record.get("provenance"),
        }
        for record in records
    ]
    return {
        "derivation": "translation_csv_and_canonical_base_rom",
        "entries": len(entries),
        "sha256": _canonical_json_sha256(entries),
    }


def _plan_args(
    *,
    csv_path: Path,
    input_rom: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        csv=str(csv_path),
        input_rom=str(input_rom),
        min_pointer_run=5,
        min_known_ratio=0.4,
        min_known_count=3,
        min_free_run=32,
        context_pointer_window=32,
        min_context_pointers=0,
        only_overflow=False,
    )


def _payload_at(rom: bytes, target: int, *, max_len: int = 4096) -> bytes:
    end = min(len(rom), target + max_len)
    terminator = rom.find(b"\x0D", target, end)
    if terminator < 0:
        raise ValueError(f"no 0x0D terminator after {_hex(target)}")
    return rom[target:terminator]


def build_manifest(
    *,
    rom_path: Path,
    csv_path: Path,
    input_rom_path: Path,
) -> dict[str, Any]:
    """Build the final pointer evidence and its canonical inventory commit."""

    (
        original,
        row_info,
        row_pointer_refs,
        allocations,
        failures,
        _free_spans,
        unsafe,
    ) = compute_plan(
        _plan_args(csv_path=csv_path, input_rom=input_rom_path)
    )
    if failures:
        raise ValueError(f"cannot manifest {len(failures)} failed allocations")
    if unsafe:
        raise ValueError(f"cannot manifest {len(unsafe)} unsafe rows")

    final_rom = rom_path.read_bytes()
    if len(final_rom) != len(original):
        raise ValueError("final ROM and canonical input have different sizes")

    # These sets are used only to label provenance.  Redirect application
    # requires the already merged global table, so applying it to either
    # subset alone would incorrectly reject legitimate cross-table owners.
    field_entries = verified_field_dialogue_pointer_entries(original)
    override_entries = verified_pointer_override_entries(original)
    field_refs = {
        ref
        for refs in field_entries.values()
        for ref in refs
    }
    override_refs = {
        ref
        for refs in override_entries.values()
        for ref in refs
    }
    restoration_payloads = verified_dialogue_restoration_payloads(original)
    restoration_references = set(restoration_payloads)

    records: list[dict[str, Any]] = []
    seen_references: set[int] = set()
    for row, max_len, encoded in row_info:
        allocated = allocations.get(row.offset)
        for source_target, refs in row_pointer_refs[row.offset]:
            if allocated is None:
                final_target = source_target
            else:
                final_target = relocated_text_target(
                    original,
                    row.offset,
                    max_len,
                    encoded,
                    source_target,
                    allocated,
                    collapse_graphical_interior=False,
                )
            payload = _payload_at(final_rom, final_target)
            for reference in refs:
                # A restored Chinese dialogue deliberately reclaims this
                # pointer slot after the ordinary translation pass.  The
                # restoration record below is therefore the authoritative
                # final owner.
                if reference in restoration_references:
                    continue
                if reference in seen_references:
                    raise ValueError(
                        f"duplicate pointer reference {_hex(reference)}"
                    )
                seen_references.add(reference)
                expected_word = cpu_addr_for_offset(final_target)
                actual_word = int.from_bytes(
                    final_rom[reference:reference + 2],
                    "little",
                )
                if actual_word != expected_word:
                    raise ValueError(
                        f"{_hex(reference)} points to 0x{actual_word:04X}, "
                        f"expected 0x{expected_word:04X}"
                    )
                provenance = (
                    "field_verified"
                    if reference in field_refs
                    else "override_verified"
                    if reference in override_refs
                    else "detected"
                )
                records.append(
                    {
                        "kind": "translation",
                        "reference": _hex(reference),
                        "source_row": _hex(row.offset),
                        "source_target": _hex(source_target),
                        "final_target": _hex(final_target),
                        "pair": pair_for_offset(reference),
                        "cpu_address": f"0x{expected_word:04X}",
                        "provenance": provenance,
                        "payload_length": len(payload),
                        "payload_sha256": _sha256(payload),
                    }
                )

    for reference, expected_payload in sorted(restoration_payloads.items()):
        if reference in seen_references:
            raise ValueError(f"duplicate restoration reference {_hex(reference)}")
        seen_references.add(reference)
        final_target = allocations[reference]
        payload = _payload_at(final_rom, final_target)
        if payload != expected_payload:
            raise ValueError(
                f"restoration payload mismatch at {_hex(reference)}"
            )
        expected_word = cpu_addr_for_offset(final_target)
        actual_word = int.from_bytes(
            final_rom[reference:reference + 2],
            "little",
        )
        if actual_word != expected_word:
            raise ValueError(
                f"restoration {_hex(reference)} has wrong pointer word"
            )
        records.append(
            {
                "kind": "restoration",
                "reference": _hex(reference),
                "source_row": None,
                "source_target": None,
                "final_target": _hex(final_target),
                "pair": pair_for_offset(reference),
                "cpu_address": f"0x{expected_word:04X}",
                "provenance": "restoration_verified",
                "payload_length": len(payload),
                "payload_sha256": _sha256(payload),
            }
        )

    records.sort(key=lambda item: int(item["reference"], 0))
    provenance_counts: dict[str, int] = {}
    for record in records:
        provenance = record["provenance"]
        provenance_counts[provenance] = (
            provenance_counts.get(provenance, 0) + 1
        )

    return {
        "schema": SCHEMA,
        "inputs": {
            # Logical names keep the manifest byte-identical when a release
            # is rebuilt in a different temporary directory.
            "canonical_rom": input_rom_path.name,
            "canonical_rom_sha256": _sha256(original),
            "translation_csv": csv_path.name,
            "translation_csv_sha256": _sha256(csv_path.read_bytes()),
            "final_rom": rom_path.name,
            "final_rom_sha256": _sha256(final_rom),
        },
        "summary": {
            "translated_rows": len(row_info),
            "allocated_payloads": len(allocations),
            "pointer_records": len(records),
            "unique_references": len(seen_references),
            "restorations": len(restoration_payloads),
            "by_provenance": dict(sorted(provenance_counts.items())),
        },
        "canonical_inventory": canonical_inventory_commitment(records),
        "records": records,
    }


def validate_manifest(
    *,
    rom_path: Path,
    manifest: dict[str, Any],
    expected_manifest: dict[str, Any] | None = None,
) -> list[str]:
    """Validate pointer evidence, optionally against canonical regeneration.

    ``expected_manifest`` must be supplied by release gates that claim
    completeness.  Self-validation alone detects malformed records and ROM
    mutations, while canonical regeneration additionally detects a removed
    record even when every manifest summary and commitment was edited to
    remain internally consistent.
    """

    errors: list[str] = []
    if manifest.get("schema") != SCHEMA:
        errors.append(f"unexpected schema: {manifest.get('schema')!r}")
        return errors
    rom = rom_path.read_bytes()
    expected_rom_hash = manifest.get("inputs", {}).get("final_rom_sha256")
    if _sha256(rom) != expected_rom_hash:
        errors.append("final ROM SHA-256 differs from pointer manifest")

    seen: set[int] = set()
    previous_reference = -1
    provenance_counts: dict[str, int] = {}
    restoration_count = 0
    records = manifest.get("records")
    if not isinstance(records, list):
        errors.append("manifest records is not an array")
        return errors
    for index, record in enumerate(records):
        label = f"record {index}"
        try:
            reference = int(record["reference"], 0)
            final_target = int(record["final_target"], 0)
            cpu_address = int(record["cpu_address"], 0)
            payload_length = int(record["payload_length"])
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{label}: malformed fields ({exc})")
            continue
        kind = record.get("kind")
        provenance = record.get("provenance")
        if kind == "translation":
            if provenance not in {
                "detected",
                "field_verified",
                "override_verified",
            }:
                errors.append(f"{label}: invalid translation provenance")
            if record.get("source_row") is None:
                errors.append(f"{label}: translation source_row is missing")
            if record.get("source_target") is None:
                errors.append(f"{label}: translation source_target is missing")
        elif kind == "restoration":
            restoration_count += 1
            if provenance != "restoration_verified":
                errors.append(f"{label}: invalid restoration provenance")
            if record.get("source_row") is not None:
                errors.append(f"{label}: restoration source_row must be null")
            if record.get("source_target") is not None:
                errors.append(
                    f"{label}: restoration source_target must be null"
                )
        else:
            errors.append(f"{label}: invalid kind {kind!r}")
        if isinstance(provenance, str):
            provenance_counts[provenance] = (
                provenance_counts.get(provenance, 0) + 1
            )
        if reference < previous_reference:
            errors.append(f"{label}: references are not sorted")
        previous_reference = reference
        if payload_length < 0:
            errors.append(f"{label}: negative payload length")
            continue
        if reference in seen:
            errors.append(f"{label}: duplicate reference {_hex(reference)}")
            continue
        seen.add(reference)
        if reference < 16 or reference + 2 > len(rom):
            errors.append(f"{label}: reference outside ROM")
            continue
        if final_target < 16 or final_target >= len(rom):
            errors.append(f"{label}: target outside ROM")
            continue
        if pair_for_offset(reference) != int(record.get("pair", -1)):
            errors.append(f"{label}: reference pair differs")
        if pair_for_offset(final_target) != pair_for_offset(reference):
            errors.append(f"{label}: target crosses PRG pair")
        expected_cpu = cpu_addr_for_offset(final_target)
        if expected_cpu != cpu_address:
            errors.append(f"{label}: target/CPU address mismatch")
        actual_cpu = int.from_bytes(rom[reference:reference + 2], "little")
        if actual_cpu != cpu_address:
            errors.append(f"{label}: ROM pointer word differs")
        payload_end = final_target + payload_length
        if payload_end >= len(rom) or rom[payload_end] != 0x0D:
            errors.append(f"{label}: payload terminator differs")
            continue
        payload = rom[final_target:payload_end]
        if _sha256(payload) != record.get("payload_sha256"):
            errors.append(f"{label}: payload SHA-256 differs")

    summary = manifest.get("summary", {})
    if summary.get("pointer_records") != len(records):
        errors.append("summary pointer_records differs")
    if summary.get("unique_references") != len(seen):
        errors.append("summary unique_references differs")
    if summary.get("restorations") != restoration_count:
        errors.append("summary restorations differs")
    if summary.get("by_provenance") != dict(sorted(provenance_counts.items())):
        errors.append("summary by_provenance differs")

    actual_commitment = manifest.get("canonical_inventory")
    recomputed_commitment = canonical_inventory_commitment(records)
    if actual_commitment != recomputed_commitment:
        errors.append("canonical inventory commitment differs from records")

    if expected_manifest is not None:
        if expected_manifest.get("schema") != SCHEMA:
            errors.append("recomputed canonical inventory has wrong schema")
            return errors
        expected_records = expected_manifest.get("records")
        if not isinstance(expected_records, list):
            errors.append("recomputed canonical inventory has no records")
            return errors

        def by_reference(
            items: list[dict[str, Any]],
        ) -> dict[str, dict[str, Any]]:
            result: dict[str, dict[str, Any]] = {}
            for item in items:
                reference = item.get("reference")
                if isinstance(reference, str):
                    result[reference] = item
            return result

        actual_by_reference = by_reference(records)
        expected_by_reference = by_reference(expected_records)
        missing = sorted(
            set(expected_by_reference) - set(actual_by_reference),
            key=lambda value: int(value, 0),
        )
        unexpected = sorted(
            set(actual_by_reference) - set(expected_by_reference),
            key=lambda value: int(value, 0),
        )
        if missing:
            errors.append(
                "canonical inventory is incomplete; missing references: "
                + ", ".join(missing[:20])
            )
        if unexpected:
            errors.append(
                "canonical inventory has unexpected references: "
                + ", ".join(unexpected[:20])
            )
        for reference in sorted(
            set(actual_by_reference) & set(expected_by_reference),
            key=lambda value: int(value, 0),
        ):
            if actual_by_reference[reference] != expected_by_reference[reference]:
                errors.append(
                    f"canonical record differs for reference {reference}"
                )

        if manifest.get("canonical_inventory") != expected_manifest.get(
            "canonical_inventory"
        ):
            errors.append("canonical inventory commitment differs from source")
        if manifest.get("inputs") != expected_manifest.get("inputs"):
            errors.append("manifest inputs differ from canonical regeneration")
    return errors


def _command_generate(args: argparse.Namespace) -> int:
    manifest = build_manifest(
        rom_path=args.rom,
        csv_path=args.csv,
        input_rom_path=args.input_rom,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Pointer manifest PASS records={manifest['summary']['pointer_records']} "
        f"output={args.output}"
    )
    return 0


def _command_validate(args: argparse.Namespace) -> int:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    try:
        expected_manifest = build_manifest(
            rom_path=args.rom,
            csv_path=args.csv,
            input_rom_path=args.input_rom,
        )
    except (OSError, ValueError) as exc:
        print(f"ERROR: cannot rebuild canonical pointer inventory: {exc}")
        return 1
    errors = validate_manifest(
        rom_path=args.rom,
        manifest=manifest,
        expected_manifest=expected_manifest,
    )
    if errors:
        for error in errors[:50]:
            print(f"ERROR: {error}")
        if len(errors) > 50:
            print(f"ERROR: ... and {len(errors) - 50} more")
        return 1
    print(
        "Pointer manifest PASS "
        f"records={len(manifest['records'])} rom={args.rom}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate")
    generate.add_argument("--rom", type=Path, default=Path(DEFAULT_ROM))
    generate.add_argument("--csv", type=Path, default=Path(DEFAULT_CSV))
    generate.add_argument(
        "--input-rom",
        type=Path,
        default=Path(TRANSLATION_BASE_ROM),
    )
    generate.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    generate.set_defaults(func=_command_generate)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--rom", type=Path, default=Path(DEFAULT_ROM))
    validate.add_argument(
        "--manifest",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
    )
    validate.add_argument("--csv", type=Path, default=Path(DEFAULT_CSV))
    validate.add_argument(
        "--input-rom",
        type=Path,
        default=Path(TRANSLATION_BASE_ROM),
    )
    validate.set_defaults(func=_command_validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
