#!/usr/bin/env python3
"""Select and author ROM-budgeted dialogue page improvements.

The page-quality audit exposes plans which remove strong grammatical
boundaries but need a longer final page.  This tool chooses the best plans
within explicit per-PRG-pair byte budgets, records the decision as JSON, and
optionally turns those selected plans into authoritative ``\n`` page breaks
inside ``script.py``.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import parse_patch_entries  # noqa: E402
from tools.dialogue_layout import (  # noqa: E402
    DIALOGUE_LAYOUT,
    semantic_units,
)
from tools.french_font import encode_game_text  # noqa: E402


@dataclass(frozen=True)
class Candidate:
    offset: int
    prg_pair: int
    byte_cost: int
    strong_gain: int
    source_text: str
    growth_pages: tuple[str, ...]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_candidates(report_path: Path) -> tuple[Candidate, ...]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = report.get("encoded_growth_candidates")
    if not isinstance(rows, list):
        raise ValueError("report missing encoded_growth_candidates")
    candidates: list[Candidate] = []
    for row in rows:
        candidate = Candidate(
            offset=int(str(row["offset_hex"]), 16),
            prg_pair=int(row["prg_pair"]),
            byte_cost=int(row["delta_encoded_bytes"]),
            strong_gain=int(row["strong_gain"]),
            source_text=str(row["source_text"]),
            growth_pages=tuple(str(page) for page in row["growth_pages"]),
        )
        if candidate.prg_pair not in {6, 7}:
            raise ValueError(
                f"0x{candidate.offset:06X}: unexpected PRG pair "
                f"{candidate.prg_pair}"
            )
        if candidate.byte_cost <= 0 or candidate.strong_gain <= 0:
            raise ValueError(
                f"0x{candidate.offset:06X}: candidate without positive gain/cost"
            )
        candidates.append(candidate)
    return tuple(sorted(candidates, key=lambda row: row.offset))


def select_for_budget(
    candidates: Iterable[Candidate],
    budget: int,
) -> tuple[Candidate, ...]:
    """Knapsack: maximise strong issues removed, then minimise bytes."""
    if budget < 0:
        raise ValueError("negative budget")
    rows = tuple(sorted(candidates, key=lambda row: row.offset))
    # used -> (gain, selected indexes)
    states: dict[int, tuple[int, tuple[int, ...]]] = {0: (0, ())}
    for index, row in enumerate(rows):
        previous = tuple(states.items())
        for used, (gain, selected) in previous:
            new_used = used + row.byte_cost
            if new_used > budget:
                continue
            proposed = (gain + row.strong_gain, selected + (index,))
            current = states.get(new_used)
            if current is None:
                states[new_used] = proposed
                continue
            proposed_key = (
                proposed[0],
                -len(proposed[1]),
                tuple(-item for item in proposed[1]),
            )
            current_key = (
                current[0],
                -len(current[1]),
                tuple(-item for item in current[1]),
            )
            if proposed_key > current_key:
                states[new_used] = proposed

    used, (_, selected_indexes) = max(
        states.items(),
        key=lambda item: (
            item[1][0],
            -item[0],
            -len(item[1][1]),
            tuple(-index for index in item[1][1]),
        ),
    )
    selected = tuple(rows[index] for index in selected_indexes)
    if sum(row.byte_cost for row in selected) != used:
        raise AssertionError("inconsistent knapsack cost")
    return selected


def author_pages(candidate: Candidate) -> tuple[str, ...]:
    """Map encoded audit pages back to the exact Unicode source units."""
    units = semantic_units(candidate.source_text)
    encoded_units = tuple(encode_game_text(unit) for unit in units)
    authored: list[str] = []
    unit_index = 0
    for audited_page in candidate.growth_pages:
        target = encode_game_text(audited_page)
        page_units: list[str] = []
        encoded = bytearray()
        while unit_index < len(units):
            separator = b" " if page_units else b""
            proposed = bytes(encoded) + separator + encoded_units[unit_index]
            if not target.startswith(proposed):
                break
            page_units.append(units[unit_index])
            encoded = bytearray(proposed)
            unit_index += 1
            if bytes(encoded) == target:
                break
        if bytes(encoded) != target or not page_units:
            raise ValueError(
                f"0x{candidate.offset:06X}: cannot reconstruct "
                f"page {audited_page!r}"
            )
        authored.append(" ".join(page_units))
    if unit_index != len(units):
        raise ValueError(
            f"0x{candidate.offset:06X}: unconsumed source units"
        )
    return tuple(authored)


def _byte_column_to_character(line: str, byte_column: int) -> int:
    raw = line.encode("utf-8")
    if byte_column > len(raw):
        raise ValueError("AST column outside line")
    return len(raw[:byte_column].decode("utf-8"))


def _absolute_character_offset(
    lines: list[str],
    line_starts: list[int],
    line_number: int,
    byte_column: int,
) -> int:
    line = lines[line_number - 1]
    return (
        line_starts[line_number - 1]
        + _byte_column_to_character(line, byte_column)
    )


def _string_expression(pages: tuple[str, ...], indent: int) -> str:
    child_indent = " " * (indent + 4)
    close_indent = " " * indent
    literals = []
    for index, page in enumerate(pages):
        value = page + ("\n" if index < len(pages) - 1 else "")
        literals.append(
            child_indent
            + json.dumps(value, ensure_ascii=False)
        )
    return "(\n" + "\n".join(literals) + "\n" + close_indent + ")"


def apply_selected_pages(
    script_path: Path,
    selected: Iterable[Candidate],
) -> tuple[str, dict[int, tuple[str, ...]]]:
    source = script_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(script_path))
    by_offset = {row.offset: row for row in selected}
    pages_by_offset = {
        offset: author_pages(row)
        for offset, row in by_offset.items()
    }
    replacements: list[tuple[int, int, str]] = []
    lines = source.splitlines(keepends=True)
    line_starts: list[int] = []
    total = 0
    for line in lines:
        line_starts.append(total)
        total += len(line)

    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "p":
            continue
        if len(node.args) < 2:
            continue
        offset_node, text_node = node.args[:2]
        if not isinstance(offset_node, ast.Constant):
            continue
        if not isinstance(offset_node.value, int):
            continue
        offset = offset_node.value
        if offset not in by_offset:
            continue
        if not isinstance(text_node, ast.Constant):
            raise ValueError(
                f"0x{offset:06X}: non-constant text argument"
            )
        if not isinstance(text_node.value, str):
            raise ValueError(f"0x{offset:06X}: text is not a string")
        if text_node.value != by_offset[offset].source_text:
            raise ValueError(
                f"0x{offset:06X}: source differs from report"
            )
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
        replacements.append(
            (
                start,
                end,
                _string_expression(
                    pages_by_offset[offset],
                    text_node.col_offset,
                ),
            )
        )
        found.add(offset)

    missing = sorted(set(by_offset) - found)
    if missing:
        raise ValueError(
            "selected offset(s) missing: "
            + ", ".join(f"0x{offset:06X}" for offset in missing)
        )
    for start, end, replacement in sorted(replacements, reverse=True):
        source = source[:start] + replacement + source[end:]
    ast.parse(source, filename=str(script_path))
    return source, pages_by_offset


def build_plan(
    report_path: Path,
    script_path: Path,
    budgets: dict[int, int],
) -> tuple[dict[str, object], tuple[Candidate, ...]]:
    candidates = load_candidates(report_path)
    selected: list[Candidate] = []
    pair_reports: dict[str, object] = {}
    for pair in (6, 7):
        pair_candidates = tuple(
            row for row in candidates if row.prg_pair == pair
        )
        chosen = select_for_budget(pair_candidates, budgets[pair])
        selected.extend(chosen)
        pair_reports[str(pair)] = {
            "budget": budgets[pair],
            "candidate_rows": len(pair_candidates),
            "selected_rows": len(chosen),
            "used_bytes": sum(row.byte_cost for row in chosen),
            "strong_gain": sum(row.strong_gain for row in chosen),
        }
    selected_tuple = tuple(sorted(selected, key=lambda row: row.offset))
    script_bytes = script_path.read_bytes()
    report: dict[str, object] = {
        "schema_version": 1,
        "quality_report": str(report_path.resolve()),
        "script": str(script_path.resolve()),
        "script_sha256_before": sha256(script_bytes),
        "pairs": pair_reports,
        "selected_rows": len(selected_tuple),
        "selected_strong_gain": sum(
            row.strong_gain for row in selected_tuple
        ),
        "selected": [
            {
                "offset_hex": f"0x{row.offset:06X}",
                "prg_pair": row.prg_pair,
                "delta_encoded_bytes": row.byte_cost,
                "strong_gain": row.strong_gain,
                "authored_pages": list(author_pages(row)),
            }
            for row in selected_tuple
        ],
    }
    return report, selected_tuple


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--script", default="script.py")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--pair6-budget", type=int, required=True)
    parser.add_argument("--pair7-budget", type=int, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report_path = Path(args.report).resolve()
    script_path = Path(args.script).resolve()
    plan_path = Path(args.plan).resolve()
    plan, selected = build_plan(
        report_path,
        script_path,
        {6: args.pair6_budget, 7: args.pair7_budget},
    )
    if args.apply:
        rewritten, _ = apply_selected_pages(script_path, selected)
        script_path.write_text(rewritten, encoding="utf-8")
        plan["script_sha256_after"] = sha256(
            script_path.read_bytes()
        )
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(script_path)
        }
        for row in selected:
            if "\n" not in entries[row.offset].text:
                raise AssertionError(
                    f"0x{row.offset:06X}: pages not applied"
                )
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Pagination plan : "
        f"{plan['selected_rows']} dialogues, "
        f"{plan['selected_strong_gain']} strong boundaries removed"
    )
    for pair, row in plan["pairs"].items():
        print(
            f"- Pair {pair}: {row['selected_rows']} rows, "
            f"{row['used_bytes']}/{row['budget']} bytes, "
            f"gain {row['strong_gain']}"
        )
    print(f"- Script modified : {args.apply}")
    print(f"- Plan : {plan_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
