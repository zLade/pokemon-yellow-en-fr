#!/usr/bin/env python3
"""Summarize rare CPU addresses from an explorer pc_trace.tsv."""
from collections import Counter
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
parser.add_argument("--rare", type=int, default=3)
args = parser.parse_args()

rows = []
for line in args.path.read_text(encoding="utf-8").splitlines()[1:]:
    parts = line.split("\t")
    if len(parts) != 3:
        continue
    try:
        rows.append((int(parts[0]), int(parts[1], 16), parts[2]))
    except ValueError:
        continue

counts = Counter(pc for _, pc, _ in rows)
print("pc\tcount\tfirst_frame\tlast_frame")
for pc, count in sorted(counts.items(), key=lambda item: (item[1], item[0])):
    if count <= args.rare:
        frames = [frame for frame, value, _ in rows if value == pc]
        print(f"{pc:04X}\t{count}\t{min(frames)}\t{max(frames)}")
