#!/usr/bin/env python3
"""Rank explorer profiles from a matrix_summary.tsv report."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def number(row: dict[str, str], key: str) -> int:
    try:
        return int(row.get(key, "0") or 0)
    except ValueError:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    args = parser.parse_args()
    rows = []
    with args.summary.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            # Reward new maps/transitions and reaching buildings; penalize
            # repeated blocked edges and recovery churn.
            score = (
                8 * number(row, "map_hashes")
                + 3 * number(row, "moved_edges")
                + 20 * (row.get("building_entered", "").lower() == "true")
                + 10 * (row.get("interior_seen", "").lower() == "true")
                - number(row, "blocked_edges")
                - 2 * number(row, "recoveries")
            )
            rows.append((score, row))
    print("score\tprofile\tdetour_y\tinterior_diagnostics\tmaps\tmoved_edges\tblocked_edges\trecoveries\tbattles")
    for score, row in sorted(rows, key=lambda item: (-item[0], row_name(item[1]))):
        print("\t".join(str(value) for value in (
            score, row.get("profile", ""), row.get("detour_y", ""), row.get("interior_diagnostics", "0"), row.get("map_hashes", "0"),
            row.get("moved_edges", "0"), row.get("blocked_edges", "0"),
            row.get("recoveries", "0"), row.get("battles", "0"))))
    return 0


def row_name(row: dict[str, str]) -> str:
    return row.get("profile", "")


if __name__ == "__main__":
    raise SystemExit(main())
