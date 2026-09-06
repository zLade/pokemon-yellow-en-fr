#!/usr/bin/env python3
"""Merge partial or complete route-seed explorer summaries."""
from pathlib import Path
import argparse
import csv

parser = argparse.ArgumentParser()
parser.add_argument("root", type=Path)
args = parser.parse_args()
rows = []
for summary in sorted(args.root.glob("seed-*/exploration_summary.tsv")):
    seed = summary.parent.name.split("-", 1)[-1]
    values = {}
    for line in summary.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("\t")
        if key and value:
            values[key] = value
    if values:
        values["seed"] = seed
        rows.append(values)
rows.sort(key=lambda row: (
    int(row.get("battles", 0)),
    int(row.get("map_hashes", 0)),
    int(row.get("captures", 0)),
), reverse=True)
fields = ["seed", "frames", "captures", "map_hashes", "battles",
          "stagnation_resets", "route_offset",
          "exterior_reached", "building_seen", "building_entered",
          "interior_seen", "frontier_exhausted"]
out = args.root / "merged_seed_comparison.tsv"
with out.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
if rows:
    print(f"recommended_seed={rows[0]['seed']}")
    (args.root / "recommended_profile.txt").write_text(
        "\n".join([
            "POKEMON_EXPLORER_START_FRAME=4917",
            "POKEMON_EXPLORER_MAX_FRAMES=18000",
            "POKEMON_EXPLORER_MOVE_HOLD_FRAMES=60",
            "POKEMON_EXPLORER_SETTLE_FRAMES=12",
            "POKEMON_EXPLORER_DIRECT_TRANSITION=1",
            "POKEMON_EXPLORER_GUIDE_DOWNSTAIRS=1",
            "POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3",
            "POKEMON_EXPLORER_GUIDE_EXTERIOR=1",
            "POKEMON_EXPLORER_EXTERIOR_SWEEP_HOLD=900",
            "POKEMON_EXPLORER_EXTERIOR_ACTION_PERIOD=30",
            "POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET=" + rows[0]["seed"],
            "POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=0",
            "POKEMON_EXPLORER_GENERIC_ACTION_PERIOD=30",
        ]) + "\n",
        encoding="utf-8",
    )
print(f"reports={len(rows)} output={out}")
