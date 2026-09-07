#!/usr/bin/env python3
"""Build/validate the 1,912-reference English 2.0 pointer manifest."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.rom_builder import (  # noqa: E402
    reviewed_text_prefix_len,
    offset_for_cpu_addr,
    pair_for_offset,
)
from tools.locales.profiles import ENGLISH_TEXT_PROFILE  # noqa: E402
from tools.move_label_graphics import (  # noqa: E402
    MOVE_NAME_POINTER_TABLE_OFFSET,
    load_move_label_csv,
)


DEFAULT_ROM = (
    ROOT
    / "build"
    / "private"
    / "en"
    / "2.0.0"
    / "Pokemon_Yellow_NJ046_EN_v2.0.0.nes"
)
DEFAULT_CATALOGUE = ROOT / "translation"
DEFAULT_VARIANTS = ROOT / "translation" / "pointer_variants.csv"
DEFAULT_INVENTORY = ROOT / "data" / "validation" / "structural_pointer_inventory.json"
DEFAULT_MOVE_LABELS = ROOT / "translation" / "move_labels_two_line.csv"
EXPECTED_REFERENCES = 1912
EXPECTED_SECONDARY_VARIANTS = 4
TM_ITEM_POINTER_REFERENCES = frozenset(range(0x0319BF, 0x031A0F, 2))
REVIEWED_SOURCE_INTERIOR_REFERENCES = frozenset(
    {0x0301B3, 0x0301B5}
)
COLLAPSED_ASCII_PADDING_INTERIOR_REFERENCES = frozenset(
    {
        0x03002F,
        0x03003F,
        0x030047,
        # Dynamic battle suffixes own their joining space.  The repacker
        # deliberately retargets both poison/flinch variants to the complete
        # payload rather than the historical interior character.
        0x03006B,
        0x03006F,
        0x030075,
        0x030077,
        0x030079,
        0x03007B,
        0x03007D,
        0x030083,
        0x030085,
        0x030087,
        0x0300B5,
        0x0300BB,
        0x0300BF,
        0x0300C1,
        0x0300C3,
        0x0300C5,
        0x0300C7,
        0x0300C9,
        0x0300CB,
        0x0300CD,
        0x0300CF,
        0x0300D1,
        0x0300D3,
        0x0300D5,
        0x0300D7,
        0x0300D9,
        0x0300DB,
        0x0300DF,
        0x0300E1,
        0x030131,
        0x030135,
        0x030149,
        0x030161,
    }
)
PRESERVED_LEADING_CONTROL_REFERENCES = frozenset(
    {0x030173, 0x030175, 0x030177}
)
REVIEWED_FIXED_IN_PLACE_WITH_ZERO_PADDING = frozenset({0x03CFBC})


class EnglishPointerManifestError(ValueError):
    """The candidate's pointer graph differs from the reviewed inventory."""


from tools.catalogue_io import open_csv, catalogue_bytes


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_csv_by_key(path: Path, key_field: str) -> dict[str, dict[str, str]]:
    with open_csv(path) as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        if not key or key in result:
            raise EnglishPointerManifestError(
                f"{path}: empty/duplicate {key_field} {key!r}"
            )
        result[key] = row
    return result


def expected_payloads(
    catalogue_path: Path,
    variants_path: Path,
) -> tuple[dict[str, bytes], dict[int, str]]:
    catalogue = read_csv_by_key(catalogue_path, "stable_key")
    variants = read_csv_by_key(variants_path, "variant_key")
    payloads: dict[str, bytes] = {}
    for key, row in catalogue.items():
        if "pending" in row.get("review_status", "").casefold():
            raise EnglishPointerManifestError(f"{key}: pending catalogue row")
        payloads[key] = ENGLISH_TEXT_PROFILE.format_text(
            row.get("english_v2", ""),
            row.get("layout", ""),
        )

    grouped: dict[str, list[dict[str, str]]] = {}
    for key, row in variants.items():
        if "pending" in row.get("review_status", "").casefold():
            raise EnglishPointerManifestError(f"{key}: pending pointer variant")
        payloads[key] = ENGLISH_TEXT_PROFILE.format_text(
            row.get("english_v2", ""), ""
        )
        grouped.setdefault(row["stable_key"], []).append(row)

    variant_key_by_secondary_ref: dict[int, str] = {}
    for owner, rows in grouped.items():
        if payloads.get(owner) != payloads[rows[0]["variant_key"]]:
            raise EnglishPointerManifestError(
                f"{owner}: primary variant differs from main payload"
            )
        for row in rows[1:]:
            reference = int(row["pointer_reference_hex"], 16)
            if reference in variant_key_by_secondary_ref:
                raise EnglishPointerManifestError(
                    f"duplicate secondary variant ref 0x{reference:06X}"
                )
            variant_key_by_secondary_ref[reference] = row["variant_key"]
    if len(variant_key_by_secondary_ref) != EXPECTED_SECONDARY_VARIANTS:
        raise EnglishPointerManifestError(
            f"{len(variant_key_by_secondary_ref)} secondary variants instead of "
            f"{EXPECTED_SECONDARY_VARIANTS}"
        )
    return payloads, variant_key_by_secondary_ref


