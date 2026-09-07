#!/usr/bin/env python3
"""Synchronize Mesen dialogue probe records with script.py."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import parse_patch_entries  # noqa: E402
from tools.dialogue_layout import wrap_dialogue_lines  # noqa: E402


DEFAULT_SCRIPT = ROM_DIR / "script.py"
DEFAULT_TARGETS = TOOLS_DIR / "campaign" / "dialogue_targets.lua"

BLOCK_RE = re.compile(
    r"(?ms)^    \{\n(?P<body>.*?^    \},\n)"
)
OFFSET_RE = re.compile(
    r"(?m)^\s*source_offset\s*=\s*(0x[0-9A-Fa-f]+),\s*$"
)
PAYLOAD_RE = re.compile(
    r"(?ms)"
    r"(?P<head>^        payload_hex\s*=\s*\n)"
    r"(?P<lines>"
    r"(?:^            \"[0-9A-Fa-f]+\" \.\.\n)*"
    r"^            \"[0-9A-Fa-f]+\",\n"
    r")"
)


def payload_expression(text: str, layout: str) -> str:
    pages = list(wrap_dialogue_lines(text, layout))
    if not pages:
        raise ValueError("dialogue has no pages")
    pages[-1] += b"\x0D"
    rendered = []
    for index, page in enumerate(pages):
        suffix = " .." if index + 1 < len(pages) else ","
        rendered.append(f'            "{page.hex()}"{suffix}\n')
    return "".join(rendered)


def synchronise(
    source: str,
    entries_by_offset: dict[int, object],
) -> tuple[str, tuple[int, ...]]:
    changed: list[int] = []

    def replace_block(match: re.Match[str]) -> str:
        block = match.group(0)
        offset_match = OFFSET_RE.search(block)
        if offset_match is None:
            return block
        offset = int(offset_match.group(1), 16)
        if offset not in entries_by_offset:
            raise ValueError(
                f"Mesen target missing from script.py : 0x{offset:06X}"
            )
        payload_match = PAYLOAD_RE.search(block)
        if payload_match is None:
            raise ValueError(
                f"unreadable payload_hex at 0x{offset:06X}"
            )
        entry = entries_by_offset[offset]
        replacement = (
            payload_match.group("head")
            + payload_expression(entry.text, entry.layout)
        )
        updated = (
            block[: payload_match.start()]
            + replacement
            + block[payload_match.end() :]
        )
        if updated != block:
            changed.append(offset)
        return updated

    updated = BLOCK_RE.sub(replace_block, source)
    return updated, tuple(changed)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Update payload_hex in dialogue_targets.lua from "
            "the pages actually compiled by script.py."
        )
    )
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the file; without this option, check only",
    )
    args = parser.parse_args()

    entries = {
        entry.offset: entry
        for entry in parse_patch_entries(
            str(args.script),
            apply_dialogue_inventory=False,
        )
    }
    source = args.targets.read_text(encoding="utf-8")
    updated, changed = synchronise(source, entries)
    if not changed:
        print(f"Dialogue targets synchronized : {args.targets}")
        return 0
    if not args.apply:
        offsets = ", ".join(f"0x{offset:06X}" for offset in changed)
        print(f"Stale dialogue targets : {offsets}", file=sys.stderr)
        return 1
    args.targets.write_text(updated, encoding="utf-8")
    offsets = ", ".join(f"0x{offset:06X}" for offset in changed)
    print(f"Dialogue targets updated : {offsets}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
