#!/usr/bin/env python3
"""Rebuild and byte-validate an NJ046 English 2.0 candidate ROM.

This is the English counterpart to the historically French
``validate_repacked.py``.  It deliberately treats the canonical builder as a
pure function: rebuild into a private temporary directory from the reviewed
catalogues, require byte-for-byte equality, then check the English-only asset
policy and all 85 restored pointer slots.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rom_builder import (  # noqa: E402
    BATTLE_TEXT_CONTROL_CAVE_OFFSET,
    BATTLE_TEXT_CONTROL_CAVE_PATCH,
    BATTLE_TEXT_CONTROL_CAVE_SOURCE,
    BATTLE_TEXT_CONTROL_HOOK_OFFSET,
    BATTLE_TEXT_CONTROL_HOOK_PATCH,
    BATTLE_TEXT_CONTROL_HOOK_SOURCE,
    BATTLE_STATUS_UNCHANGED_SKIP_OFFSET,
    BATTLE_STATUS_UNCHANGED_SKIP_PATCH,
    BATTLE_STATUS_UNCHANGED_SKIP_SOURCE,
    BATTLE_TEXT_CLEAR_WIDTH_OFFSET,
    BATTLE_TEXT_CLEAR_WIDTH_PATCH,
    BATTLE_TEXT_CLEAR_WIDTH_SOURCE,
    TRANSLATION_BASE_SHA256,
    offset_for_cpu_addr,
    pair_for_offset,
)
from tools.restoration_topology import RESTORATION_REFERENCES  # noqa: E402
from tools.validate_mapper163 import (  # noqa: E402
    MoveLabelCertification,
    MoveLabelCertificationError,
    certify_move_label_graphics,
    changed_pairs,
    parse_header,
)


DEFAULT_ROM = (
    ROOT
    / "build"
    / "private"
    / "en"
    / "2.0.0"
    / "Pokemon_Yellow_NJ046_EN_v2.0.0.nes"
)
DEFAULT_BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
DEFAULT_CATALOGUE = ROOT / "translation" / "catalog.csv"
DEFAULT_VARIANTS = ROOT / "translation" / "pointer_variants.csv"
DEFAULT_MOVE_LABELS = ROOT / "translation" / "move_labels_two_line.csv"

ASCII_FONT_OFFSET = 0x078210
ASCII_FONT_SIZE = 96 * 16
PRG_PAIR_SIZE = 0x8000
REQUIRED_CHANGED_PAIRS = frozenset({4, 6, 7})
EXPECTED_BATTLE_LINE_BREAK_PAYLOADS = {
    0x030049: b"No! There's no running\x0Afrom a Trainer battle!",
    0x030051: b"No! That would be\x0Astealing!",
    0x0300AF: b"Which move should be\x0Aforgotten?",
    0x0300B7: b"Give up on\x0Alearning ",
    0x03012D: b"Enemy is about to use\x0A",
    0x030173: b"\x0ACan't be poisoned!",
    0x030175: b"\x0ACan't be burned!",
    0x030177: b"\x0ACan't be frozen!",
}


class EnglishRepackedError(ValueError):
    """The candidate differs from its reviewed deterministic reconstruction."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def differing_ranges(left: bytes, right: bytes) -> list[tuple[int, int]]:
    if len(left) != len(right):
        return [(0, max(len(left), len(right)))]
    ranges: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(left):
        if left[cursor] == right[cursor]:
            cursor += 1
            continue
        start = cursor
        cursor += 1
        while cursor < len(left) and left[cursor] != right[cursor]:
            cursor += 1
        ranges.append((start, cursor))
    return ranges


def validate_battle_text_control(base: bytes, candidate: bytes) -> None:
    """Certify every pair-4 byte used by the explicit battle line break."""
    expected: set[int] = set()
    regions = (
        (
            BATTLE_TEXT_CONTROL_HOOK_OFFSET,
            BATTLE_TEXT_CONTROL_HOOK_SOURCE,
            BATTLE_TEXT_CONTROL_HOOK_PATCH,
        ),
        (
            BATTLE_TEXT_CONTROL_CAVE_OFFSET,
            BATTLE_TEXT_CONTROL_CAVE_SOURCE,
            BATTLE_TEXT_CONTROL_CAVE_PATCH,
        ),
        (
            BATTLE_STATUS_UNCHANGED_SKIP_OFFSET,
            BATTLE_STATUS_UNCHANGED_SKIP_SOURCE,
            BATTLE_STATUS_UNCHANGED_SKIP_PATCH,
        ),
        (
            BATTLE_TEXT_CLEAR_WIDTH_OFFSET,
            BATTLE_TEXT_CLEAR_WIDTH_SOURCE,
            BATTLE_TEXT_CLEAR_WIDTH_PATCH,
        ),
    )
    for start, source, patched in regions:
        end = start + len(source)
        if base[start:end] != source:
            raise EnglishRepackedError(
                f"battle text control base mismatch at 0x{start:06X}"
            )
        if candidate[start:end] != patched:
            raise EnglishRepackedError(
                f"battle text control candidate mismatch at 0x{start:06X}"
            )
        expected.update(
            start + index
            for index, (before, after) in enumerate(zip(source, patched))
            if before != after
        )
    pair4_start = 16 + 4 * PRG_PAIR_SIZE
    pair4_end = pair4_start + PRG_PAIR_SIZE
    actual = {
        offset
        for offset in range(pair4_start, pair4_end)
        if base[offset] != candidate[offset]
    }
    if actual != expected:
        extra = sorted(actual - expected)[:16]
        missing = sorted(expected - actual)[:16]
        raise EnglishRepackedError(
            "pair-4 battle text control diff mismatch; "
            f"extra={[f'0x{x:06X}' for x in extra]}, "
            f"missing={[f'0x{x:06X}' for x in missing]}"
        )


