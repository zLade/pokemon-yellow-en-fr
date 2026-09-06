#!/usr/bin/env python3
"""Summarize positions tested while probing the dojo entrance."""
from collections import Counter
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
args = parser.parse_args()

rows = []
for line in args.path.read_text(encoding="utf-8").splitlines():
    parts = line.split("\t")
    if len(parts) < 5:
        continue
    try:
        frame, map_hash, x, y, action = parts[:5]
        rows.append((int(frame), map_hash, int(x, 16), int(y, 16), int(action, 16)))
    except ValueError:
        continue

counts = Counter((map_hash, x, y) for _, map_hash, x, y, _ in rows)
print("map_hash\tx\ty\tattempts\tactions")
for (map_hash, x, y), count in counts.most_common():
    actions = sorted({f"{action:02X}" for _, h, px, py, action in rows
                      if (h, px, py) == (map_hash, x, y)})
    print(f"{map_hash}\t{x:02X}\t{y:02X}\t{count}\t{','.join(actions)}")
