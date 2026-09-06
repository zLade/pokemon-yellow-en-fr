#!/usr/bin/env python3
"""Compare two explorer summary TSV files, emphasizing the stopping state."""

from __future__ import annotations

import argparse
from pathlib import Path


def read_summary(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.partition("\t")
        if sep:
            values[key] = value
    return values


def read_termination(summary_path: Path) -> str:
    path = summary_path.parent / "termination_reason.tsv"
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) != 2 or lines[0] != "reason":
        raise ValueError(f"invalid termination trace: {path}")
    if lines[1] not in {"budget", "battle", "interior", "menu-timeout"}:
        raise ValueError(f"invalid termination reason: {lines[1]}")
    return lines[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    reference = read_summary(args.reference)
    candidate = read_summary(args.candidate)
    reference["termination_reason"] = read_termination(args.reference)
    candidate["termination_reason"] = read_termination(args.candidate)
    keys = (
        "frames", "exploration_budget", "termination_reason", "direction_seed", "menu_recovery_timed_out", "menu_recovery_button", "menu_recovery_period", "menu_recovery_hold", "menu_recovery_max_frames", "captures", "moved_edges", "blocked_edges", "recoveries", "stagnation_resets", "map_hashes", "battles", "last_x", "last_y", "last_pc",
        "last_map_hash", "route_offset", "building_entered", "interior_seen",
        "interior_visual_seen",
    )
    print("field\treference\tcandidate\tdifferent")
    for key in keys:
        left = reference.get(key, "")
        right = candidate.get(key, "")
        print(f"{key}\t{left}\t{right}\t{str(left != right).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