def validate_battle_line_break_payloads(candidate: bytes) -> None:
    """Require every reviewed 0x0A to remain live through its pointer."""
    for reference, expected in EXPECTED_BATTLE_LINE_BREAK_PAYLOADS.items():
        cpu_address = int.from_bytes(
            candidate[reference:reference + 2], "little"
        )
        target = offset_for_cpu_addr(
            pair_for_offset(reference), cpu_address, len(candidate)
        )
        end = candidate.find(b"\x0D", target, target + 128)
        if end < target:
            raise EnglishRepackedError(
                f"battle line-break payload 0x{reference:06X} is unterminated"
            )
        actual = candidate[target:end]
        if actual != expected:
            raise EnglishRepackedError(
                f"battle line-break payload 0x{reference:06X}: "
                f"{actual!r}, expected {expected!r}"
            )


def builder_arguments(
    *,
    catalogue: Path,
    variants: Path,
    move_labels: Path,
    base: Path,
    output_rom: Path,
    output_ips: Path,
    overflow: Path,
    move_label_report: Path,
) -> tuple[str, ...]:
    return (
        sys.executable,
        str(ROOT / "tools/rom_builder.py"),
        "build-repacked",
        "--profile",
        "en-US",
        "--csv",
        str(catalogue),
        "--restorations-csv",
        str(catalogue),
        "--pointer-variants-csv",
        str(variants),
        "--move-labels-csv",
        str(move_labels),
        "--move-label-report",
        str(move_label_report),
        "--input-rom",
        str(base),
        "--output-rom",
        str(output_rom),
        "--output-ips",
        str(output_ips),
        "--fixed-overflow-output",
        str(overflow),
    )


def validate_overflow_report(path: Path) -> None:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if rows:
        raise EnglishRepackedError(
            f"{len(rows)} fixed text overflow(s) remain"
        )


