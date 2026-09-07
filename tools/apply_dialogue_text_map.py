#!/usr/bin/env python3
"""Apply an offset-to-text JSON map to p(...) calls in script.py."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from tools.apply_dialogue_page_plan import (  # noqa: E402
    _absolute_character_offset,
    _string_expression,
)


def load_text_map(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("the JSON map must be a non-empty object")
    result: dict[int, str] = {}
    for raw_offset, raw_text in raw.items():
        if not isinstance(raw_offset, str):
            raise ValueError("offset key is not a string")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError(f"empty text at {raw_offset}")
        offset = int(raw_offset, 0)
        if offset in result:
            raise ValueError(f"duplicate offset : 0x{offset:06X}")
        if any(not page.strip() for page in raw_text.splitlines()):
            raise ValueError(f"empty page at 0x{offset:06X}")
        result[offset] = raw_text
    return result


def apply_text_map(source: str, text_map: dict[int, str]) -> tuple[str, int]:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    line_starts: list[int] = []
    total = 0
    for line in lines:
        line_starts.append(total)
        total += len(line)

    replacements: list[tuple[int, int, str]] = []
    found: set[int] = set()
    changed = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "p":
            continue
        if len(node.args) < 2:
            continue
        offset_node, text_node = node.args[:2]
        if (
            not isinstance(offset_node, ast.Constant)
            or not isinstance(offset_node.value, int)
            or offset_node.value not in text_map
        ):
            continue
        offset = offset_node.value
        if not isinstance(text_node, ast.Constant):
            raise ValueError(
                f"0x{offset:06X}: non-constant text argument"
            )
        if not isinstance(text_node.value, str):
            raise ValueError(f"0x{offset:06X}: text is not a string")
        found.add(offset)
        new_text = text_map[offset]
        if new_text == text_node.value:
            continue
        start = _absolute_character_offset(
            lines,
            line_starts,
            text_node.lineno,
            text_node.col_offset,
        )
        end = _absolute_character_offset(
            lines,
            line_starts,
            text_node.end_lineno,
            text_node.end_col_offset,
        )
        pages = tuple(new_text.splitlines())
        replacement = (
            _string_expression(pages, text_node.col_offset)
            if len(pages) > 1
            else json.dumps(new_text, ensure_ascii=False)
        )
        replacements.append((start, end, replacement))
        changed += 1

    missing = sorted(set(text_map) - found)
    if missing:
        raise ValueError(
            "offset(s) missing from script.py : "
            + ", ".join(f"0x{offset:06X}" for offset in missing)
        )
    for start, end, replacement in sorted(replacements, reverse=True):
        source = source[:start] + replacement + source[end:]
    ast.parse(source)
    return source, changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, default=ROM_DIR / "script.py")
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    text_map = load_text_map(args.map)
    source = args.script.read_text(encoding="utf-8")
    updated, changed = apply_text_map(source, text_map)
    print(f"Declared offsets : {len(text_map)}")
    print(f"Offsets to modify : {changed}")
    if changed and not args.apply:
        return 1
    if changed:
        args.script.write_text(updated, encoding="utf-8")
        print(f"Script updated : {args.script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
