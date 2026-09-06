#!/usr/bin/env python3
"""Merge independent Mesen building-probe summaries."""
from pathlib import Path
import argparse
import csv

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
args = parser.parse_args()
rows = []
for summary in sorted(args.root.glob("direction-*/exploration_summary.tsv")):
    direction = summary.parent.name.split("-", 1)[-1]
    values = {}
    for line in summary.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("\t")
        values[key] = value
    rows.append({"direction": direction, **values})
rows.sort(key=lambda row: (int(row.get("battles", 0)), row.get("interior_seen") == "true", row.get("building_entered") == "true", int(row.get("map_hashes", 0)), int(row.get("captures", 0))), reverse=True)
out = args.root / "merged_probe_comparison.tsv"
fields = ["direction", "frames", "captures", "map_hashes", "battles", "exterior_reached", "building_seen", "building_entered", "interior_seen", "frontier_exhausted"]
with out.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
if rows:
    print(f"recommended_direction={rows[0]['direction']}")
print(f"reports={len(rows)} output={out}")