def validate_move_label_report(
    path: Path,
    certification: MoveLabelCertification,
) -> None:
    """Cross-check the builder's declarative report with live ROM evidence."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnglishRepackedError(
            f"invalid move-label build report: {path}: {exc}"
        ) from exc
    expected_slots = list(certification.used_even_slots)
    if payload.get("complete") is not True:
        raise EnglishRepackedError("move-label build report is incomplete")
    if payload.get("requested_count") != certification.requested_count:
        raise EnglishRepackedError(
            "move-label report requested_count differs from live certification"
        )
    if payload.get("applied_count") != certification.requested_count:
        raise EnglishRepackedError(
            "move-label report applied_count differs from reviewed catalogue"
        )
    if payload.get("used_even_slots") != expected_slots:
        raise EnglishRepackedError(
            "move-label report slots differ from live certified payloads"
        )


def validate_restored_pointers(candidate: bytes) -> None:
    errors: list[str] = []
    targets: dict[int, int] = {}
    for reference in sorted(RESTORATION_REFERENCES):
        address = int.from_bytes(
            candidate[reference:reference + 2], "little"
        )
        target = offset_for_cpu_addr(
            pair_for_offset(reference),
            address,
            len(candidate),
        )
        if target is None:
            errors.append(f"0x{reference:06X}: invalid restored target")
            continue
        if pair_for_offset(target) != pair_for_offset(reference):
            errors.append(f"0x{reference:06X}: restored target crosses PRG pair")
            continue
        end = candidate.find(
            b"\x0D", target, min(len(candidate), target + 4096)
        )
        if end <= target:
            errors.append(f"0x{reference:06X}: empty/unterminated payload")
            continue
        payload = candidate[target:end]
        if any(value < 0x20 or value > 0x7E for value in payload):
            errors.append(f"0x{reference:06X}: non-printable payload")
        targets[reference] = target
    if len(targets) != 85:
        errors.append(f"{len(targets)}/85 restoration targets valid")
    # Parlyz Heal must no longer share Awakening's original source target.
    if targets.get(0x0348F1) == 0x03499D:
        errors.append("Parlyz Heal still aliases Awakening")
    if errors:
        raise EnglishRepackedError("; ".join(errors[:30]))


def validate_candidate(
    *,
    candidate_path: Path,
    base_path: Path,
    catalogue_path: Path,
    variants_path: Path,
    move_labels_path: Path,
) -> dict[str, object]:
    candidate_path = candidate_path.resolve()
    base_path = base_path.resolve()
    catalogue_path = catalogue_path.resolve()
    variants_path = variants_path.resolve()
    move_labels_path = move_labels_path.resolve()
    for path, label in (
        (candidate_path, "candidate ROM"),
        (base_path, "English 2015 base"),
        (catalogue_path, "English catalogue"),
        (variants_path, "pointer variants"),
        (move_labels_path, "two-line move labels"),
    ):
        if not path.is_file():
            raise EnglishRepackedError(f"{label} missing: {path}")

    base = base_path.read_bytes()
    if sha256(base) != TRANSLATION_BASE_SHA256:
        raise EnglishRepackedError("English 2015 base hash mismatch")

    private_temp_parent = ROOT / "build" / "private"
    private_temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="nj046-en2-validate-",
        dir=private_temp_parent,
    ) as temporary:
        work = Path(temporary)
        rebuilt_path = work / "rebuilt.nes"
        move_label_report_path = work / "move_label_graphics.json"
        process = subprocess.run(
            builder_arguments(
                catalogue=catalogue_path,
                variants=variants_path,
                move_labels=move_labels_path,
                base=base_path,
                output_rom=rebuilt_path,
                output_ips=work / "rebuilt.ips",
                overflow=work / "fixed_overflow.csv",
                move_label_report=move_label_report_path,
            ),
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if process.returncode != 0:
            raise EnglishRepackedError(
                "deterministic rebuild failed:\n"
                + "\n".join(process.stdout.splitlines()[-30:])
            )
        validate_overflow_report(work / "fixed_overflow.csv")
        rebuilt = rebuilt_path.read_bytes()

        try:
            move_label_certification = certify_move_label_graphics(
                base=base,
                candidate=rebuilt,
                profile="en-US",
                catalogue=move_labels_path,
            )
        except MoveLabelCertificationError as exc:
            raise EnglishRepackedError(
                f"two-line move-label certification failed: {exc}"
            ) from exc
        validate_move_label_report(
            move_label_report_path,
            move_label_certification,
        )

    candidate = candidate_path.read_bytes()
    differences = differing_ranges(rebuilt, candidate)
    if differences:
        preview = ", ".join(
            f"0x{start:06X}-0x{end:06X}"
            for start, end in differences[:12]
        )
        raise EnglishRepackedError(
            f"candidate differs from exact rebuild in {len(differences)} "
            f"range(s): {preview}"
        )
    if len(candidate) != len(base):
        raise EnglishRepackedError("candidate size differs from base")
    header = parse_header(candidate)
    if header["mapper"] != 163 or header["prg_size"] != 2 * 1024 * 1024:
        raise EnglishRepackedError("mapper/PRG contract mismatch")
    if header["chr_size"] != 0 or not header["battery"]:
        raise EnglishRepackedError("CHR-RAM/battery contract mismatch")

    pairs = changed_pairs(base, candidate)
    expected_changed_pairs = set(REQUIRED_CHANGED_PAIRS)
    if move_label_certification.changed_pair8_offsets:
        expected_changed_pairs.add(8)
    if set(pairs) != expected_changed_pairs:
        raise EnglishRepackedError(
            f"changed PRG pairs {sorted(pairs)}, expected "
            f"{sorted(expected_changed_pairs)}"
        )
    validate_battle_text_control(base, candidate)
    validate_battle_line_break_payloads(candidate)
    font_end = ASCII_FONT_OFFSET + ASCII_FONT_SIZE
    if candidate[ASCII_FONT_OFFSET:font_end] != base[ASCII_FONT_OFFSET:font_end]:
        raise EnglishRepackedError("English font region was modified")
    validate_restored_pointers(candidate)

    return {
        "schema": "nj046-en2-exact-repacked-validation/v1",
        "result": "PASS",
        "candidate_sha256": sha256(candidate),
        "base_sha256": sha256(base),
        "size": len(candidate),
        "changed_pairs": {str(pair): count for pair, count in sorted(pairs.items())},
        "restorations": 85,
        "secondary_pointer_variants": 4,
        "font_policy": "english_base_preserved",
        "move_label_composites": move_label_certification.requested_count,
        "move_label_cells": len(move_label_certification.used_even_slots),
        "move_label_pair8_changed_bytes": len(
            move_label_certification.changed_pair8_offsets
        ),
        "exact_rebuild": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--base-rom", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument(
        "--move-labels-csv",
        type=Path,
        default=DEFAULT_MOVE_LABELS,
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_candidate(
            candidate_path=args.rom,
            base_path=args.base_rom,
            catalogue_path=args.catalogue,
            variants_path=args.variants,
            move_labels_path=args.move_labels_csv,
        )
    except (EnglishRepackedError, OSError, csv.Error) as exc:
        print(f"English exact repacked validation: FAIL\n{exc}")
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
