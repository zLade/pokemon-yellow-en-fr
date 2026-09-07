#!/usr/bin/env python3
"""Measure and gate the remaining space in the translated text banks.

The allocator deliberately mutates its free-span inventory.  The spans
returned by :func:`compute_plan` are therefore the exact residual capacity
after suffix pooling and all verified restorations have been planned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from tools.rom_builder import (  # noqa: E402
    TRANSLATION_BASE_ROM,
    FreeSpan,
    pair_for_offset,
)
from tools.validate_repacked import (  # noqa: E402
    build_parser as build_validation_parser,
    compute_plan,
)


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PairBudget:
    free_bytes: int
    largest_block: int
    fragment_count: int
    fragmentation_ratio: float
    allocation_count: int


@dataclass(frozen=True)
class BudgetFloor:
    pair: int
    minimum_free_bytes: int
    minimum_largest_block: int


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_pair(
    spans: Iterable[FreeSpan],
    *,
    allocation_count: int,
) -> PairBudget:
    lengths = sorted((span.length for span in spans if span.length > 0))
    total = sum(lengths)
    largest = lengths[-1] if lengths else 0
    fragmentation = 0.0 if total == 0 else 1.0 - (largest / total)
    return PairBudget(
        free_bytes=total,
        largest_block=largest,
        fragment_count=len(lengths),
        fragmentation_ratio=round(fragmentation, 6),
        allocation_count=allocation_count,
    )


def check_floors(
    budgets: dict[int, PairBudget],
    floors: Iterable[BudgetFloor],
) -> list[str]:
    errors: list[str] = []
    for floor in floors:
        budget = budgets.get(
            floor.pair,
            PairBudget(0, 0, 0, 0.0, 0),
        )
        if budget.free_bytes < floor.minimum_free_bytes:
            errors.append(
                f"pair {floor.pair}: {budget.free_bytes} octets libres, "
                f"minimum {floor.minimum_free_bytes}"
            )
        if budget.largest_block < floor.minimum_largest_block:
            errors.append(
                f"pair {floor.pair}: plus grand bloc "
                f"{budget.largest_block}, minimum "
                f"{floor.minimum_largest_block}"
            )
    return errors


def parse_floor(value: str) -> BudgetFloor:
    try:
        raw_pair, raw_total, raw_largest = value.split(":", 2)
        floor = BudgetFloor(
            int(raw_pair),
            int(raw_total),
            int(raw_largest),
        )
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError(
            "format attendu PAIR:OCTETS_LIBRES:PLUS_GRAND_BLOC"
        ) from error
    if min(
        floor.pair,
        floor.minimum_free_bytes,
        floor.minimum_largest_block,
    ) < 0:
        raise argparse.ArgumentTypeError("les valeurs doivent être positives")
    return floor


def resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROM_DIR / path


def portable_path(path: Path) -> str:
    """Prefer a repository-relative path so reports are reproducible."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROM_DIR.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def build_report(args: argparse.Namespace) -> tuple[dict[str, object], list[str]]:
    validation_args = build_validation_parser().parse_args([])
    validation_args.csv = args.csv
    validation_args.input_rom = args.input_rom
    (
        _,
        _,
        _,
        allocations,
        failures,
        free_spans,
        _,
    ) = compute_plan(validation_args)

    allocation_counts: dict[int, int] = {}
    for source_offset in allocations:
        pair = pair_for_offset(source_offset)
        allocation_counts[pair] = allocation_counts.get(pair, 0) + 1

    pairs = {
        pair: summarize_pair(
            free_spans.get(pair, ()),
            allocation_count=allocation_counts.get(pair, 0),
        )
        for pair in sorted(set(free_spans) | set(allocation_counts))
        if pair in (6, 7)
    }
    errors = [
        f"allocation impossible à 0x{offset:06X}: "
        f"{size} octets dans le pair {pair}"
        for offset, size, pair in failures
    ]
    errors.extend(check_floors(pairs, args.floor))

    input_path = resolve_repo_path(args.input_rom)
    csv_path = resolve_repo_path(args.csv)
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "input_rom": {
            "path": portable_path(input_path),
            "sha256": file_sha256(input_path),
        },
        "translation_csv": {
            "path": portable_path(csv_path),
            "sha256": file_sha256(csv_path),
        },
        "planned_allocations": len(allocations),
        "allocation_failures": len(failures),
        "pairs": {
            str(pair): asdict(budget)
            for pair, budget in pairs.items()
        },
        "floors": [asdict(floor) for floor in args.floor],
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
    }
    return report, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Mesure la capacité résiduelle des banques de texte après "
            "l'allocation déterministe."
        )
    )
    parser.add_argument("--csv", default="traduction/catalogue.csv")
    parser.add_argument("--input-rom", default=TRANSLATION_BASE_ROM)
    parser.add_argument(
        "--floor",
        action="append",
        type=parse_floor,
        default=[],
        metavar="PAIR:LIBRE:BLOC",
        help="seuil minimal répétable par pair de banques",
    )
    parser.add_argument("--output", help="écrit aussi le rapport JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report, errors = build_report(args)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
