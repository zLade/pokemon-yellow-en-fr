#!/usr/bin/env python3
"""Apply the reviewed accent audit and inline effective dialogue texts.

The command is deliberately conservative: it rewrites only calls whose
effective text differs from their literal source, or whose legacy dialogue
text is still supplied by the reviewed inventory.  Offsets and unrelated
source code are preserved byte-for-byte.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    DIALOGUE_LAYOUT,
    PATCH_SCRIPT,
    TRANSLATION_BASE_ROM,
    TranslationRow,
    apply_verified_pointer_redirects,
    assign_pointer_targets_to_rows,
    format_game_text,
    parse_patch_entries,
    read_bytes,
    source_record_len,
    structured_glyph_record_map,
    verified_field_dialogue_pointer_entries,
    verified_all_graphical_text_records,
)
from tools.audit_french_accents import audit  # noqa: E402
from tools.dialogue_inventory import load_dialogue_inventory  # noqa: E402


EXPECTED_ENTRY_COUNT = 1846
EXPECTED_AMBIGUOUS_OFFSETS = frozenset()


@dataclass(frozen=True)
class SourceCall:
    offset: int
    start: int
    end: int


def _line_byte_starts(data: bytes) -> list[int]:
    starts = [0]
    for index, value in enumerate(data):
        if value == 0x0A:
            starts.append(index + 1)
    return starts


def _source_calls(data: bytes, path: Path) -> dict[int, SourceCall]:
    source = data.decode("utf-8")
    tree = ast.parse(source, filename=str(path))
    line_starts = _line_byte_starts(data)
    calls: dict[int, SourceCall] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "p":
            continue
        if len(node.args) < 2:
            continue
        try:
            offset = ast.literal_eval(node.args[0])
            text = ast.literal_eval(node.args[1])
        except Exception:
            continue
        if not isinstance(offset, int) or not isinstance(text, str):
            continue
        if node.end_lineno is None or node.end_col_offset is None:
            raise ValueError(f"{path}:{node.lineno}: position AST incomplète")
        if offset in calls:
            raise ValueError(f"offset source en double: 0x{offset:06X}")
        calls[offset] = SourceCall(
            offset=offset,
            start=line_starts[node.lineno - 1] + node.col_offset,
            end=line_starts[node.end_lineno - 1] + node.end_col_offset,
        )
    return calls


def _fixed_width_text_chunks(text: str, width: int = 72) -> list[str]:
    if not text:
        return [""]
    return [text[index : index + width] for index in range(0, len(text), width)]


def _text_chunks(text: str, width: int = 72) -> list[str]:
    """Split source literals at spaces while preserving the exact text."""
    if not text:
        return [""]

    chunks: list[str] = []
    cursor = 0
    while len(text) - cursor > width:
        limit = cursor + width
        split = text.rfind(" ", cursor + 1, limit + 1)
        if split < 0:
            split = limit
        chunks.append(text[cursor:split])
        cursor = split
    chunks.append(text[cursor:])
    return chunks


def _quoted(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _render_call_with_chunks(
    offset: int,
    text: str,
    layout: str,
    chunks: list[str],
) -> str:
    layout_suffix = f', layout={_quoted(layout)}' if layout else ""
    single_line = f"p(0x{offset:06X}, {_quoted(text)}{layout_suffix})"
    if len(single_line) <= 100:
        return single_line

    lines = [
        "p(",
        f"    0x{offset:06X},",
    ]
    for chunk in chunks:
        lines.append(f"    {_quoted(chunk)}")
    lines[-1] += ","
    if layout:
        lines.append(f"    layout={_quoted(layout)},")
    lines.append(")")
    return "\n".join(lines)


def _render_call(offset: int, text: str, layout: str) -> str:
    return _render_call_with_chunks(
        offset,
        text,
        layout,
        _text_chunks(text),
    )


def _render_legacy_fixed_width_call(
    offset: int,
    text: str,
    layout: str,
) -> str:
    return _render_call_with_chunks(
        offset,
        text,
        layout,
        _fixed_width_text_chunks(text),
    )


def canonicalized_source(
    script_path: str | Path = PATCH_SCRIPT,
) -> tuple[bytes, dict[str, int]]:
    path = Path(script_path)
    if not path.is_absolute():
        path = ROM_DIR / path
    original = path.read_bytes()
    source_calls = _source_calls(original, path)

    raw_entries = parse_patch_entries(
        path,
        apply_dialogue_inventory=False,
    )
    effective_entries = parse_patch_entries(path)
    if len(raw_entries) != EXPECTED_ENTRY_COUNT:
        raise ValueError(
            f"{len(raw_entries)} entrées source, "
            f"{EXPECTED_ENTRY_COUNT} attendues"
        )
    if len(effective_entries) != EXPECTED_ENTRY_COUNT:
        raise ValueError(
            f"{len(effective_entries)} entrées effectives, "
            f"{EXPECTED_ENTRY_COUNT} attendues"
        )
    raw_by_offset = {entry.offset: entry for entry in raw_entries}
    effective_by_offset = {entry.offset: entry for entry in effective_entries}
    if (
        len(raw_by_offset) != EXPECTED_ENTRY_COUNT
        or len(effective_by_offset) != EXPECTED_ENTRY_COUNT
        or len(source_calls) != EXPECTED_ENTRY_COUNT
    ):
        raise ValueError(
            f"les {EXPECTED_ENTRY_COUNT} offsets doivent être uniques"
        )
    if not (
        set(raw_by_offset) == set(effective_by_offset) == set(source_calls)
    ):
        raise ValueError("les ensembles d'offsets source/effectifs divergent")

    report = audit(path)
    summary = report["summary"]
    ambiguous = {
        int(offset, 16)
        for offset in summary["ambiguous_offsets"]
    }
    if ambiguous != EXPECTED_AMBIGUOUS_OFFSETS:
        raise ValueError(
            "ambiguïtés inattendues: "
            + ", ".join(f"0x{offset:06X}" for offset in sorted(ambiguous))
        )

    corrections: dict[int, str] = {}
    for record in report["records"]:
        if record["encoded_bytes_before"] != record["encoded_bytes_after"]:
            raise ValueError(
                f"{record['offset_hex']}: correction non isométrique"
            )
        if record["effective_text_before"] != record["corrected_text"]:
            corrections[int(record["offset"])] = str(
                record["corrected_text"]
            )

    inventory_offsets = set(load_dialogue_inventory())
    inventory_backed = {
        entry.offset
        for entry in raw_entries
        if not entry.layout and entry.offset in inventory_offsets
    }

    original_rom = read_bytes(TRANSLATION_BASE_ROM)
    glyph_by_start = structured_glyph_record_map(
        verified_all_graphical_text_records(original_rom)
    )
    row_info = []
    for entry in raw_entries:
        max_len = source_record_len(
            original_rom,
            entry.offset,
            glyph_by_start,
        )
        semantic_text = (
            entry.text.lstrip("0")
            if entry.layout == DIALOGUE_LAYOUT
            else entry.text
        )
        row_info.append(
            (
                TranslationRow(
                    entry.offset,
                    semantic_text,
                    max_len,
                    entry.layout,
                ),
                max_len,
                format_game_text(semantic_text, entry.layout),
            )
        )
    field_pointer_entries = apply_verified_pointer_redirects(
        original_rom,
        verified_field_dialogue_pointer_entries(original_rom),
    )
    field_row_refs = assign_pointer_targets_to_rows(
        row_info,
        field_pointer_entries,
    )
    field_backed = {
        offset
        for offset, targets in field_row_refs.items()
        if any(refs for _, refs in targets)
    }

    replacements: list[tuple[int, int, bytes]] = []
    accent_rewrites = 0
    dialogue_rewrites = 0
    field_dialogue_rewrites = 0
    field_padding_rewrites = 0
    readability_rewrites = 0
    for offset, raw in raw_by_offset.items():
        canonical_dialogue = offset in inventory_backed
        canonical_field_dialogue = offset in field_backed
        call = source_calls[offset]
        source_call = original[call.start : call.end].decode("utf-8")
        legacy_call = _render_legacy_fixed_width_call(
            offset,
            raw.text,
            raw.layout,
        )
        readable_call = _render_call(offset, raw.text, raw.layout)
        legacy_chunking = (
            source_call == legacy_call
            and readable_call != legacy_call
        )
        field_padding = (
            canonical_field_dialogue
            and raw.text != raw.text.lstrip("0")
        )
        if (
            offset not in corrections
            and not canonical_dialogue
            and (
                not canonical_field_dialogue
                or raw.layout == DIALOGUE_LAYOUT
            )
            and not legacy_chunking
            and not field_padding
        ):
            continue

        effective = effective_by_offset[offset]
        desired_text = corrections.get(offset, effective.text)
        if canonical_field_dialogue:
            desired_text = desired_text.lstrip("0")
        desired_layout = (
            DIALOGUE_LAYOUT
            if canonical_dialogue or canonical_field_dialogue
            else raw.layout
        )
        if (
            not canonical_dialogue
            and not canonical_field_dialogue
            and desired_layout != raw.layout
        ):
            raise ValueError(
                f"0x{offset:06X}: changement de layout non autorisé"
            )
        if raw.layout == "pokedex_13x4" and desired_layout != raw.layout:
            raise ValueError(
                f"0x{offset:06X}: layout Pokédex modifié"
            )

        rendered = _render_call(
            offset,
            desired_text,
            desired_layout,
        ).encode("utf-8")
        replacements.append((call.start, call.end, rendered))
        accent_rewrites += offset in corrections
        dialogue_rewrites += canonical_dialogue
        field_dialogue_rewrites += (
            canonical_field_dialogue
            and raw.layout != DIALOGUE_LAYOUT
        )
        field_padding_rewrites += field_padding
        readability_rewrites += legacy_chunking

    updated = original
    for start, end, replacement in sorted(replacements, reverse=True):
        updated = updated[:start] + replacement + updated[end:]

    updated_calls = _source_calls(updated, path)
    if set(updated_calls) != set(source_calls):
        raise ValueError("la réécriture a modifié les offsets")

    return updated, {
        "entries": len(raw_entries),
        "rewritten_calls": len(replacements),
        "accent_rewrites": accent_rewrites,
        "dialogue_rewrites": dialogue_rewrites,
        "field_dialogue_rewrites": field_dialogue_rewrites,
        "field_padding_rewrites": field_padding_rewrites,
        "readability_rewrites": readability_rewrites,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Canonise les accents et dialogues effectifs de script.py."
    )
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument(
        "--write",
        action="store_true",
        help="écrit la source; sans cette option, effectue un contrôle à blanc",
    )
    args = parser.parse_args()

    path = Path(args.script)
    if not path.is_absolute():
        path = ROM_DIR / path
    updated, summary = canonicalized_source(path)
    original = path.read_bytes()
    changed = updated != original
    print(
        "Canonisation accents/dialogues: "
        f"{summary['entries']} entrées, "
        f"{summary['accent_rewrites']} corrections accentuelles, "
        f"{summary['dialogue_rewrites']} dialogues rendus explicites, "
        f"{summary['field_dialogue_rewrites']} dialogues terrain classés, "
        f"{summary['field_padding_rewrites']} préfixes terrain retirés, "
        f"{summary['readability_rewrites']} découpages rendus lisibles, "
        f"{summary['rewritten_calls']} appels réécrits"
    )
    if args.write and changed:
        path.write_bytes(updated)
        print(f"Source mise à jour: {path}")
    elif args.write:
        print("Source déjà canonique")
    else:
        print(
            "Contrôle à blanc: "
            + ("des changements sont requis" if changed else "aucun changement")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
