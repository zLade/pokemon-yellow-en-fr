#!/usr/bin/env python3
"""Prove that no language-bearing Chinese glyph record remains reachable.

The 299 language-bearing graphical records belong to the canonical catalogue.
The only excluded records are the 18 explicitly reviewed type pictograms;
their exact source bytes must remain unchanged in the English candidate.
Exhaustive pointer payload validation is handled by english_pointer_manifest.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rom_builder import (  # noqa: E402
    STRUCTURED_GLYPH_RECORD_COUNT,
    TRANSLATION_BASE_SHA256,
    verified_structured_glyph_records,
)


DEFAULT_ROM = (
    ROOT / "build" / "private" / "en" / "2.0.0" /
    "Pokemon_Yellow_NJ046_EN_v2.0.0.nes"
)
DEFAULT_BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
DEFAULT_CATALOGUE = ROOT / "translation"
DEFAULT_NEUTRAL = ROOT / "data" / "validation" / "neutral_glyph_records.csv"
EXPECTED_NEUTRAL_INDICES = frozenset(range(32, 50))


class EnglishGlyphResidueError(RuntimeError):
    pass


from tools.catalogue_io import open_csv


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with open_csv(path) as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise EnglishGlyphResidueError(f"CSV without header: {path}")
        return list(reader)


def _hex(value: str, label: str) -> int:
    try:
        return int(value, 0)
    except (TypeError, ValueError) as exc:
        raise EnglishGlyphResidueError(f"invalid {label}: {value!r}") from exc


def validate_glyph_residue(
    *,
    candidate: bytes,
    base: bytes,
    catalogue_rows: Sequence[dict[str, str]],
    neutral_rows: Sequence[dict[str, str]],
    records: Sequence[tuple[int, int, int, int]] | None = None,
) -> dict[str, object]:
    if sha256(base) != TRANSLATION_BASE_SHA256:
        raise EnglishGlyphResidueError("English 2015 base hash mismatch")
    if len(candidate) != len(base):
        raise EnglishGlyphResidueError("candidate/base size mismatch")
    records = list(records or verified_structured_glyph_records(base))
    if len(records) != STRUCTURED_GLYPH_RECORD_COUNT:
        raise EnglishGlyphResidueError(
            f"graphical record count {len(records)}, expected 317"
        )

    neutral_by_index: dict[int, dict[str, str]] = {}
    for row in neutral_rows:
        try:
            index = int(row.get("record_index", ""))
        except ValueError as exc:
            raise EnglishGlyphResidueError("invalid neutral record index") from exc
        if index in neutral_by_index:
            raise EnglishGlyphResidueError(f"duplicate neutral index {index}")
        neutral_by_index[index] = row
    if set(neutral_by_index) != EXPECTED_NEUTRAL_INDICES:
        raise EnglishGlyphResidueError(
            "neutral classifications must cover exactly record indices 32-49"
        )

    catalogue_offsets: set[int] = set()
    for row in catalogue_rows:
        if row.get("record_type", "").strip().upper() != "MAIN":
            continue
        raw = row.get("source_offset_or_pointer", "").strip()
        if raw:
            catalogue_offsets.add(_hex(raw, "catalogue offset"))

    errors: list[str] = []
    neutral_hashes: dict[str, str] = {}
    language_bearing = 0
    for index, (start, end, _pair, glyph_count) in enumerate(records, start=1):
        if index in EXPECTED_NEUTRAL_INDICES:
            row = neutral_by_index[index]
            declared = (
                _hex(row.get("start_hex", ""), "neutral start"),
                _hex(row.get("end_hex_exclusive", ""), "neutral end"),
                int(row.get("glyph_count", "0")),
            )
            if declared != (start, end, glyph_count):
                errors.append(
                    f"neutral record {index}: declared {declared}, "
                    f"detected {(start, end, glyph_count)}"
                )
            if row.get("classification") != "language_neutral_type_pictogram":
                errors.append(f"neutral record {index}: invalid classification")
            if row.get("review_status") != "reviewed_language_neutral":
                errors.append(f"neutral record {index}: invalid review status")
            if not row.get("reason", "").strip():
                errors.append(f"neutral record {index}: missing reason")
            if start in catalogue_offsets:
                errors.append(f"neutral record {index}: also present in catalogue")
            if candidate[start:end] != base[start:end]:
                errors.append(f"neutral record {index}: candidate bytes changed")
            neutral_hashes[str(index)] = sha256(candidate[start:end])
        else:
            language_bearing += 1
            if start not in catalogue_offsets:
                errors.append(
                    f"language-bearing record {index} 0x{start:06X}: "
                    "missing catalogue owner"
                )
    if errors:
        raise EnglishGlyphResidueError(
            f"{len(errors)} glyph residue error(s):\n  "
            + "\n  ".join(errors[:50])
        )
    return {
        "schema": "nj046-en2-glyph-residue-validation/v1",
        "result": "PASS",
        "graphical_records": len(records),
        "language_bearing_catalogued": language_bearing,
        "neutral_pictograms_preserved": len(neutral_by_index),
        "neutral_record_hashes": neutral_hashes,
        "reachable_language_payload_gate": "english_pointer_manifest_1912",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--base-rom", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--neutral", type=Path, default=DEFAULT_NEUTRAL)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_glyph_residue(
            candidate=args.rom.read_bytes(),
            base=args.base_rom.read_bytes(),
            catalogue_rows=_read_rows(args.catalogue),
            neutral_rows=_read_rows(args.neutral),
        )
    except (EnglishGlyphResidueError, OSError, csv.Error, ValueError) as exc:
        print(f"English graphical residue: FAIL\n{exc}")
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
