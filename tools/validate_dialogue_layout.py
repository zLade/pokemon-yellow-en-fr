#!/usr/bin/env python3
"""Validate every verified field and introduction dialogue layout."""

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
    TRANSLATION_BASE_ROM,
    TRANSLATION_BASE_SHA256,
    VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT,
    VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS,
    TranslationRow,
    apply_verified_pointer_redirects,
    assign_pointer_targets_to_rows,
    detect_pointer_table_entries,
    graphical_pointer_target_conflicts,
    known_source_target_offsets,
    merge_non_overlapping_pointer_entries,
    parse_patch_entries,
    read_bytes,
    remove_verified_non_dialogue_pointer_refs,
    reviewed_text_prefix_len,
    sha256,
    source_record_len,
    structured_glyph_record_map,
    verified_field_dialogue_pointer_entries,
    verified_pointer_override_entries,
    verified_all_graphical_text_records,
)
from tools.dialogue_inventory import (  # noqa: E402
    INVENTORY_FAULTY_BOUNDARY_COUNT,
    INVENTORY_LEGITIMATE_BOUNDARY_COUNT,
    INVENTORY_PATH,
    INVENTORY_SHA256,
    load_dialogue_inventory,
)
from tools.dialogue_layout import (  # noqa: E402
    DIALOGUE_LAYOUT,
    INTRO_DIALOGUE_LAYOUT,
    RAW_LAYOUT,
    dialogue_line_width,
    format_game_text,
    semantic_units,
    text_midword_boundary_positions,
    wrap_dialogue_lines,
)
from tools.french_font import encode_game_text  # noqa: E402


# These are the only unmarked source records whose visible payload would
# contain a lexical cut if it were sent through the regular 19/19 renderer.
# They are fixed-width copyright, battle, or item UI assets and do not use
# that renderer.  Keeping the list exact makes any new unclassified candidate
# fail validation instead of silently escaping the dialogue audit.
NON_DIALOGUE_BOUNDARY_EXEMPTIONS = {
    0x030392: "battle_message",
    0x0304C2: "battle_message",
    0x0304CF: "battle_message",
    0x0304DB: "battle_message",
    0x0304F1: "battle_message",
    0x0304FB: "battle_message",
    0x030505: "battle_message",
    0x03050F: "battle_message",
    0x030519: "battle_message",
    0x030541: "battle_message",
    0x030555: "battle_message",
    0x0306FE: "battle_message",
    0x030744: "battle_message",
    0x0307B9: "battle_message",
    0x0307C4: "battle_message",
    0x0307CF: "battle_message",
    0x031AE8: "item_interface",
    0x031B29: "item_interface",
    0x031B54: "item_interface",
    0x031B67: "item_interface",
    0x031B7A: "item_interface",
}

INTRO_DIALOGUE_OFFSETS = frozenset(
    {
        0x03082C,
        0x035DCC,
        0x035E82,
    }
)

EXPECTED_RAW_LAYOUT_OFFSETS = frozenset(
    {
        0x034656,
        0x035F3D,
        0x035F98,
        0x03656D,
        0x0368F1,
        0x039D3B,
        0x039D60,
        0x03DF0D,
    }
)


