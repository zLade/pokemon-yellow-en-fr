#!/usr/bin/env python3
"""Validate the 159 compiled Pokédex descriptions through live ROM pointers.

The source-layout validator proves that every semantic French description
fits the 13x4 contract.  This validator closes the build gap: it follows the
actual pointer table in the final repacked ROM, then compares every compiled
payload and terminator with the exact bytes expected from ``script.py``.
"""

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
from tools.dialogue_layout import (  # noqa: E402
    POKEDEX_LAYOUT,
    POKEDEX_LINE_WIDTH,
    format_game_text,
    semantic_units,
    wrap_pokedex_lines,
)
from tools.french_font import decode_game_text, encode_game_text  # noqa: E402
from tools.pokedex_description_table import (  # noqa: E402
    DEFAULT_POINTER_ROM,
    POKEDEX_ACCESSIBLE_COUNT,
    POKEDEX_DESCRIPTION_TABLE_OFFSET,
    POKEDEX_EXTENDED_POINTER_COUNT,
    POKEDEX_POINTER_FILE_BIAS,
    load_pokedex_description_table,
)


DEFAULT_FINAL_ROM = ROM_DIR / "Pokemon_Jaune_FR_repacked_title.nes"
DEFAULT_OUTPUT = (
    ROM_DIR / "build" / "audits" / "final_pokedex_runtime_validation.json"
)
TERMINATOR = 0x0D


