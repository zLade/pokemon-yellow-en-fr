#!/usr/bin/env python3
"""Summarize stagnation-recovery events emitted by the campaign explorer."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("recovery", type=Path)
    args = parser.parse_args()
    counts = Counter()
    total = 0
    with args.recovery.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            if not row.get("frame"):
                continue
            total += 1
            counts[(row.get("map_hash", ""), row.get("start_direction", ""))] += 1
    print(f"recoveries\t{total}")
    print("map_hash\tstart_direction\tcount")
    for (map_hash, direction), count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{map_hash}\t{direction}\t{count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
