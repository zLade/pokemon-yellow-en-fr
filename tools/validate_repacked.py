#!/usr/bin/env python3
"""
Static validation of the repacked build.

This does not replace in-game testing. It checks unchanged ROM size,
32 KiB bank boundaries, non-overlapping allocations, pointer targets,
0x0D text terminators and fixed labels fitting their storage.




"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    TRANSLATION_BASE_ROM,
    TRANSLATION_BASE_SHA256,
    VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT,
    VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS,
    FreeSpan,
    allocate_suffix_pooled,
    apply_verified_pointer_redirects,
    assign_pointer_targets_to_rows,
    cpu_addr_for_offset,
    detect_contextual_pointer_entries,
    detect_pointer_table_entries,
    find_text_free_spans,
    graphical_pointer_target_conflicts,
    verified_all_graphical_text_records,
    has_source_record_terminator,
    intersects_spans,
    known_source_target_offsets,
    likely_text_pointer_target,
    merge_non_overlapping_pointer_entries,
    merge_free_spans,
    normalize_repacked_payload,
    offset_for_cpu_addr,
    pair_for_offset,
    protected_bank_tail,
    read_bytes,
    read_translation_csv,
    relocated_text_target,
    remove_verified_non_dialogue_pointer_refs,
    reviewed_text_prefix_len,
    sha256,
    source_record_len,
    structured_glyph_record_map,
    verified_field_dialogue_pointer_entries,
    verified_dialogue_restoration_payloads,
    verified_pointer_override_entries,
)
from tools.dialogue_layout import (  # noqa: E402
    DIALOGUE_LAYOUT,
    format_game_text,
)
from tools.french_font import (  # noqa: E402
    ASCII_FONT_OFFSET,
    ASCII_FONT_SIZE,
    extract_ascii_font,
    french_font_tiles,
    literal_slot_conflicts,
)


def compute_plan(args: argparse.Namespace):
    original = read_bytes(args.input_rom)
    original_hash = sha256(original)
    if original_hash != TRANSLATION_BASE_SHA256:
        raise ValueError(
            "Noncanonical base ROM: "
            f"{original_hash} instead of {TRANSLATION_BASE_SHA256}"
        )
    rows = read_translation_csv(args.csv)
    restoration_payloads = verified_dialogue_restoration_payloads(original)
    glyph_records = verified_all_graphical_text_records(original)
    glyph_by_start = structured_glyph_record_map(glyph_records)
    translated_glyph_starts = {
        row.offset
        for row in rows
        if row.offset in glyph_by_start
    }
    glyph_spans = [
        (start, end)
        for start, end, _, _ in glyph_records
        if start not in translated_glyph_starts
    ]

    row_info = []
    for row in rows:
        canonical_max_len = source_record_len(
            original,
            row.offset,
            glyph_by_start,
        )
        max_len = (
            row.max_len
            if row.max_len is not None
            else canonical_max_len
        )
        encoded = format_game_text(row.text, row.layout)
        conflicts = literal_slot_conflicts(row.text)
        if conflicts:
            raise ValueError(
                f"0x{row.offset:06X}: reserved punctuation "
                + " ".join(repr(item) for item in sorted(conflicts))
            )
        row_info.append((row, max_len, encoded))

    known_offsets = known_source_target_offsets(
        original,
        (
            (row.offset, max_len)
            for row, max_len, _ in row_info
        ),
    )
    pointer_entries = detect_pointer_table_entries(
        original,
        min_run=args.min_pointer_run,
        known_offsets=known_offsets,
        min_known_ratio=args.min_known_ratio,
        min_known_count=args.min_known_count,
    )
    verified_entries = verified_pointer_override_entries(original)
    field_pointer_entries = verified_field_dialogue_pointer_entries(
        original
    )
    pointer_entries, skipped_verified = merge_non_overlapping_pointer_entries(
        pointer_entries,
        verified_entries,
    )
    if skipped_verified:
        raise ValueError(
            "conflict in verified pointers: "
            + repr(skipped_verified[:5])
        )
    pointer_entries, skipped_field = merge_non_overlapping_pointer_entries(
        pointer_entries,
        field_pointer_entries,
    )
    if skipped_field:
        raise ValueError(
            "conflict in verified field pointers: "
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
        raise ValueError(
            f'{field_pointer_slots} field slots after redirection; expected {VERIFIED_FIELD_DIALOGUE_POINTER_SLOT_COUNT}'
        )
    if (
        len(field_pointer_entries)
        != VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS
    ):
        raise ValueError(
            f'{len(field_pointer_entries)} field targets after redirection; expected {VERIFIED_FIELD_DIALOGUE_TARGET_COUNT_AFTER_REDIRECTS}'
        )

    if args.min_context_pointers > 0:
        contextual_targets = set()
        for row, max_len, _ in row_info:
            if max_len < 1:
                continue
            plausible = {row.offset}
            delta = reviewed_text_prefix_len(
                original[row.offset:row.offset + max_len]
            )
            if 0 < delta < max_len:
                plausible.add(row.offset + delta)
            for target in plausible:
                if likely_text_pointer_target(original, target):
                    contextual_targets.add(target)

        contextual_entries = detect_contextual_pointer_entries(
            original,
            contextual_targets,
            window=args.context_pointer_window,
            min_context_count=args.min_context_pointers,
        )
        pointer_entries, _ = merge_non_overlapping_pointer_entries(pointer_entries, contextual_entries)

    pointer_spans = [
        (ref, ref + 2)
        for refs in pointer_entries.values()
        for ref in refs
    ]
    pointer_spans.extend(
        (ref, ref + 2)
        for ref in restoration_payloads
    )
    for target, refs in pointer_entries.items():
        for ref in refs:
            if intersects_spans(ref, ref + 2, glyph_spans):
                raise ValueError(
                    f'Pointer 0x{ref:06X} to 0x{target:06X} inside a protected glyph record'
                )
    row_pointer_refs = assign_pointer_targets_to_rows(
        row_info,
        pointer_entries,
    )
    field_target_owners: dict[int, list[int]] = {}
    for row, _, _ in row_info:
        for target, refs in row_pointer_refs[row.offset]:
            if target not in field_pointer_entries or not refs:
                continue
            field_target_owners.setdefault(target, []).append(row.offset)
            if row.layout != DIALOGUE_LAYOUT:
                raise ValueError(
                    f'0x{row.offset:06X}: field target 0x{target:06X} without layout {DIALOGUE_LAYOUT}'
                )
    unowned_field_targets = sorted(
        set(field_pointer_entries) - set(field_target_owners)
    )
    if unowned_field_targets:
        raise ValueError(
            "field targets without translations: "
            + ", ".join(
                f"0x{target:06X}"
                for target in unowned_field_targets
            )
        )
    multiply_owned_field_targets = {
        target: owners
        for target, owners in field_target_owners.items()
        if len(owners) != 1
    }
    if multiply_owned_field_targets:
        raise ValueError(
            "field targets with multiple owners: "
            + repr(multiply_owned_field_targets)
        )

    graphical_target_errors = graphical_pointer_target_conflicts(
        row_pointer_refs,
        translated_glyph_starts,
    )
    if graphical_target_errors:
        raise ValueError("; ".join(graphical_target_errors))

    candidate_offsets = set()
    for row, max_len, encoded in row_info:
        if max_len < 1:
            continue
        if not row_pointer_refs[row.offset]:
            continue
        if not has_source_record_terminator(
            original,
            row.offset,
            max_len,
        ):
            continue
        if args.only_overflow and len(encoded) <= max_len:
            continue
        candidate_offsets.add(row.offset)

    protected_non_candidates = []
    for row, max_len, _ in row_info:
        if max_len > 0 and row.offset not in candidate_offsets:
            protected_non_candidates.append((row.offset, min(len(original), row.offset + max_len + 1)))
    protected_non_candidates.extend(pointer_spans)
    protected_non_candidates.extend(glyph_spans)

    unsafe = set()
    for row, max_len, _ in row_info:
        if row.offset not in candidate_offsets or max_len < 1:
            continue
        end = min(len(original), row.offset + max_len + 1)
        if intersects_spans(row.offset, end, protected_non_candidates):
            unsafe.add(row.offset)
    candidate_offsets.difference_update(unsafe)

    normalized_by_offset = {}
    for row, max_len, encoded in row_info:
        if row.offset not in candidate_offsets:
            normalized_by_offset[row.offset] = encoded
            continue
        normalized_by_offset[row.offset] = normalize_repacked_payload(
            original,
            row.offset,
            max_len,
            encoded,
            (
                target
                for target, refs in row_pointer_refs[row.offset]
                if refs
            ),
            graphical=(row.offset in translated_glyph_starts),
        )
    row_info = [
        (row, max_len, normalized_by_offset[row.offset])
        for row, max_len, _ in row_info
    ]

    protected = []
    for row, max_len, _ in row_info:
        if max_len > 0 and row.offset not in candidate_offsets:
            protected.append((row.offset, min(len(original), row.offset + max_len + 1)))
    protected.extend(pointer_spans)
    protected.extend(glyph_spans)

    free_spans = find_text_free_spans(
        original,
        protected,
        min_len=args.min_free_run,
    )
    for row, max_len, _ in row_info:
        if row.offset in candidate_offsets and max_len > 0:
            free_spans.setdefault(pair_for_offset(row.offset), []).append(FreeSpan(row.offset, max_len + 1))
    for pair in list(free_spans):
        free_spans[pair] = merge_free_spans(free_spans[pair])

    allocation_payloads = {
        row.offset: encoded
        for row, _, encoded in row_info
        if row.offset in candidate_offsets
    }
    allocation_payloads.update(restoration_payloads)
    allocations, failures = allocate_suffix_pooled(
        free_spans,
        allocation_payloads,
    )

    return (
        original,
        row_info,
        row_pointer_refs,
        allocations,
        failures,
        free_spans,
        unsafe,
    )


def find_overlaps(ranges):
    ranges = sorted(ranges)
    overlaps = []
    for prev, current in zip(ranges, ranges[1:]):
        prev_start, prev_end, prev_label = prev
        cur_start, cur_end, cur_label = current
        if cur_start < prev_end:
            overlaps.append((prev_label, cur_label, prev_start, prev_end, cur_start, cur_end))
    return overlaps


def reconstruct_expected_text_banks(
    original: bytes,
    row_info,
    row_pointer_refs,
    restoration_payloads,
    allocations,
) -> tuple[bytes, list[str]]:
    """
    Rebuild the exact expected bytes for every translated text bank.

    This deliberately validates fixed texts, cleared source slots, allocated
    destinations and pointer words together. A stray write anywhere else in
    banks 6/7 therefore fails the full-bank comparison below.
    """
    expected = bytearray(original)
    errors: list[str] = []
    graphical_starts = {
        start
        for start, _, _, _ in verified_all_graphical_text_records(original)
    }

    for row, max_len, _ in row_info:
        if row.offset in allocations and max_len > 0:
            expected[row.offset:row.offset + max_len + 1] = (
                b"\0" * (max_len + 1)
            )

    for row, max_len, encoded in row_info:
        if max_len < 1:
            errors.append(
                f"0x{row.offset:06X}: no canonical source span"
            )
            continue

        if row.offset in allocations:
            new_offset = allocations[row.offset]
            end = new_offset + len(encoded) + 1
            expected[new_offset:end] = encoded + b"\x0D"
            for target, refs in row_pointer_refs[row.offset]:
                expected_target = relocated_text_target(
                    original,
                    row.offset,
                    max_len,
                    encoded,
                    target,
                    new_offset,
                    collapse_graphical_interior=(
                        row.offset in graphical_starts
                    ),
                )
                address = cpu_addr_for_offset(expected_target)
                word = address.to_bytes(2, "little")
                for ref in refs:
                    expected[ref:ref + 2] = word
            continue

        if len(encoded) > max_len:
            errors.append(
                f'0x{row.offset:06X}: fixed text too long ({len(encoded)} > {max_len})'
            )
            continue
        expected[row.offset:row.offset + max_len] = encoded.ljust(max_len)

    for ref, encoded in sorted(restoration_payloads.items()):
        new_offset = allocations[ref]
        end = new_offset + len(encoded) + 1
        expected[new_offset:end] = encoded + b"\x0D"
        address = cpu_addr_for_offset(new_offset)
        expected[ref:ref + 2] = address.to_bytes(2, "little")

    return bytes(expected), errors


def changed_ranges(left: bytes, right: bytes, start: int, end: int):
    """Return compact differing ranges within [start, end)."""
    ranges = []
    cursor = start
    while cursor < end:
        if left[cursor] == right[cursor]:
            cursor += 1
            continue
        range_start = cursor
        cursor += 1
        while cursor < end and left[cursor] != right[cursor]:
            cursor += 1
        ranges.append((range_start, cursor))
    return ranges


def command_validate(args: argparse.Namespace) -> int:
    (
        original,
        row_info,
        row_pointer_refs,
        allocations,
        failures,
        free_spans,
        unsafe,
    ) = compute_plan(args)
    restoration_payloads = verified_dialogue_restoration_payloads(original)
    patched = read_bytes(args.rom)
    errors = []
    warnings = []

    if len(patched) != len(original):
        errors.append(f'ROM size differs: {len(patched)} != {len(original)}')

    if failures:
        errors.append(f"{len(failures)} failed allocation(s)")

    seen_offsets = set()
    glyph_by_start = structured_glyph_record_map(
        verified_all_graphical_text_records(original)
    )
    for row, max_len, encoded in row_info:
        if row.offset in seen_offsets:
            errors.append(f"duplicate translated offset: 0x{row.offset:06X}")
        seen_offsets.add(row.offset)
        canonical_max_len = source_record_len(
            original,
            row.offset,
            glyph_by_start,
        )
        if max_len != canonical_max_len:
            errors.append(
                f"0x{row.offset:06X}: max_len CSV {max_len}, "
                f"canonical source {canonical_max_len}"
            )
        if any(value < 0x20 or value > 0x7E for value in encoded):
            errors.append(
                f"0x{row.offset:06X}: nonprintable translation"
            )

    base_font = extract_ascii_font(original)
    expected_font_tiles = french_font_tiles(base_font)
    for code, expected_tile in sorted(expected_font_tiles.items()):
        offset = ASCII_FONT_OFFSET + (code - 0x20) * 16
        actual_tile = patched[offset : offset + 16]
        if actual_tile != expected_tile:
            errors.append(
                f'Unexpected French glyph 0x{code:02X} at 0x{offset:06X}'
            )

    allocated_ranges = []
    row_by_offset = {row.offset: (row, max_len, encoded) for row, max_len, encoded in row_info}
    payload_by_offset = {
        row.offset: encoded
        for row, _, encoded in row_info
        if row.offset in allocations
    }
    payload_by_offset.update(restoration_payloads)
    for old_offset, new_offset in allocations.items():
        encoded = payload_by_offset[old_offset]
        size = len(encoded) + 1
        end = new_offset + size
        allocated_ranges.append((new_offset, end, old_offset))

        if end > len(patched):
            errors.append(f'0x{old_offset:06X}: relocated text outside ROM')
        if pair_for_offset(new_offset) != pair_for_offset(end - 1):
            errors.append(f'0x{old_offset:06X}: relocated text crosses a bank')

        expected = encoded + b"\x0D"
        actual = patched[new_offset:end]
        if actual != expected:
            errors.append(f'0x{old_offset:06X}: relocated text differs from expected bytes')

    overlaps = find_overlaps(allocated_ranges)
    incompatible_overlaps = []
    for (
        left,
        right,
        left_start,
        left_end,
        right_start,
        right_end,
    ) in overlaps:
        overlap_start = max(left_start, right_start)
        overlap_end = min(left_end, right_end)
        left_payload = payload_by_offset[left] + b"\x0D"
        right_payload = payload_by_offset[right] + b"\x0D"
        left_bytes = left_payload[
            overlap_start - left_start:overlap_end - left_start
        ]
        right_bytes = right_payload[
            overlap_start - right_start:overlap_end - right_start
        ]
        if left_end != right_end or left_bytes != right_bytes:
            incompatible_overlaps.append(
                (
                    left,
                    right,
                    left_start,
                    left_end,
                    right_start,
                    right_end,
                )
            )

    for (
        left,
        right,
        left_start,
        left_end,
        right_start,
        right_end,
    ) in incompatible_overlaps[:20]:
        errors.append(
            f'Incompatible overlap: 0x{left:06X} [{left_start:06X}:{left_end:06X}] with 0x{right:06X} [{right_start:06X}:{right_end:06X}]'
        )
    if len(incompatible_overlaps) > 20:
        errors.append(
            "... and "
            f"{len(incompatible_overlaps) - 20} additional "
            "incompatible overlap(s)"
        )

    expected_by_pointer = {}
    conflicts = []
    for old_offset, new_offset in allocations.items():
        if old_offset in restoration_payloads:
            continue
        row, max_len, encoded = row_by_offset[old_offset]
        for target, refs in row_pointer_refs[old_offset]:
            expected_target = relocated_text_target(
                original,
                old_offset,
                max_len,
                encoded,
                target,
                new_offset,
                collapse_graphical_interior=(
                    old_offset in glyph_by_start
                ),
            )
            for ref in refs:
                previous = expected_by_pointer.get(ref)
                if previous is not None and previous != expected_target:
                    conflicts.append((ref, previous, expected_target))
                expected_by_pointer[ref] = expected_target

    # The four reviewed bad English refs are deliberately overwritten here,
    # after the ordinary redirected table entries, just like in the builder.
    for ref in restoration_payloads:
        expected_by_pointer[ref] = allocations[ref]

    for ref, previous, current in conflicts[:20]:
        errors.append(
            f"pointer 0x{ref:06X} targets two texts: 0x{previous:06X} and 0x{current:06X}"
        )
    if len(conflicts) > 20:
        errors.append(f"... and {len(conflicts) - 20} additional pointer conflict(s)")

    for ref, expected_target in expected_by_pointer.items():
        address = int.from_bytes(patched[ref:ref + 2], "little")
        pair = pair_for_offset(ref)
        actual_target = offset_for_cpu_addr(pair, address, len(patched))
        if actual_target != expected_target:
            errors.append(
                f'Pointer 0x{ref:06X}: target 0x{actual_target or 0:06X}, expected 0x{expected_target:06X}'
            )
            continue

        end = patched.find(b"\x0D", expected_target, min(len(patched), expected_target + args.max_text_scan))
        if end < 0:
            errors.append(f'Pointer 0x{ref:06X}: target text missing 0x0D terminator')
            continue

        block = patched[expected_target:end]
        if not block:
            errors.append(f'Pointer 0x{ref:06X}: empty target text')
        if any(value < 0x20 or value > 0x7E for value in block):
            errors.append(f'Pointer 0x{ref:06X}: target contains nonprintable bytes')

    expected_rom, reconstruction_errors = reconstruct_expected_text_banks(
        original,
        row_info,
        row_pointer_refs,
        restoration_payloads,
        allocations,
    )
    errors.extend(reconstruction_errors)

    full_bank_differences = []
    for pair in (6, 7):
        bank_start = 16 + pair * 0x8000
        bank_end = min(len(original), bank_start + 0x8000)
        if len(patched) < bank_end:
            continue
        differences = changed_ranges(
            expected_rom,
            patched,
            bank_start,
            bank_end,
        )
        full_bank_differences.extend(
            (pair, start, end)
            for start, end in differences
        )
        if differences:
            errors.append(
                f"bank {pair}: {len(differences)} range(s) differ "
                "from the exact reconstruction"
            )

        tail_start, tail_end = protected_bank_tail(pair)
        base_tail = original[tail_start:tail_end]
        patched_tail = patched[tail_start:tail_end]
        if patched_tail != base_tail:
            errors.append(
                f"bank {pair}: tail code $FFC0-$FFFF changed "
                f"(base {hashlib.sha256(base_tail).hexdigest()}, "
                f"ROM {hashlib.sha256(patched_tail).hexdigest()})"
            )

    fixed_overflow_rows = 0
    report = ROM_DIR / args.fixed_overflow
    if report.exists():
        try:
            with report.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                required_fields = {
                    "offset_hex",
                    "max_len",
                    "fr_len",
                    "overflow",
                    "fr_text",
                }
                if not required_fields.issubset(reader.fieldnames or []):
                    errors.append(
                        f'Invalid overflow report: {report}'
                    )
                fixed_overflow_rows = sum(1 for _ in reader)
        except (OSError, csv.Error) as exc:
            errors.append(
                f"unreadable overflow report: {report} ({exc})"
            )
    else:
        errors.append(f'Missing report: {report}')

    if fixed_overflow_rows:
        errors.append(f'{fixed_overflow_rows} fixed text record(s) still too long')

    print("Static repack validation")
    print(f"- ROM : {ROM_DIR / args.rom if not Path(args.rom).is_absolute() else Path(args.rom)}")
    print(f"- Identical size: {'YES' if len(patched) == len(original) else 'NO'} ({len(patched)} bytes)")
    print(f"- Relocated texts : {len(allocations)}")
    print(f"- Restored Chinese dialogues : {len(restoration_payloads)}")
    print(f"- Allocation failures : {len(failures)}")
    print(
        "- Exact/suffix sharing : "
        f"{len(overlaps) - len(incompatible_overlaps)}"
    )
    print(
        "- Incompatible overlaps : "
        f"{len(incompatible_overlaps)}"
    )
    print(f"- Pointer conflicts : {len(conflicts)}")
    print(f"- Fixed texts too long : {fixed_overflow_rows}")
    print(f'- Candidates ignored due to overlap: {len(unsafe)}')
    print(
        "- Bank 6/7 reconstruction differences : "
        f"{len(full_bank_differences)}"
    )

    for pair in sorted(pair for pair in free_spans if pair in (6, 7)):
        total = sum(span.length for span in free_spans[pair])
        largest = max((span.length for span in free_spans[pair]), default=0)
        print(f'- Bank/pair {pair}: {total} free bytes remaining, largest block {largest}')

    if warnings:
        print(f"- Warnings : {len(warnings)}")
        for warning in warnings:
            print(f"  {warning}")

    if errors:
        print(f"- ERRORS : {len(errors)}")
        for error in errors[:40]:
            print(f"  {error}")
        remaining = max(0, 40 - len(errors))
        if remaining and full_bank_differences:
            for pair, start, end in full_bank_differences[:remaining]:
                print(
                    f"  bank {pair}: 0x{start:06X}-0x{end:06X}"
                )
        if len(errors) > 40:
            print(f"  ... and {len(errors) - 40} more")
        return 1

    print("- Result : OK")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Statically validate a repacked ROM.')
    parser.add_argument("--rom", default="Pokemon_Jaune_FR_repacked.nes")
    parser.add_argument("--csv", default="traduction_base.csv")
    parser.add_argument("--input-rom", default=TRANSLATION_BASE_ROM)
    parser.add_argument("--fixed-overflow", default="textes_fixes_trop_longs.csv")
    parser.add_argument("--min-pointer-run", type=int, default=5)
    parser.add_argument("--min-known-ratio", type=float, default=0.4)
    parser.add_argument("--min-known-count", type=int, default=3)
    parser.add_argument("--min-free-run", type=int, default=32)
    parser.add_argument("--context-pointer-window", type=int, default=32)
    parser.add_argument("--min-context-pointers", type=int, default=0)
    parser.add_argument("--only-overflow", action="store_true")
    parser.add_argument("--max-text-scan", type=int, default=1024)
    return parser


def main() -> int:
    return command_validate(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
