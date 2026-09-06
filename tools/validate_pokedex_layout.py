#!/usr/bin/env python3
"""Validate all 151 accessible Pokédex descriptions in four 13-column lines."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    PATCH_SCRIPT,
    parse_patch_entries,
    sha256,
)
from tools.dialogue_inventory import (  # noqa: E402
    INVENTORY_PATH,
    INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT,
    INVENTORY_POKEDEX_RECORD_COUNT,
    INVENTORY_SHA256,
    load_pokedex_inventory,
)
from tools.dialogue_layout import (  # noqa: E402
    POKEDEX_LAYOUT,
    POKEDEX_LINE_WIDTH,
    POKEDEX_MAX_LINES,
    format_game_text,
    semantic_units,
    wrap_pokedex_lines,
)
from tools.french_font import encode_game_text  # noqa: E402
from tools.pokedex_description_table import (  # noqa: E402
    DEFAULT_POINTER_ROM,
    POKEDEX_ACCESSIBLE_ANCHORS,
    POKEDEX_ACCESSIBLE_COUNT,
    POKEDEX_ACCESSIBLE_OFFSET_FINGERPRINT,
    POKEDEX_EXTENDED_POINTER_COUNT,
    POKEDEX_EXTENDED_OFFSET_FINGERPRINT,
    load_pokedex_description_table,
)


def validate(
    script_path: str | Path = PATCH_SCRIPT,
    rom_path: str | Path = DEFAULT_POINTER_ROM,
) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    entries = parse_patch_entries(
        script_path,
        apply_dialogue_inventory=False,
    )
    by_offset = {entry.offset: entry for entry in entries}
    if len(by_offset) != len(entries):
        errors.append("offset(s) en double dans le script")

    accessible_records, extended_records = load_pokedex_description_table(
        rom_path
    )
    accessible_offsets = tuple(
        record.description_offset for record in accessible_records
    )
    extended_offsets = tuple(
        record.description_offset for record in extended_records
    )
    accessible_set = set(accessible_offsets)
    extended_set = set(extended_offsets)
    allowed_layout_offsets = accessible_set | extended_set

    inventory = load_pokedex_inventory()
    layout_entries = {
        entry.offset: entry
        for entry in entries
        if entry.layout == POKEDEX_LAYOUT
    }

    for record in accessible_records:
        offset = record.description_offset
        entry = by_offset.get(offset)
        if entry is None:
            errors.append(
                f"Pokédex #{record.table_index}: description absente "
                f"du script à 0x{offset:06X}"
            )
        elif entry.layout != POKEDEX_LAYOUT:
            errors.append(
                f"Pokédex #{record.table_index} 0x{offset:06X}: "
                "layout Pokédex 13×4 non appliqué"
            )
    for offset in sorted(set(layout_entries) - allowed_layout_offsets):
        errors.append(
            f"layout Pokédex hors table accessible/étendue: 0x{offset:06X}"
        )

    artificial_hyphenations_checked = 0
    artificial_hyphenations_remaining = 0
    for offset, record in inventory.items():
        entry = by_offset.get(offset)
        if entry is None:
            continue
        for repair in record["artificial_hyphenations"]:
            source_form = str(repair["source_form"])
            artificial_hyphenations_checked += 1
            if source_form in entry.text:
                artificial_hyphenations_remaining += 1
                errors.append(
                    f"0x{offset:06X}: césure artificielle restante "
                    f"{source_form!r}"
                )
    if artificial_hyphenations_checked != (
        INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT
    ):
        errors.append(
            f"{artificial_hyphenations_checked} césures contrôlées, "
            "attendu "
            f"{INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT}"
        )

    accessible_layout_offsets = accessible_set & set(layout_entries)
    extended_layout_offsets = extended_set & set(layout_entries)
    validated_offsets = (
        accessible_layout_offsets | extended_layout_offsets
    )
    physical_lines = 0
    accessible_physical_lines = 0
    extended_physical_lines = 0
    full_four_line_records = 0
    semantic_unit_count = 0
    encoded_bytes = 0
    visible_bytes = 0
    word_split_boundaries = 0
    longest: tuple[int, int] = (0, 0)

    for offset in sorted(validated_offsets):
        entry = layout_entries[offset]
        units = semantic_units(entry.text)
        if entry.text != " ".join(units):
            errors.append(
                f"0x{offset:06X}: espacement sémantique non canonique"
            )
        try:
            lines = wrap_pokedex_lines(entry.text)
            encoded = format_game_text(entry.text, entry.layout)
        except ValueError as exc:
            errors.append(f"0x{offset:06X}: {exc}")
            continue

        if not lines:
            errors.append(f"0x{offset:06X}: description vide")
            continue
        if encoded != b"".join(lines):
            errors.append(
                f"0x{offset:06X}: divergence wrapper/lignes"
            )
        semantic_text = b" ".join(
            encode_game_text(unit) for unit in units
        )
        visible_reflow = b" ".join(
            line.rstrip(b" ") for line in lines
        )
        if visible_reflow != semantic_text:
            word_split_boundaries += 1
            errors.append(
                f"0x{offset:06X}: césure ou perte de mot au reflow"
            )
        if len(lines) > POKEDEX_MAX_LINES:
            errors.append(
                f"0x{offset:06X}: {len(lines)} lignes, "
                f"maximum {POKEDEX_MAX_LINES}"
            )
        for line_index, line in enumerate(lines):
            is_last = line_index == len(lines) - 1
            if len(line) > POKEDEX_LINE_WIDTH:
                errors.append(
                    f"0x{offset:06X}: ligne {line_index + 1} "
                    f"trop longue ({len(line)} > {POKEDEX_LINE_WIDTH})"
                )
            if not is_last and len(line) != POKEDEX_LINE_WIDTH:
                errors.append(
                    f"0x{offset:06X}: ligne complète "
                    f"{line_index + 1} non paddée"
                )

        physical_lines += len(lines)
        if offset in accessible_set:
            accessible_physical_lines += len(lines)
        else:
            extended_physical_lines += len(lines)
        full_four_line_records += len(lines) == POKEDEX_MAX_LINES
        semantic_unit_count += len(units)
        encoded_bytes += len(encoded)
        visible_length = sum(len(line.rstrip(b" ")) for line in lines)
        visible_bytes += visible_length
        if len(encoded) > longest[1]:
            longest = (offset, len(encoded))

    missing_accessible_offsets = tuple(
        offset
        for offset in accessible_offsets
        if offset not in accessible_layout_offsets
    )

    report: dict[str, object] = {
        "schema_version": 2,
        "result": "PASS" if not errors else "FAIL",
        "script": str((ROM_DIR / script_path).resolve()),
        "script_sha256": sha256((ROM_DIR / script_path).read_bytes()),
        "pointer_rom": str(Path(rom_path).resolve()),
        "pointer_table": {
            "accessible_rows": POKEDEX_ACCESSIBLE_COUNT,
            "extended_rows": POKEDEX_EXTENDED_POINTER_COUNT,
            "accessible_offset_fingerprint": (
                POKEDEX_ACCESSIBLE_OFFSET_FINGERPRINT
            ),
            "extended_offset_fingerprint": (
                POKEDEX_EXTENDED_OFFSET_FINGERPRINT
            ),
            "anchors": {
                str(species_id): f"0x{offset:06X}"
                for species_id, offset in (
                    POKEDEX_ACCESSIBLE_ANCHORS.items()
                )
            },
        },
        "inventory": str(INVENTORY_PATH.resolve()),
        "inventory_sha256": INVENTORY_SHA256,
        "script_entries": len(entries),
        "layout_rows": len(layout_entries),
        "accessible_expected_rows": POKEDEX_ACCESSIBLE_COUNT,
        "accessible_layout_rows": len(accessible_layout_offsets),
        "accessible_missing_layout_rows": len(
            missing_accessible_offsets
        ),
        "accessible_missing_layout_offsets": [
            f"0x{offset:06X}" for offset in missing_accessible_offsets
        ],
        "extended_pointer_rows": POKEDEX_EXTENDED_POINTER_COUNT,
        "extended_layout_rows": len(extended_layout_offsets),
        "extended_layout_offsets": [
            f"0x{offset:06X}"
            for offset in extended_offsets
            if offset in extended_layout_offsets
        ],
        "inventory_rows": len(inventory),
        "expected_inventory_rows": INVENTORY_POKEDEX_RECORD_COUNT,
        "checked_artificial_hyphenations": (
            artificial_hyphenations_checked
        ),
        "remaining_artificial_hyphenations": (
            artificial_hyphenations_remaining
        ),
        "expected_artificial_hyphenations": (
            INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT
        ),
        "line_width": POKEDEX_LINE_WIDTH,
        "maximum_lines": POKEDEX_MAX_LINES,
        "physical_lines": physical_lines,
        "accessible_physical_lines": accessible_physical_lines,
        "extended_physical_lines": extended_physical_lines,
        "four_line_records": full_four_line_records,
        "semantic_units": semantic_unit_count,
        "encoded_bytes": encoded_bytes,
        "visible_bytes": visible_bytes,
        "word_split_boundaries": word_split_boundaries,
        "longest_layout_offset": f"0x{longest[0]:06X}",
        "longest_layout_bytes": longest[1],
        "errors": errors,
    }
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Valide les descriptions Pokédex sur quatre lignes de 13."
    )
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument(
        "--rom",
        default=str(DEFAULT_POINTER_ROM),
        help="ROM anglaise canonique contenant la table à 0x03201E",
    )
    parser.add_argument(
        "--output",
        default="build/audits/pokedex_layout_validation.json",
    )
    args = parser.parse_args()

    report, errors = validate(args.script, args.rom)
    output = (
        Path(args.output)
        if Path(args.output).is_absolute()
        else ROM_DIR / args.output
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Validation mise en page Pokédex 13×4")
    print(
        "- Descriptions accessibles : "
        f"{report['accessible_layout_rows']}/"
        f"{report['accessible_expected_rows']}"
    )
    print(
        "- Layouts étendus validés : "
        f"{report['extended_layout_rows']}/"
        f"{report['extended_pointer_rows']} (non requis)"
    )
    print(f"- Lignes physiques : {report['physical_lines']}")
    print(
        "- Césures de mot au reflow : "
        f"{report['word_split_boundaries']}"
    )
    print(f"- Rapport : {output}")
    print(f"- Résultat : {report['result']}")
    if errors:
        for error in errors[:40]:
            print(f"  {error}")
        if len(errors) > 40:
            print(f"  ... et {len(errors) - 40} de plus")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