def validate_live_pointer_ownership(
    entries,
) -> tuple[dict[str, int], list[str]]:
    """Prove exact ownership of every field-dialogue target and pointer."""
    errors: list[str] = []
    original = read_bytes(TRANSLATION_BASE_ROM)
    if sha256(original) != TRANSLATION_BASE_SHA256:
        return {}, ["canonical English ROM missing or modified"]

    glyph_records = verified_all_graphical_text_records(original)
    glyph_by_start = structured_glyph_record_map(glyph_records)
    row_info = []
    for entry in entries:
        max_len = source_record_len(
            original,
            entry.offset,
            glyph_by_start,
        )
        row_info.append(
            (
                TranslationRow(
                    entry.offset,
                    entry.text,
                    max_len,
                    entry.layout,
                ),
                max_len,
                format_game_text(entry.text, entry.layout),
            )
        )

    known_offsets = known_source_target_offsets(
        original,
        (
            (row.offset, max_len)
            for row, max_len, _ in row_info
        ),
    )
    pointer_entries = detect_pointer_table_entries(
        original,
        min_run=5,
        known_offsets=known_offsets,
        min_known_ratio=0.4,
        min_known_count=3,
    )
    pointer_entries, skipped_verified = merge_non_overlapping_pointer_entries(
        pointer_entries,
        verified_pointer_override_entries(original),
    )
    if skipped_verified:
        errors.append(
            "verified pointer conflict: "
            + repr(skipped_verified[:5])
        )
    field_pointer_entries = verified_field_dialogue_pointer_entries(
        original
    )
    pointer_entries, skipped_field = merge_non_overlapping_pointer_entries(
        pointer_entries,
        field_pointer_entries,
    )
    if skipped_field:
        errors.append(
            "verified field pointer conflict: "
            + repr(skipped_field[:5])
        )
    pointer_entries = remove_verified_non_dialogue_pointer_refs(
        original,
        pointer_entries,
    )
    pointer_entries = apply_verified_pointer_redirects(
        original,
        pointer_entries,
    )
    field_pointer_entries = apply_verified_pointer_redirects(
        original,
        field_pointer_entries,
    )
    field_pointer_slots = sum(
        len(refs)
        for refs in field_pointer_entries.values()
    )
    if (
        field_pointer_slots
        != VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT
    ):
        errors.append(
            f"{field_pointer_slots} field slots after redirection, "
            f"{VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT} expected"
        )
    if (
        len(field_pointer_entries)
        != VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS
    ):
        errors.append(
            f"{len(field_pointer_entries)} field targets after "
            f"redirection, "
            f"{VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS} "
            "expected"
        )

    row_pointer_refs = assign_pointer_targets_to_rows(
        row_info,
        pointer_entries,
    )
    graphical_starts = {
        row.offset
        for row, _, _ in row_info
        if row.offset in glyph_by_start
    }
    errors.extend(
        graphical_pointer_target_conflicts(
            row_pointer_refs,
            graphical_starts,
        )
    )

    dialogue_rows_with_targets = 0
    dialogue_target_groups = 0
    safe_prefix_targets = 0
    exact_submessage_rows = 0
    field_target_owners: dict[int, list[int]] = {}
    field_owner_rows: set[int] = set()
    row_ranges = [
        (row.offset, row.offset + max_len)
        for row, max_len, _ in row_info
        if max_len > 0
    ]

    for row, max_len, _ in row_info:
        for target, refs in row_pointer_refs[row.offset]:
            if target not in field_pointer_entries or not refs:
                continue
            field_target_owners.setdefault(target, []).append(row.offset)
            field_owner_rows.add(row.offset)
            if row.layout != DIALOGUE_LAYOUT:
                errors.append(
                    f"0x{row.offset:06X}: owner of field target "
                    f"0x{target:06X} without layout {DIALOGUE_LAYOUT}"
                )

        if row.layout != DIALOGUE_LAYOUT:
            continue
        targets = row_pointer_refs[row.offset]
        if targets:
            dialogue_rows_with_targets += 1
        dialogue_target_groups += len(targets)
        if any(
            start < row.offset < end
            for start, end in row_ranges
            if start != row.offset
        ):
            exact_submessage_rows += 1
            if not any(
                target == row.offset and refs
                for target, refs in targets
            ):
                errors.append(
                    f"0x{row.offset:06X}: submessage without exact pointer"
                )

        source_prefix = reviewed_text_prefix_len(
            original[row.offset:row.offset + max_len]
        )
        for target, refs in targets:
            if not refs or target == row.offset:
                continue
            if row.offset in graphical_starts:
                safe_prefix_targets += 1
                continue
            if target == row.offset + source_prefix:
                safe_prefix_targets += 1
                continue
            errors.append(
                f"0x{row.offset:06X}: undeclared interior pointer "
                f"0x{target:06X} (+{target - row.offset})"
            )

    unowned_field_targets = sorted(
        set(field_pointer_entries) - set(field_target_owners)
    )
    multiply_owned_field_targets = {
        target: owners
        for target, owners in field_target_owners.items()
        if len(owners) != 1
    }
    common_layout_rows = {
        row.offset
        for row, _, _ in row_info
        if row.layout == DIALOGUE_LAYOUT
    }
    non_field_common_rows = sorted(
        common_layout_rows - field_owner_rows
    )
    for target in unowned_field_targets:
        errors.append(
            f"field target without translation row: 0x{target:06X}"
        )
    for target, owners in sorted(multiply_owned_field_targets.items()):
        errors.append(
            f"field target 0x{target:06X} owned by "
            + ", ".join(f"0x{owner:06X}" for owner in owners)
        )
    for offset in non_field_common_rows:
        errors.append(
            f"0x{offset:06X}: field layout without verified field target"
        )

    return {
        "detected_pointer_targets": len(pointer_entries),
        "detected_pointer_refs": sum(
            len(refs)
            for refs in pointer_entries.values()
        ),
        "dialogue_rows_with_live_targets": dialogue_rows_with_targets,
        "dialogue_live_target_groups": dialogue_target_groups,
        "safe_prefix_target_groups": safe_prefix_targets,
        "exact_submessage_rows": exact_submessage_rows,
        "verified_field_pointer_slots": field_pointer_slots,
        "verified_field_pointer_targets": len(field_pointer_entries),
        "owned_field_pointer_targets": len(field_target_owners),
        "field_dialogue_owner_rows": len(field_owner_rows),
        "unowned_field_pointer_targets": len(unowned_field_targets),
        "multiply_owned_field_pointer_targets": len(
            multiply_owned_field_targets
        ),
        "non_field_common_layout_rows": len(non_field_common_rows),
    }, errors


