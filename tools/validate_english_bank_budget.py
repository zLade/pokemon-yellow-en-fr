#!/usr/bin/env python3
"""Validate the measured English allocator headroom against a pinned policy."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ALLOCATION = (
    ROOT / "build" / "private" / "en" / "2.0.0" /
    "english_text_allocation.csv"
)
DEFAULT_BUDGET = (
    ROOT / "build" / "private" / "en" / "2.0.0" /
    "english_bank_budget.csv"
)
DEFAULT_POLICY = ROOT / "locales" / "en-US" / "bank_budget_policy.json"


class EnglishBankBudgetError(RuntimeError):
    pass


def _integer(row: Mapping[str, str], field: str, label: str) -> int:
    try:
        return int(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise EnglishBankBudgetError(f"{label}: invalid {field}") from exc


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise EnglishBankBudgetError(f"CSV without header: {path}")
        return list(reader.fieldnames), list(reader)


def validate_budget(
    allocation_path: Path,
    budget_path: Path,
    policy_path: Path,
) -> dict[str, object]:
    allocation_fields, allocations = _read_csv(allocation_path)
    budget_fields, budgets = _read_csv(budget_path)
    required_alloc = {
        "record_type",
        "stable_key",
        "source_pair",
        "target_pair",
        "physical_bytes",
        "payload_bytes",
        "pointer_reference_count",
    }
    required_budget = {
        "prg_pair",
        "initial_free_bytes",
        "allocated_physical_bytes",
        "remaining_free_bytes",
        "initial_span_count",
        "remaining_span_count",
        "largest_remaining_span",
    }
    if missing := required_alloc.difference(allocation_fields):
        raise EnglishBankBudgetError(
            f"allocation columns missing: {', '.join(sorted(missing))}"
        )
    if missing := required_budget.difference(budget_fields):
        raise EnglishBankBudgetError(
            f"budget columns missing: {', '.join(sorted(missing))}"
        )
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EnglishBankBudgetError(f"invalid policy JSON: {exc}") from exc
    if policy.get("schema") != "nj046-en2-bank-budget-policy/v1":
        raise EnglishBankBudgetError("unexpected bank budget policy schema")
    policy_pairs = policy.get("pairs")
    if not isinstance(policy_pairs, dict) or set(policy_pairs) != {"6", "7"}:
        raise EnglishBankBudgetError("policy must cover exactly PRG pairs 6 and 7")
    if not str(policy.get("rationale", "")).strip():
        raise EnglishBankBudgetError("policy rationale is required")

    rows_by_pair: dict[int, dict[str, str]] = {}
    for row in budgets:
        pair = _integer(row, "prg_pair", "bank budget")
        if pair in rows_by_pair:
            raise EnglishBankBudgetError(f"duplicate bank budget pair {pair}")
        rows_by_pair[pair] = row
    if not {6, 7}.issubset(rows_by_pair):
        raise EnglishBankBudgetError(
            f"budget must cover PRG pairs 6 and 7: {sorted(rows_by_pair)}"
        )
    for pair, row in rows_by_pair.items():
        if pair in (6, 7):
            continue
        nonzero = {
            field: _integer(row, field, f"pair {pair}")
            for field in required_budget.difference({"prg_pair"})
            if _integer(row, field, f"pair {pair}") != 0
        }
        if nonzero:
            raise EnglishBankBudgetError(
                f"unexpected text budget outside pairs 6/7 at pair {pair}: "
                f"{nonzero}"
            )

    physical_by_pair: Counter[int] = Counter()
    keys: list[str] = []
    logical_counts: Counter[str] = Counter()
    for row in allocations:
        key = row["stable_key"].strip()
        if not key:
            raise EnglishBankBudgetError("empty allocation stable key")
        keys.append(key)
        record_type = row["record_type"].strip()
        logical_counts[record_type] += 1
        source_pair = _integer(row, "source_pair", key)
        target_pair = _integer(row, "target_pair", key)
        if source_pair != target_pair:
            raise EnglishBankBudgetError(
                f"{key}: cross-pair allocation {source_pair}->{target_pair}"
            )
        physical = _integer(row, "physical_bytes", key)
        payload = _integer(row, "payload_bytes", key)
        references = _integer(row, "pointer_reference_count", key)
        if physical < 0 or payload < 1 or references < 1:
            raise EnglishBankBudgetError(f"{key}: invalid allocation measures")
        physical_by_pair[target_pair] += physical
    if len(keys) != len(set(keys)):
        raise EnglishBankBudgetError("duplicate allocation stable keys")

    measured: dict[str, dict[str, int]] = {}
    for pair in (6, 7):
        row = rows_by_pair[pair]
        initial = _integer(row, "initial_free_bytes", f"pair {pair}")
        allocated = _integer(row, "allocated_physical_bytes", f"pair {pair}")
        remaining = _integer(row, "remaining_free_bytes", f"pair {pair}")
        largest = _integer(row, "largest_remaining_span", f"pair {pair}")
        remaining_spans = _integer(row, "remaining_span_count", f"pair {pair}")
        if initial != allocated + remaining:
            raise EnglishBankBudgetError(
                f"pair {pair}: {initial} != {allocated} + {remaining}"
            )
        if allocated != physical_by_pair[pair]:
            raise EnglishBankBudgetError(
                f"pair {pair}: allocation report charges {physical_by_pair[pair]}, "
                f"budget charges {allocated}"
            )
        limits = policy_pairs[str(pair)]
        if not isinstance(limits, dict):
            raise EnglishBankBudgetError(f"pair {pair}: invalid policy entry")
        minimum_free = int(limits.get("minimum_remaining_free_bytes", -1))
        minimum_largest = int(limits.get("minimum_largest_remaining_span", -1))
        if minimum_free < 32 or minimum_largest < 1:
            raise EnglishBankBudgetError(
                f"pair {pair}: policy floor is not meaningful"
            )
        if remaining < minimum_free:
            raise EnglishBankBudgetError(
                f"pair {pair}: remaining {remaining} below floor {minimum_free}"
            )
        if largest < minimum_largest:
            raise EnglishBankBudgetError(
                f"pair {pair}: largest span {largest} below floor {minimum_largest}"
            )
        if remaining_spans < 1:
            raise EnglishBankBudgetError(f"pair {pair}: no remaining span")
        measured[str(pair)] = {
            "initial_free_bytes": initial,
            "allocated_physical_bytes": allocated,
            "remaining_free_bytes": remaining,
            "largest_remaining_span": largest,
            "minimum_remaining_free_bytes": minimum_free,
            "minimum_largest_remaining_span": minimum_largest,
        }

    return {
        "schema": "nj046-en2-bank-budget-validation/v1",
        "result": "PASS",
        "logical_allocations": len(allocations),
        "logical_types": dict(sorted(logical_counts.items())),
        "pairs": measured,
        "policy_rationale": policy["rationale"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allocation", type=Path, default=DEFAULT_ALLOCATION)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = validate_budget(
            args.allocation.resolve(),
            args.budget.resolve(),
            args.policy.resolve(),
        )
    except (EnglishBankBudgetError, OSError, csv.Error, ValueError) as exc:
        print(f"English bank budget: FAIL\n{exc}")
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