def _resolve(path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROM_DIR / candidate


def validate(
    final_rom_path: str | Path = DEFAULT_FINAL_ROM,
    script_path: str | Path = PATCH_SCRIPT,
    pointer_rom_path: str | Path = DEFAULT_POINTER_ROM,
) -> tuple[dict[str, object], list[str]]:
    """Return a machine-readable report and every hard validation error."""
    final_path = _resolve(final_rom_path)
    source_path = _resolve(pointer_rom_path)
    script_file = _resolve(script_path)
    final_rom = final_path.read_bytes()
    pointer_rom = source_path.read_bytes()
    errors: list[str] = []

    accessible, extended = load_pokedex_description_table(source_path)
    records = accessible + extended
    expected_count = (
        POKEDEX_ACCESSIBLE_COUNT + POKEDEX_EXTENDED_POINTER_COUNT
    )
    if len(records) != expected_count:
        errors.append(
            f"table source: {len(records)} fiches au lieu de {expected_count}"
        )

    entries = parse_patch_entries(
        script_file,
        apply_dialogue_inventory=False,
    )
    by_offset = {entry.offset: entry for entry in entries}
    if len(by_offset) != len(entries):
        errors.append("offset(s) en double dans script.py")

    exact_payloads = 0
    exact_terminators = 0
    valid_layouts = 0
    valid_pointer_ranges = 0
    physical_lines = 0
    word_split_boundaries = 0
    final_targets: list[int] = []
    report_records: list[dict[str, object]] = []

    bank_start = POKEDEX_POINTER_FILE_BIAS + 0x8000
    bank_end = POKEDEX_POINTER_FILE_BIAS + 0x10000
    table_end = POKEDEX_DESCRIPTION_TABLE_OFFSET + expected_count * 2
    if len(final_rom) < table_end:
        errors.append(
            "ROM finale trop courte pour la table Pokédex compilée"
        )

    for record in records:
        species_id = record.table_index
        source_offset = record.description_offset
        pointer_offset = (
            POKEDEX_DESCRIPTION_TABLE_OFFSET + 2 * (species_id - 1)
        )
        cpu_pointer = int.from_bytes(
            final_rom[pointer_offset : pointer_offset + 2],
            "little",
        )
        target_offset = cpu_pointer + POKEDEX_POINTER_FILE_BIAS
        final_targets.append(target_offset)

        pointer_valid = (
            0x8000 <= cpu_pointer <= 0xFFFF
            and bank_start <= target_offset < bank_end
            and target_offset < len(final_rom)
        )
        if pointer_valid:
            valid_pointer_ranges += 1
        else:
            errors.append(
                f"Pokédex #{species_id}: pointeur final 0x{cpu_pointer:04X} "
                f"hors banque (cible 0x{target_offset:06X})"
            )

        entry = by_offset.get(source_offset)
        layout_valid = entry is not None and entry.layout == POKEDEX_LAYOUT
        expected = b""
        lines: tuple[bytes, ...] = ()
        if entry is None:
            errors.append(
                f"Pokédex #{species_id}: source absente à "
                f"0x{source_offset:06X}"
            )
        elif entry.layout != POKEDEX_LAYOUT:
            errors.append(
                f"Pokédex #{species_id}: layout {entry.layout!r} au lieu de "
                f"{POKEDEX_LAYOUT!r}"
            )
        else:
            valid_layouts += 1
            try:
                lines = wrap_pokedex_lines(entry.text)
                expected = format_game_text(entry.text, entry.layout)
            except ValueError as exc:
                errors.append(f"Pokédex #{species_id}: {exc}")

        actual = (
            final_rom[target_offset : target_offset + len(expected)]
            if pointer_valid
            else b""
        )
        payload_exact = bool(expected) and actual == expected
        if payload_exact:
            exact_payloads += 1
        elif expected:
            mismatch = next(
                (
                    index
                    for index, (left, right) in enumerate(
                        zip(actual, expected, strict=False)
                    )
                    if left != right
                ),
                min(len(actual), len(expected)),
            )
            errors.append(
                f"Pokédex #{species_id}: payload compilé différent à "
                f"+0x{mismatch:X} (cible 0x{target_offset:06X})"
            )

        terminator_offset = target_offset + len(expected)
        terminator_exact = (
            pointer_valid
            and terminator_offset < len(final_rom)
            and final_rom[terminator_offset] == TERMINATOR
        )
        if terminator_exact:
            exact_terminators += 1
        elif expected:
            actual_terminator = (
                final_rom[terminator_offset]
                if terminator_offset < len(final_rom)
                else None
            )
            rendered = (
                "hors ROM"
                if actual_terminator is None
                else f"0x{actual_terminator:02X}"
            )
            errors.append(
                f"Pokédex #{species_id}: terminateur final {rendered} "
                "au lieu de 0x0D"
            )

        visible_reflow = b" ".join(
            line.rstrip(b" ") for line in lines
        )
        semantic = (
            b" ".join(
                encode_game_text(unit)
                for unit in semantic_units(entry.text)
            )
            if entry is not None
            else b""
        )
        word_split = bool(lines) and visible_reflow != semantic
        if word_split:
            word_split_boundaries += 1
            errors.append(
                f"Pokédex #{species_id}: perte ou césure lexicale "
                "dans les lignes compilées"
            )

        physical_lines += len(lines)
        report_records.append(
            {
                "table_index": species_id,
                "accessible_in_kanto_ui": record.accessible,
                "source_description_offset": f"0x{source_offset:06X}",
                "pointer_file_offset": f"0x{pointer_offset:06X}",
                "compiled_cpu_pointer": f"0x{cpu_pointer:04X}",
                "compiled_target_offset": f"0x{target_offset:06X}",
                "layout": entry.layout if entry is not None else None,
                "encoded_length": len(expected),
                "physical_line_count": len(lines),
                "compiled_lines": [
                    decode_game_text(line.rstrip(b" ")) for line in lines
                ],
                "pointer_range_valid": pointer_valid,
                "payload_exact": payload_exact,
                "terminator_exact": terminator_exact,
                "word_split": word_split,
            }
        )

    report: dict[str, object] = {
        "schema": "final_pokedex_runtime_validation/v1",
        "result": "PASS" if not errors else "FAIL",
        "inputs": {
            "final_rom": str(final_path.resolve()),
            "final_rom_sha256": sha256(final_rom),
            "pointer_source_rom": str(source_path.resolve()),
            "pointer_source_rom_sha256": sha256(pointer_rom),
            "script": str(script_file.resolve()),
            "script_sha256": sha256(script_file.read_bytes()),
        },
        "pointer_contract": {
            "table_file_offset": (
                f"0x{POKEDEX_DESCRIPTION_TABLE_OFFSET:06X}"
            ),
            "entry_encoding": "little-endian 16-bit CPU pointer",
            "target_formula": (
                f"cpu_pointer + 0x{POKEDEX_POINTER_FILE_BIAS:05X}"
            ),
            "compiled_target_bank": (
                f"0x{bank_start:06X}-0x{bank_end - 1:06X}"
            ),
            "terminator": "0x0D",
            "line_width": POKEDEX_LINE_WIDTH,
            "maximum_lines": 4,
        },
        "summary": {
            "expected_records": expected_count,
            "checked_records": len(records),
            "accessible_records": len(accessible),
            "extended_records": len(extended),
            "valid_layouts": valid_layouts,
            "valid_pointer_ranges": valid_pointer_ranges,
            "exact_payloads": exact_payloads,
            "exact_terminators": exact_terminators,
            "unique_compiled_targets": len(set(final_targets)),
            "physical_lines": physical_lines,
            "word_split_boundaries": word_split_boundaries,
            "errors": len(errors),
        },
        "errors": errors,
        "records": report_records,
    }
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Valide les 159 descriptions Pokédex via les pointeurs de la "
            "ROM finale compilée."
        )
    )
    parser.add_argument("--rom", default=DEFAULT_FINAL_ROM)
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument("--pointer-rom", default=DEFAULT_POINTER_ROM)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report, errors = validate(
        args.rom,
        args.script,
        args.pointer_rom,
    )
    output = _resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = report["summary"]
    print("Validation Pokédex compilé")
    print(f"- ROM : {report['inputs']['final_rom']}")
    print(f"- SHA-256 : {report['inputs']['final_rom_sha256']}")
    print(
        "- Fiches : "
        f"{summary['exact_payloads']}/{summary['expected_records']} "
        "payloads exacts"
    )
    print(
        "- Pointeurs/terminateurs : "
        f"{summary['valid_pointer_ranges']}/"
        f"{summary['exact_terminators']}"
    )
    print(
        f"- Lignes physiques : {summary['physical_lines']}; "
        f"césures lexicales : {summary['word_split_boundaries']}"
    )
    print(f"- Rapport : {output.resolve()}")
    if errors:
        print(f"- Résultat : ÉCHEC ({len(errors)} erreur(s))")
        for error in errors[:20]:
            print(f"  - {error}")
        return 1
    print("- Résultat : PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
