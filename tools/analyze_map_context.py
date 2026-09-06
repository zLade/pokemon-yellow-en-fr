#!/usr/bin/env python3
"""Group transition destinations by their context-RAM signature."""
from collections import defaultdict, Counter
from pathlib import Path
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
args = parser.parse_args()

groups = defaultdict(Counter)
for line in args.path.read_text(encoding="utf-8").splitlines()[1:]:
    parts = line.split("\t")
    if len(parts) != 4:
        continue
    _, _, destination, context = parts
    groups[context][destination] += 1

print("context_hash\ttransitions\tdestinations")
for context, destinations in sorted(groups.items(), key=lambda item: -sum(item[1].values())):
    detail = ",".join(f"{dest}:{count}" for dest, count in destinations.most_common())
    print(f"{context}\t{sum(destinations.values())}\t{detail}")