def _source_target_delta(structural: Mapping[str, object]) -> int:
    """Return the reviewed interior-target delta of one source record."""

    source_row = int(str(structural["source_row"]), 16)
    source_target = int(str(structural["source_target"]), 16)
    delta = source_target - source_row
    if delta < 0:
        raise EnglishPointerManifestError(
            f"{structural['reference']}: source target precedes its row"
        )
    return delta


def expected_payload_for_reference(
    *,
    stable_key: str,
    structural: Mapping[str, object],
    payloads: Mapping[str, bytes],
) -> bytes:
    """Match the bytes a live pointer is meant to see after relocation.

    The repacker preserves genuine interior ASCII targets.  It also collapses
    source padding/control prefixes to the formatted payload's reviewed text
    start.  Comparing every pointer against the complete owning row therefore
    produced false failures for the 98 reviewed submessage/prefix references.
    """

    expected = payloads.get(stable_key)
    if expected is None:
        raise EnglishPointerManifestError(
            f"{structural['reference']}: unknown owner {stable_key}"
        )
    if str(structural.get("kind")) == "restoration" or "@0x" in stable_key:
        return expected
    reference = int(str(structural["reference"]), 16)
    if reference in COLLAPSED_ASCII_PADDING_INTERIOR_REFERENCES:
        return expected
    if reference in PRESERVED_LEADING_CONTROL_REFERENCES:
        return expected
    delta = _source_target_delta(structural)
    if delta == 0:
        return expected
    prefix = reviewed_text_prefix_len(expected)
    if delta > 0 and prefix > 0:
        return expected[prefix:]
    # Interior targets in the 2015 source often select a historical suffix.
    # The repacker intentionally retargets them to the start of the reviewed
    # translated row when no translated prefix exists; source byte deltas are
    # not stable across languages.
    return expected


def final_payload_for_reference(
    *,
    rom: bytes,
    reference: int,
    target: int,
    expected: bytes,
) -> bytes:
    """Read the exact final bytes owned by one reviewed pointer reference."""

    if reference in REVIEWED_FIXED_IN_PLACE_WITH_ZERO_PADDING:
        actual = rom[target : target + len(expected)]
        if len(actual) != len(expected):
            raise EnglishPointerManifestError(
                f"0x{reference:06X}: fixed payload extends past ROM"
            )
        return actual
    end = rom.find(b"\x0D", target, min(len(rom), target + 4096))
    if end < target:
        raise EnglishPointerManifestError(
            f"0x{reference:06X}: unterminated target"
        )
    return rom[target:end]


def validate_graphical_move_payload(reference: int, payload: bytes) -> None:
    """Require a complete sequence of mapper-163 two-byte graphic codes."""

    if not payload or len(payload) % 2:
        raise EnglishPointerManifestError(
            f"0x{reference:06X}: malformed two-line move payload length"
        )
    for cursor in range(0, len(payload), 2):
        high, low = payload[cursor:cursor + 2]
        if not 0xB0 <= high <= 0xBF or not 0xA1 <= low <= 0xFE:
            raise EnglishPointerManifestError(
                f"0x{reference:06X}: invalid graphical move code "
                f"0x{high:02X}{low:02X}"
            )


