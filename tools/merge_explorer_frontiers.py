#!/usr/bin/env python3
"""Merge frontier TSV files from independent explorer sessions."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    merged: dict[str, set[str]] = {}
    for path in args.frontier:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                node = row.get("node", "")
                if not node:
                    continue
                remaining = {d for d in row.get("remaining", "").split(",") if d}
                merged.setdefault(node, set()).update(remaining)
    rows = [(node, sorted(directions)) for node, directions in merged.items() if directions]
    rows.sort(key=lambda item: item[0])
    out = args.output.open("w", encoding="utf-8", newline="") if args.output else None
    stream = out or __import__("sys").stdout
    try:
        stream.write("node\tremaining\n")
        for node, directions in rows:
            stream.write(f"{node}\t{','.join(directions)}\n")
    finally:
        if out:
            out.close()
    print(f"merged_nodes\t{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