def validate(
    script_path: str | Path = PATCH_SCRIPT,
) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    raw_entries = parse_patch_entries(
        script_path,
        apply_dialogue_inventory=False,
    )
    migrated_entries = parse_patch_entries(script_path)
    raw_by_offset = {entry.offset: entry for entry in raw_entries}
    migrated_by_offset = {
        entry.offset: entry
        for entry in migrated_entries
    }
    if len(raw_by_offset) != len(raw_entries):
        errors.append("duplicate offset(s) in raw script")
    if len(migrated_by_offset) != len(migrated_entries):
        errors.append("duplicate offset(s) after migration")
    if set(raw_by_offset) != set(migrated_by_offset):
        errors.append("migration changed the set of offsets")

    intro_layout_offsets = {
        entry.offset
        for entry in migrated_entries
        if entry.layout == INTRO_DIALOGUE_LAYOUT
    }
    raw_layout_offsets = {
        entry.offset
        for entry in migrated_entries
        if entry.layout == RAW_LAYOUT
    }
    if intro_layout_offsets != INTRO_DIALOGUE_OFFSETS:
        errors.append(
            "unexpected introduction dialogue set: "
            + repr(
                {
                    "missing": sorted(
                        INTRO_DIALOGUE_OFFSETS - intro_layout_offsets
                    ),
                    "extra": sorted(
                        intro_layout_offsets - INTRO_DIALOGUE_OFFSETS
                    ),
                }
            )
        )
    if raw_layout_offsets != EXPECTED_RAW_LAYOUT_OFFSETS:
        errors.append(
            "unexpected raw layout set: "
            + repr(
                {
                    "missing": sorted(
                        EXPECTED_RAW_LAYOUT_OFFSETS - raw_layout_offsets
                    ),
                    "extra": sorted(
                        raw_layout_offsets - EXPECTED_RAW_LAYOUT_OFFSETS
                    ),
                }
            )
        )

    inventory = load_dialogue_inventory()
    missing_inventory_offsets = sorted(
        set(inventory) - set(migrated_by_offset)
    )
    for offset in missing_inventory_offsets:
        errors.append(
            f"inventoried dialogue missing from script: 0x{offset:06X}"
        )

    explicit_revisions = 0
    inventory_applied = 0
    inventory_non_dialogue_rows = 0
    artificial_hyphenations_removed = 0
    for offset, record in inventory.items():
        raw_entry = raw_by_offset.get(offset)
        entry = migrated_by_offset.get(offset)
        if raw_entry is None or entry is None:
            continue
        if entry.layout not in {
            DIALOGUE_LAYOUT,
            INTRO_DIALOGUE_LAYOUT,
            RAW_LAYOUT,
        }:
            errors.append(
                f"0x{offset:06X}: historical inventory without "
                "renderer classification"
            )
            continue
        if entry.layout == RAW_LAYOUT:
            inventory_non_dialogue_rows += 1
        if raw_entry.layout:
            explicit_revisions += 1
        else:
            inventory_applied += 1
            expected = str(record["semantic_text_proposed"]).lstrip("0")
            if entry.text != expected:
                errors.append(
                    f"0x{offset:06X}: semantic text differs "
                    "from the inventory"
                )
        for repair in record["artificial_hyphenations"]:
            source_form = str(repair["source_form"])
            reconstruction = str(repair["semantic_reconstruction"])
            if source_form in entry.text:
                errors.append(
                    f"0x{offset:06X}: remaining artificial hyphenation "
                    f"{source_form!r}"
                )
            if (
                not raw_entry.layout
                and reconstruction not in entry.text
            ):
                errors.append(
                    f"0x{offset:06X}: missing reconstruction "
                    f"{reconstruction!r}"
                )
            artificial_hyphenations_removed += 1

    common_layout_rows = 0
    intro_layout_rows = 0
    physical_lines = 0
    bubbles = 0
    semantic_unit_count = 0
    encoded_bytes = 0
    word_split_boundaries = 0
    longest: tuple[int, int] = (0, 0)
    for entry in migrated_entries:
        if entry.layout not in {
            DIALOGUE_LAYOUT,
            INTRO_DIALOGUE_LAYOUT,
        }:
            continue
        if entry.layout == DIALOGUE_LAYOUT:
            common_layout_rows += 1
        else:
            intro_layout_rows += 1
        try:
            lines = wrap_dialogue_lines(entry.text, entry.layout)
            encoded = format_game_text(entry.text, entry.layout)
        except ValueError as exc:
            errors.append(f"0x{entry.offset:06X}: {exc}")
            continue
        if encoded != b"".join(lines):
            errors.append(
                f"0x{entry.offset:06X}: wrapper/lines mismatch"
            )
        semantic_text = b" ".join(
            encode_game_text(unit)
            for unit in semantic_units(entry.text)
        )
        visible_reflow = b" ".join(
            line.rstrip(b" ")
            for line in lines
        )
        if visible_reflow != semantic_text:
            word_split_boundaries += 1
            errors.append(
                f"0x{entry.offset:06X}: word split or loss during reflow"
            )
        for line_index, line in enumerate(lines):
            width = dialogue_line_width(line_index, entry.layout)
            is_last = line_index == len(lines) - 1
            if len(line) > width:
                errors.append(
                    f"0x{entry.offset:06X}: line {line_index + 1} "
                    f"too long ({len(line)} > {width})"
                )
            if not is_last and len(line) != width:
                errors.append(
                    f"0x{entry.offset:06X}: full line "
                    f"{line_index + 1} not padded"
                )
        physical_lines += len(lines)
        # The ordinary renderer waits after every physical 19-column slice.
        # The introduction is the only observed two-line dialogue box.
        bubbles += (
            len(lines)
            if entry.layout == DIALOGUE_LAYOUT
            else (len(lines) + 1) // 2
        )
        semantic_unit_count += len(semantic_units(entry.text))
        encoded_bytes += len(encoded)
        if len(encoded) > longest[1]:
            longest = (entry.offset, len(encoded))

    unmarked_candidates: dict[int, tuple[int, ...]] = {}
    for entry in migrated_entries:
        if entry.layout:
            continue
        # Historical ASCII ``0`` bytes are pointer-side padding, not visible
        # dialogue columns.  Reset the phase at the first visible character.
        visible_text = entry.text.lstrip("0")
        boundaries = text_midword_boundary_positions(visible_text)
        if boundaries:
            unmarked_candidates[entry.offset] = boundaries

    unknown_candidates = sorted(
        set(unmarked_candidates) - set(NON_DIALOGUE_BOUNDARY_EXEMPTIONS)
    )
    stale_exemptions = sorted(
        set(NON_DIALOGUE_BOUNDARY_EXEMPTIONS) - set(unmarked_candidates)
    )
    for offset in unknown_candidates:
        errors.append(
            f"0x{offset:06X}: unmarked lexical boundary "
            f"{unmarked_candidates[offset]!r}"
        )
    for offset in stale_exemptions:
        errors.append(
            f"0x{offset:06X}: stale non-dialogue exemption"
        )

    pointer_report, pointer_errors = validate_live_pointer_ownership(
        migrated_entries,
    )
    errors.extend(pointer_errors)

    report: dict[str, object] = {
        "schema_version": 2,
        "result": "PASS" if not errors else "FAIL",
        "script": str((ROM_DIR / script_path).resolve()),
        "script_sha256": sha256((ROM_DIR / script_path).read_bytes()),
        "inventory": str(INVENTORY_PATH.resolve()),
        "inventory_sha256": INVENTORY_SHA256,
        "script_entries": len(migrated_entries),
        "dialogue_layout_rows": (
            common_layout_rows + intro_layout_rows
        ),
        "common_19x19_dialogue_rows": common_layout_rows,
        "intro_17x19_dialogue_rows": intro_layout_rows,
        "inventory_rows": len(inventory),
        "inventory_applied_rows": inventory_applied,
        "explicitly_revised_inventory_rows": explicit_revisions,
        "inventory_non_dialogue_rows": inventory_non_dialogue_rows,
        "historical_inventory_faulty_boundaries": (
            INVENTORY_FAULTY_BOUNDARY_COUNT
        ),
        "historical_inventory_legitimate_boundaries": (
            INVENTORY_LEGITIMATE_BOUNDARY_COUNT
        ),
        "removed_artificial_hyphenations": (
            artificial_hyphenations_removed
        ),
        "physical_lines": physical_lines,
        "dialogue_bubbles": bubbles,
        "word_split_boundaries": word_split_boundaries,
        "semantic_units": semantic_unit_count,
        "encoded_bytes": encoded_bytes,
        "longest_layout_offset": f"0x{longest[0]:06X}",
        "longest_layout_bytes": longest[1],
        "unmarked_boundary_candidates": len(unmarked_candidates),
        "reviewed_non_dialogue_candidates": len(
            NON_DIALOGUE_BOUNDARY_EXEMPTIONS
        ),
        "unclassified_boundary_candidates": len(unknown_candidates),
        "stale_non_dialogue_exemptions": len(stale_exemptions),
        **pointer_report,
        "errors": errors,
    }
    return report, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate 19/19 field and 17/19 introduction dialogues."
        )
    )
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument(
        "--output",
        default="build/audits/dialogue_layout_validation.json",
    )
    args = parser.parse_args()

    report, errors = validate(args.script)
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

    print("Dialogue layout validation 19/19 + intro 17/19")
    print(
        "- Field dialogues 19/19 : "
        f"{report['common_19x19_dialogue_rows']}"
    )
    print(
        "- Introduction dialogues 17/19 : "
        f"{report['intro_17x19_dialogue_rows']}"
    )
    print(
        "- Faulty boundaries in the historical inventory : "
        f"{report['historical_inventory_faulty_boundaries']}"
    )
    print(
        "- Legitimate boundaries in the historical inventory : "
        f"{report['historical_inventory_legitimate_boundaries']}"
    )
    print(
        "- Artificial hyphenations removed : "
        f"{report['removed_artificial_hyphenations']}"
    )
    print(
        "- Word splits after reflow : "
        f"{report['word_split_boundaries']}"
    )
    print(f"- Report: {output}")
    print(f"- Result: {report['result']}")
    if errors:
        for error in errors[:40]:
            print(f"  {error}")
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
