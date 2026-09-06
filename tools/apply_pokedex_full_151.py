#!/usr/bin/env python3
"""Apply the reviewed, pointer-accurate Kanto Pokédex migration.

The 151 target offsets are derived from the English ROM pointer table by
``audit_pokedex_full_151.build_report``.  Only those calls are rewritten; the
extended post-Kanto descriptions and every unrelated translation stay
byte-for-byte unchanged.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import PATCH_SCRIPT, parse_patch_entries  # noqa: E402
from tools.audit_pokedex_full_151 import (  # noqa: E402
    DEFAULT_CSV,
    DEFAULT_ROM,
    KANTO_COUNT,
    build_report,
)
from tools.canonicalize_french_accents import (  # noqa: E402
    _render_call,
    _source_calls,
)
from tools.dialogue_layout import POKEDEX_LAYOUT, wrap_pokedex_lines  # noqa: E402


def _literal_records(data: bytes, path: Path) -> dict[int, tuple[str, str]]:
    """Read literal ``p()`` text/layout pairs from an in-memory source."""
    tree = ast.parse(data.decode("utf-8"), filename=str(path))
    records: dict[int, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "p"
            and len(node.args) >= 2
        ):
            continue
        try:
            offset = ast.literal_eval(node.args[0])
            text = ast.literal_eval(node.args[1])
        except Exception:
            continue
        if not isinstance(offset, int) or not isinstance(text, str):
            continue
        layout = ""
        for keyword in node.keywords:
            if keyword.arg == "layout":
                layout = ast.literal_eval(keyword.value)
        if offset in records:
            raise ValueError(f"offset en double: 0x{offset:06X}")
        records[offset] = (text, layout)
    return records


def migrated_source(
    script_path: str | Path = PATCH_SCRIPT,
    rom_path: str | Path = DEFAULT_ROM,
    csv_path: str | Path = DEFAULT_CSV,
) -> tuple[bytes, dict[str, int]]:
    """Return the migrated source and a deterministic change summary."""
    script = Path(script_path)
    if not script.is_absolute():
        script = ROM_DIR / script
    rom = Path(rom_path)
    if not rom.is_absolute():
        rom = ROM_DIR / rom
    csv_file = Path(csv_path)
    if not csv_file.is_absolute():
        csv_file = ROM_DIR / csv_file

    original = script.read_bytes()
    source_calls = _source_calls(original, script)
    raw_entries = parse_patch_entries(
        script,
        apply_dialogue_inventory=False,
    )
    raw_by_offset = {entry.offset: entry for entry in raw_entries}
    if len(raw_by_offset) != len(raw_entries):
        raise ValueError("le script contient des offsets en double")

    report = build_report(rom, script, csv_file)
    records = report["records"]
    if len(records) != KANTO_COUNT:
        raise ValueError(
            f"{len(records)} descriptions accessibles, {KANTO_COUNT} attendues"
        )

    target_offsets: set[int] = set()
    replacements: list[tuple[int, int, bytes]] = []
    content_changes = 0
    layout_changes = 0

    for record in records:
        offset = int(str(record["description_offset"]), 16)
        if offset in target_offsets:
            raise ValueError(
                f"pointeur Pokédex accessible en double: 0x{offset:06X}"
            )
        target_offsets.add(offset)
        desired = str(record["proposed_fr"])
        wrap_pokedex_lines(desired)

        current = raw_by_offset.get(offset)
        call = source_calls.get(offset)
        if current is None or call is None:
            raise ValueError(
                f"description Pokédex absente à 0x{offset:06X}"
            )
        if current.text != str(record["current_fr"]):
            raise ValueError(
                f"rapport périmé à 0x{offset:06X}: texte source divergent"
            )

        needs_content = current.text != desired
        needs_layout = current.layout != POKEDEX_LAYOUT
        if not needs_content and not needs_layout:
            continue
        replacement = _render_call(
            offset,
            desired,
            POKEDEX_LAYOUT,
        ).encode("utf-8")
        replacements.append((call.start, call.end, replacement))
        content_changes += needs_content
        layout_changes += needs_layout

    if len(target_offsets) != KANTO_COUNT:
        raise ValueError(
            f"{len(target_offsets)} offsets uniques, {KANTO_COUNT} attendus"
        )

    updated = original
    for start, end, replacement in sorted(replacements, reverse=True):
        updated = updated[:start] + replacement + updated[end:]

    updated_records = _literal_records(updated, script)
    for offset in target_offsets:
        text, layout = updated_records[offset]
        if layout != POKEDEX_LAYOUT:
            raise ValueError(
                f"layout final absent à 0x{offset:06X}"
            )
        wrap_pokedex_lines(text)

    return updated, {
        "accessible_descriptions": len(target_offsets),
        "rewritten_calls": len(replacements),
        "content_changes": content_changes,
        "layout_changes": layout_changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migre les 151 descriptions Kanto au format Pokédex 13×4."
    )
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument("--rom", default=str(DEFAULT_ROM))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument(
        "--write",
        action="store_true",
        help="écrit script.py; sans cette option, effectue un contrôle à blanc",
    )
    args = parser.parse_args()

    script = Path(args.script)
    if not script.is_absolute():
        script = ROM_DIR / script
    updated, summary = migrated_source(script, args.rom, args.csv)
    changed = updated != script.read_bytes()
    print(
        "Migration Pokédex Kanto: "
        f"{summary['accessible_descriptions']} descriptions, "
        f"{summary['content_changes']} contenus corrigés, "
        f"{summary['layout_changes']} layouts ajoutés, "
        f"{summary['rewritten_calls']} appels réécrits"
    )
    if args.write and changed:
        script.write_bytes(updated)
        print(f"Source mise à jour: {script}")
    elif args.write:
        print("Source déjà migrée")
    else:
        print(
            "Contrôle à blanc: "
            + ("des changements sont requis" if changed else "aucun changement")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