def build_manifest(
    *,
    rom_path: Path,
    catalogue_path: Path,
    variants_path: Path,
    inventory_path: Path,
    move_labels_path: Path,
) -> dict[str, object]:
    rom = rom_path.read_bytes()
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    structural_records = inventory.get("records")
    if not isinstance(structural_records, list) or len(structural_records) != 1912:
        raise EnglishPointerManifestError("structural inventory is not 1912 rows")
    payloads, secondary_variants = expected_payloads(
        catalogue_path, variants_path
    )
    graphical_moves = {
        MOVE_NAME_POINTER_TABLE_OFFSET + spec.move_index * 2: spec
        for spec in load_move_label_csv(move_labels_path)
    }

    records: list[dict[str, object]] = []
    errors: list[str] = []
    for structural in structural_records:
        reference = int(str(structural["reference"]), 16)
        pair = pair_for_offset(reference)
        address = int.from_bytes(rom[reference:reference + 2], "little")
        target = offset_for_cpu_addr(pair, address, len(rom))
        if target is None:
            errors.append(f"0x{reference:06X}: invalid final target")
            continue
        if structural["kind"] == "restoration":
            stable_key = f"RESTORED:0x{reference:06X}"
        else:
            stable_key = secondary_variants.get(reference) or (
                f"MAIN:{structural['source_row']}"
            )
        try:
            expected = expected_payload_for_reference(
                stable_key=stable_key,
                structural=structural,
                payloads=payloads,
            )
        except EnglishPointerManifestError as exc:
            errors.append(str(exc))
            expected = None
        if (
            expected is not None
            and reference in REVIEWED_SOURCE_INTERIOR_REFERENCES
        ):
            source_delta = _source_target_delta(structural)
            expected = expected[min(source_delta, len(expected)) :]
        if expected is not None and reference in TM_ITEM_POINTER_REFERENCES:
            # The TM item-name table stores display padding in the source CSV,
            # but the repacker terminates the live six-cell label after the
            # visible number.  Dynamic battle prefixes keep their join space.
            expected = expected.rstrip(b" ")
        try:
            payload = final_payload_for_reference(
                rom=rom,
                reference=reference,
                target=target,
                expected=expected or b"",
            )
        except EnglishPointerManifestError as exc:
            errors.append(str(exc))
            continue
        move_spec = graphical_moves.get(reference)
        if move_spec is not None:
            try:
                validate_graphical_move_payload(reference, payload)
            except EnglishPointerManifestError as exc:
                errors.append(str(exc))
        elif expected is not None and payload != expected:
            errors.append(
                f"0x{reference:06X}: payload for {stable_key} differs "
                f"({sha256(payload)} != {sha256(expected)})"
            )
        records.append(
            {
                "kind": structural["kind"],
                "reference": f"0x{reference:06X}",
                "stable_key": stable_key,
                "source_row": structural["source_row"],
                "source_target": structural["source_target"],
                "final_target": f"0x{target:06X}",
                "pair": pair,
                "cpu_address": f"0x{address:04X}",
                "provenance": structural["provenance"],
                "payload_length": len(payload),
                "payload_sha256": sha256(payload),
                "payload_kind": (
                    "two_line_move_graphic" if move_spec is not None else "text"
                ),
                "reviewed_text": (
                    move_spec.full_name if move_spec is not None else None
                ),
                "move_lines": (
                    [move_spec.line_1, move_spec.line_2]
                    if move_spec is not None
                    else None
                ),
            }
        )

    references = [row["reference"] for row in records]
    if len(records) != EXPECTED_REFERENCES or len(set(references)) != EXPECTED_REFERENCES:
        errors.append(
            f"manifest cardinality {len(records)}/{len(set(references))}, expected 1912"
        )
    if errors:
        raise EnglishPointerManifestError(
            f"{len(errors)} pointer manifest error(s):\n  "
            + "\n  ".join(errors[:50])
        )

    by_provenance = Counter(str(row["provenance"]) for row in records)
    records_commitment = sha256(
        json.dumps(
            records,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return {
        "schema": "nj046-en2-pointer-manifest/v1",
        "result": "PASS",
        "inputs": {
            "rom": {"name": rom_path.name, "sha256": sha256(rom)},
            "catalogue": {
                "name": catalogue_path.name,
                "sha256": sha256(catalogue_bytes(catalogue_path)),
            },
            "variants": {
                "name": variants_path.name,
                "sha256": sha256(variants_path.read_bytes()),
            },
            "structural_inventory": {
                "name": inventory_path.name,
                "sha256": sha256(inventory_path.read_bytes()),
            },
            "move_labels": {
                "name": move_labels_path.name,
                "sha256": sha256(move_labels_path.read_bytes()),
            },
        },
        "summary": {
            "pointer_records": len(records),
            "unique_references": len(set(references)),
            "restorations": sum(row["kind"] == "restoration" for row in records),
            "secondary_pointer_variants": len(secondary_variants),
            "graphical_move_records": sum(
                row["payload_kind"] == "two_line_move_graphic"
                for row in records
            ),
            "by_provenance": dict(sorted(by_provenance.items())),
            "records_sha256": records_commitment,
        },
        "structural_inventory": inventory.get("summary"),
        "records": records,
    }


def render(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "validate"))
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--variants", type=Path, default=DEFAULT_VARIANTS)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--move-labels", type=Path, default=DEFAULT_MOVE_LABELS)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        document = build_manifest(
            rom_path=args.rom.resolve(),
            catalogue_path=args.catalogue.resolve(),
            variants_path=args.variants.resolve(),
            inventory_path=args.inventory.resolve(),
            move_labels_path=args.move_labels.resolve(),
        )
    except (EnglishPointerManifestError, OSError, csv.Error, json.JSONDecodeError) as exc:
        print(f"English pointer manifest: FAIL\n{exc}")
        return 1
    expected = render(document)
    output = args.output.resolve()
    if args.command == "validate":
        if not output.is_file() or output.read_text(encoding="utf-8") != expected:
            print(f"English pointer manifest: FAIL (stale {output})")
            return 1
        print("English pointer manifest: PASS (1912/1912)")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8")
    print(f"English pointer manifest: PASS -> {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
