#!/usr/bin/env python3
"""Exhaustive coverage inventory for the French text pipeline."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    FINAL_ROM,
    PATCH_SCRIPT,
    TRANSLATION_BASE_ROM,
    TRANSLATION_BASE_SHA256,
    cpu_addr_for_offset,
    csv_safe,
    pair_for_offset,
    parse_patch_entries,
    read_bytes,
    sha256,
    source_record_len,
    source_record_text,
    structured_glyph_record_map,
    verified_all_graphical_text_records,
)
from tools.dialogue_layout import format_game_text  # noqa: E402


TEXT_BANK_START = 0x030010
TEXT_BANK_END = 0x040010
ASCII_RUN_RE = re.compile(rb"[ -~]{3,}")
ENGLISH_GRAPHIC_FONT_SLOT_COUNT = 868

# The records below are graphical symbols, not text.  They are kept as
# reviewed exceptions instead of being counted as untranslated dialogue.
# Their indices are deliberately explicit so a parser/order change fails
# loudly instead of silently widening the exception.
REVIEWED_LANGUAGE_NEUTRAL_GLYPH_RECORDS: dict[int, str] = {
    index: "type pictogram with no linguistic content"
    for index in range(32, 50)
}

# These source strings are intentionally unchanged because their spelling is
# already French. ``Ball`` is different: it is dead residue from the English
# patch.  The adjacent B597/B599 graphics already render ``Mist``/``Ball``;
# the 177-entry move-name table skips the redundant ASCII record.
REVIEWED_ASCII_REMAINDERS: dict[int, tuple[str, str, str]] = {
    0x030628: ("Type:", "invariant_fr", "identical label in French"),
    0x031161: ("Surf", "invariant_fr", "identical official name"),
    0x031410: (
        "Ball",
        "dead_unreferenced_english_patch_residue",
        (
            "redundant English patch residue: B597/B599 already render "
            "Mist/Ball and the 177-move table skips this record"
        ),
    ),
    0x0315EE: ("Flash", "invariant_fr", "identical official name"),
    0x031603: ("Encore", "invariant_fr", "identical official name"),
    0x03172B: ("000Antidote", "invariant_fr", "identical item"),
    0x0317AD: ("Pok@dex", "invariant_fr", "Pokédex encoded with @"),
    0x031ED0: ("Eusine", "proper_name", "identical proper name"),
    0x031ED8: ("Sage", "invariant_fr", "identical class"),
    0x033068: ("Surf", "invariant_fr", "identical official name"),
    0x033076: ("Flash", "invariant_fr", "identical official name"),
    0x036071: ("Rattata", "pokemon_name", "identical official name"),
    0x036097: ("Arbok", "pokemon_name", "identical official name"),
    0x03609D: ("Pikachu", "pokemon_name", "identical official name"),
    0x0360A5: ("Raichu", "pokemon_name", "identical official name"),
    0x0360C0: ("Nidoran=", "pokemon_name", "identical official name"),
    0x0360D3: ("Nidoqueen", "pokemon_name", "identical official name"),
    0x0360DD: ("Nidoran>", "pokemon_name", "identical official name"),
    0x0360F0: ("Nidoking", "pokemon_name", "identical official name"),
    0x036156: ("Paras", "pokemon_name", "identical official name"),
    0x03615C: ("Parasect", "pokemon_name", "identical official name"),
    0x03618D: ("Persian", "pokemon_name", "identical official name"),
    0x0361E4: ("Abra", "pokemon_name", "identical official name"),
    0x0361E9: ("Kadabra", "pokemon_name", "identical official name"),
    0x0361F1: ("Alakazam", "pokemon_name", "identical official name"),
    0x036232: ("Tentacool", "pokemon_name", "identical official name"),
    0x03623C: ("Tentacruel", "pokemon_name", "identical official name"),
    0x03625E: ("Ponyta", "pokemon_name", "identical official name"),
    0x03629D: ("Doduo", "pokemon_name", "identical official name"),
    0x0362A3: ("Dodrio", "pokemon_name", "identical official name"),
    0x0362EA: ("Onix", "pokemon_name", "identical official name"),
    0x0362FD: ("Krabby", "pokemon_name", "identical official name"),
    0x0363E6: ("Magmar", "pokemon_name", "identical official name"),
    0x0363F4: ("Tauros", "pokemon_name", "identical official name"),
    0x036439: ("Porygon", "pokemon_name", "identical official name"),
    0x036458: ("Kabutops", "pokemon_name", "identical official name"),
    0x0364A8: ("Mewtwo", "pokemon_name", "identical official name"),
    0x0364AF: ("Mew", "pokemon_name", "identical official name"),
    0x0364B3: ("Raikou", "pokemon_name", "identical official name"),
    0x0364BA: ("Entei", "pokemon_name", "identical official name"),
    0x0364C0: ("Suicune", "pokemon_name", "identical official name"),
    0x0364C8: ("Lugia", "pokemon_name", "identical official name"),
    0x0364CE: ("Ho-Oh", "pokemon_name", "identical official name"),
    0x0364D4: ("Kyogre", "pokemon_name", "identical official name"),
    0x0364DB: ("Groudon", "pokemon_name", "identical official name"),
    0x0364E3: ("Rayquaza", "pokemon_name", "identical official name"),
}


def significant_ascii_span(
    start: int,
    raw: bytes,
) -> tuple[int, int]:
    left = 0
    right = len(raw)
    while left < right and raw[left] in (0x20, 0x30):
        left += 1
    while right > left and raw[right - 1] in (0x20, 0x30):
        right -= 1
    return start + left, start + right


def is_lexical_ascii(raw: bytes) -> bool:
    text = raw.decode("ascii")
    letters = sum(character.isalpha() for character in text)
    return letters >= 3 and letters / max(1, len(text)) >= 0.25


def raw_pointer_refs(data: bytes, target: int) -> list[int]:
    pair = pair_for_offset(target)
    pair_start = 16 + pair * 0x8000
    pair_end = min(len(data), pair_start + 0x8000)
    word = cpu_addr_for_offset(target).to_bytes(2, "little")
    refs: list[int] = []
    cursor = pair_start
    while True:
        cursor = data.find(word, cursor, pair_end)
        if cursor < 0:
            return refs
        refs.append(cursor)
        cursor += 1


def graphic_font_slot(high: int, low: int) -> int:
    """Mirror the mapper-163 font index routine at ROM offset 0x019A53."""
    return (high - 0xB0) * 94 + ((low - 0xA1) & 0xFF)


def graphic_slot_counts(raw: bytes) -> tuple[int, int]:
    english_graphics = 0
    source_graphics = 0
    cursor = 0
    while cursor < len(raw):
        value = raw[cursor]
        if 0xB0 <= value <= 0xBF:
            slot = graphic_font_slot(value, raw[cursor + 1])
            if slot < ENGLISH_GRAPHIC_FONT_SLOT_COUNT:
                english_graphics += 1
            else:
                source_graphics += 1
            cursor += 2
        else:
            cursor += 1
    return english_graphics, source_graphics


def expected_csv_rows(english: bytes):
    glyph_by_start = structured_glyph_record_map(
        verified_all_graphical_text_records(english)
    )
    expected = []
    for entry in parse_patch_entries(PATCH_SCRIPT):
        max_len = source_record_len(
            english,
            entry.offset,
            glyph_by_start,
        )
        source = source_record_text(
            english,
            entry.offset,
            max_len,
            glyph_by_start,
        )
        encoded = format_game_text(entry.text, entry.layout)
        expected.append(
            {
                "offset_hex": f"0x{entry.offset:06X}",
                "line": str(entry.line),
                "layout": entry.layout,
                "max_len": str(max_len),
                "source_en": csv_safe(source),
                "fr_text": csv_safe(entry.text),
                "fr_len": str(len(encoded)),
                "overflow": (
                    "YES" if max_len and len(encoded) > max_len else ""
                ),
            }
        )
    return expected


def validate_csv_sync(
    english: bytes,
    csv_path: Path,
) -> list[str]:
    errors: list[str] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        actual = list(csv.DictReader(handle))
    expected = expected_csv_rows(english)
    if len(actual) != len(expected):
        errors.append(
            f"CSV/script: {len(actual)} rows instead of {len(expected)}"
        )
        return errors

    fields = (
        "offset_hex",
        "line",
        "layout",
        "max_len",
        "source_en",
        "fr_text",
        "fr_len",
        "overflow",
    )
    for index, (actual_row, expected_row) in enumerate(
        zip(actual, expected),
        start=2,
    ):
        for field in fields:
            if (actual_row.get(field) or "") != expected_row[field]:
                errors.append(
                    f"CSV row {index} field {field}: "
                    f"{actual_row.get(field)!r} instead of "
                    f"{expected_row[field]!r}"
                )
                break
    return errors


def audit(args: argparse.Namespace) -> int:
    english = read_bytes(args.english_rom)
    chinese = read_bytes(args.chinese_rom)
    candidate = read_bytes(args.rom)
    csv_path = (
        Path(args.csv)
        if Path(args.csv).is_absolute()
        else ROM_DIR / args.csv
    )
    ascii_report = (
        Path(args.ascii_report)
        if Path(args.ascii_report).is_absolute()
        else ROM_DIR / args.ascii_report
    )
    glyph_report = (
        Path(args.glyph_report)
        if Path(args.glyph_report).is_absolute()
        else ROM_DIR / args.glyph_report
    )
    ascii_report.parent.mkdir(parents=True, exist_ok=True)
    glyph_report.parent.mkdir(parents=True, exist_ok=True)

    errors = validate_csv_sync(english, csv_path)
    english_hash = sha256(english)
    if english_hash != TRANSLATION_BASE_SHA256:
        errors.append(
            "non-canonical English ROM: "
            f"{english_hash} instead of {TRANSLATION_BASE_SHA256}"
        )
    if len(chinese) != len(english):
        errors.append(
            "Chinese ROM size differs from English base: "
            f"{len(chinese)} instead of {len(english)}"
        )
    if len(candidate) != len(english):
        errors.append(
            "candidate ROM size differs from English base: "
            f"{len(candidate)} instead of {len(english)}"
        )

    glyph_records = verified_all_graphical_text_records(english)
    glyph_by_start = structured_glyph_record_map(glyph_records)
    patch_entries = parse_patch_entries(PATCH_SCRIPT)
    translated_ranges = []
    for entry in patch_entries:
        max_len = source_record_len(
            english,
            entry.offset,
            glyph_by_start,
        )
        translated_ranges.append(
            (entry.offset, entry.offset + max_len)
        )
    translated_glyph_starts = {
        entry.offset
        for entry in patch_entries
        if entry.offset in glyph_by_start
    }

    def covered(start: int, end: int) -> bool:
        return any(
            range_start <= start and end <= range_end
            for range_start, range_end in translated_ranges
        )

    reviewed_rows = []
    unknown_rows = []
    seen_reviewed = set()
    data = english[TEXT_BANK_START:TEXT_BANK_END]
    for match in ASCII_RUN_RE.finditer(data):
        start = TEXT_BANK_START + match.start()
        end = TEXT_BANK_START + match.end()
        raw = match.group()
        core_start, core_end = significant_ascii_span(start, raw)
        if covered(start, end) or (
            core_start < core_end and covered(core_start, core_end)
        ):
            continue
        if not is_lexical_ascii(raw):
            continue

        text = raw.decode("ascii")
        reviewed = REVIEWED_ASCII_REMAINDERS.get(start)
        row = {
            "offset_hex": f"0x{start:06X}",
            "length": len(raw),
            "source": text,
            "classification": "",
            "reason": "",
            "raw_pointer_refs": "",
        }
        if reviewed is None:
            row["classification"] = "UNREVIEWED"
            row["reason"] = "lexical ASCII run outside script/allowlist"
            unknown_rows.append(row)
            continue

        expected_text, classification, reason = reviewed
        if text != expected_text:
            errors.append(
                f"allowlist ASCII 0x{start:06X}: {text!r} "
                f"instead of {expected_text!r}"
            )
        seen_reviewed.add(start)
        refs = raw_pointer_refs(english, start)
        row["classification"] = classification
        row["reason"] = reason
        row["raw_pointer_refs"] = " ".join(
            f"0x{ref:06X}" for ref in refs
        )
        reviewed_rows.append(row)

    missing_allowlist = (
        set(REVIEWED_ASCII_REMAINDERS) - seen_reviewed
    )
    for offset in sorted(missing_allowlist):
        errors.append(
            f"ASCII allowlist entry not observed: 0x{offset:06X}"
        )
    for row in unknown_rows:
        errors.append(
            f"unclassified ASCII {row['offset_hex']}: "
            f"{row['source']!r}"
        )

    report_fields = (
        "offset_hex",
        "length",
        "classification",
        "reason",
        "raw_pointer_refs",
        "source",
    )
    with ascii_report.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=report_fields)
        writer.writeheader()
        writer.writerows(reviewed_rows + unknown_rows)

    glyph_rows = []
    mutated_untranslated_glyph_records = 0
    translated_glyph_records = 0
    reviewed_neutral_glyph_records = 0
    untranslated_language_glyph_records = 0
    unchanged_from_chinese = 0
    fully_english_graphic_records = 0
    mixed_graphic_records = 0
    source_graphic_codes = 0
    for record_index, (
        start,
        end,
        pair,
        glyph_count,
    ) in enumerate(glyph_records, start=1):
        same_chinese = chinese[start:end] == english[start:end]
        same_candidate = candidate[start:end] == english[start:end]
        translation_declared = start in translated_glyph_starts
        neutral_reason = REVIEWED_LANGUAGE_NEUTRAL_GLYPH_RECORDS.get(
            record_index,
            "",
        )
        reviewed_neutral = bool(neutral_reason)
        if translation_declared and reviewed_neutral:
            errors.append(
                f"graphical record {record_index} 0x{start:06X}: "
                "both translated and declared language-neutral"
            )
        if translation_declared:
            language_status = "translated_fr"
        elif reviewed_neutral:
            language_status = "reviewed_language_neutral"
        else:
            language_status = "UNTRANSLATED_LANGUAGE_BEARING"
            untranslated_language_glyph_records += 1
        english_codes, source_codes = graphic_slot_counts(
            english[start:end]
        )
        if source_codes:
            classification = "mixed_english_source_graphics"
            mixed_graphic_records += 1
        else:
            classification = "english_graphics"
            fully_english_graphic_records += 1
        source_graphic_codes += source_codes
        unchanged_from_chinese += int(same_chinese)
        translated_glyph_records += int(translation_declared)
        reviewed_neutral_glyph_records += int(reviewed_neutral)
        mutated_untranslated_glyph_records += int(
            not same_candidate and not translation_declared
        )
        refs = raw_pointer_refs(english, start)
        glyph_rows.append(
            {
                "record_index": record_index,
                "start_hex": f"0x{start:06X}",
                "end_hex_exclusive": f"0x{end:06X}",
                "pair": pair,
                "payload_bytes": end - start,
                "glyph_pairs": glyph_count,
                "english_graphic_codes": english_codes,
                "source_graphic_codes": source_codes,
                "classification": classification,
                "language_status": language_status,
                "neutral_reason": neutral_reason,
                "translation_declared": (
                    "YES" if translation_declared else ""
                ),
                "unchanged_chinese_to_english": (
                    "YES" if same_chinese else ""
                ),
                "preserved_in_candidate": (
                    "YES" if same_candidate else ""
                ),
                "raw_start_pointer_refs": " ".join(
                    f"0x{ref:06X}" for ref in refs
                ),
            }
        )

    with glyph_report.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "record_index",
                "start_hex",
                "end_hex_exclusive",
                "pair",
                "payload_bytes",
                "glyph_pairs",
                "english_graphic_codes",
                "source_graphic_codes",
                "classification",
                "language_status",
                "neutral_reason",
                "translation_declared",
                "unchanged_chinese_to_english",
                "preserved_in_candidate",
                "raw_start_pointer_refs",
            ),
        )
        writer.writeheader()
        writer.writerows(glyph_rows)

    if mutated_untranslated_glyph_records:
        errors.append(
            f"{mutated_untranslated_glyph_records} "
            "graphical record(s) modified without declared translation "
            "in the candidate ROM"
        )
    if untranslated_language_glyph_records:
        errors.append(
            f"{untranslated_language_glyph_records} "
            "language-bearing graphical record(s) without French translation"
        )

    english_orphans = sum(
        1
        for _, classification, _ in REVIEWED_ASCII_REMAINDERS.values()
        if classification == "orphan_unreferenced_en"
    )
    dead_english_patch_residues = sum(
        1
        for _, classification, _ in REVIEWED_ASCII_REMAINDERS.values()
        if classification
        == "dead_unreferenced_english_patch_residue"
    )
    print("Exhaustive translation coverage audit")
    print(f"- Script/CSV entries : {len(translated_ranges)}")
    print(f"- Classified ASCII remainders : {len(reviewed_rows)}")
    print(f"- Unknown ASCII remainders : {len(unknown_rows)}")
    print(f"- Known orphaned English fragments : {english_orphans}")
    print(
        "- Dead English patch residues : "
        f"{dead_english_patch_residues}"
    )
    print(
        "- Graphical records declared translated into French : "
        f"{translated_glyph_records}"
    )
    print(
        "- Untranslated graphical records preserved : "
        f"{len(glyph_records) - translated_glyph_records}"
    )
    print(
        "- Reviewed neutral graphical records (pictograms) : "
        f"{reviewed_neutral_glyph_records}"
    )
    print(
        "- Language-bearing graphical records still untranslated : "
        f"{untranslated_language_glyph_records}"
    )
    print(
        "- Records with codes unchanged from the Chinese ROM : "
        f"{unchanged_from_chinese}"
    )
    print(
        "- Records with codes modified by the English patch : "
        f"{len(glyph_records) - unchanged_from_chinese}"
    )
    print(
        "- Records fully rendered by the English graphical font : "
        f"{fully_english_graphic_records}"
    )
    print(
        "- Records mixing English graphics and source glyphs : "
        f"{mixed_graphic_records}"
    )
    print(
        "- Occurrences still pointing to the Chinese source font : "
        f"{source_graphic_codes}"
    )
    print(
        "- Graphical records modified without declaration : "
        f"{mutated_untranslated_glyph_records}"
    )
    print(f"- ASCII report : {ascii_report}")
    print(f"- Glyph report : {glyph_report}")

    if errors:
        print(f"- Result: FAIL ({len(errors)} error(s))")
        for error in errors[:40]:
            print(f"  {error}")
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more")
        return 1

    print(
        "- Inventory result : OK "
        "(in-game accessibility qualification remains separate)"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit ASCII and glyph text coverage."
    )
    parser.add_argument("--rom", default=FINAL_ROM)
    parser.add_argument("--csv", default="traduction_base.csv")
    parser.add_argument("--english-rom", default=TRANSLATION_BASE_ROM)
    parser.add_argument("--chinese-rom", default=CHINESE_ROM)
    parser.add_argument(
        "--ascii-report",
        default="build/audit/translation_ascii_coverage.csv",
    )
    parser.add_argument(
        "--glyph-report",
        default="build/audit/translation_glyph_records.csv",
    )
    return parser


if __name__ == "__main__":
    raise SystemExit(audit(build_parser().parse_args()))
