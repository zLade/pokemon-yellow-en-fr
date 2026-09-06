#!/usr/bin/env python3
"""Merge route-seed reports stored in separate campaign roots."""
from pathlib import Path
import argparse
import csv

parser = argparse.ArgumentParser()
parser.add_argument("roots", nargs="+", type=Path)
args = parser.parse_args()
rows = []
for root in args.roots:
    for summary in sorted(root.glob("seed-*/exploration_summary.tsv")):
        values = {}
        for line in summary.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("\t")
            if key and value:
                values[key] = value
        if values:
            values["root"] = str(root)
            values["seed"] = summary.parent.name.split("-", 1)[-1]
            rows.append(values)
rows.sort(key=lambda row: (
    int(row.get("battles", 0)), int(row.get("map_hashes", 0)),
    int(row.get("captures", 0)), -int(row.get("blocked_edges", 0)),
), reverse=True)
fields = ["root", "seed", "frames", "captures", "map_hashes", "battles",
          "stagnation_resets", "route_offset", "exterior_reached",
          "building_seen", "building_entered", "interior_seen"]
out = Path.cwd() / "route_seed_matrix.tsv"
with out.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t",
                            extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
if rows:
    print(f"recommended_seed={rows[0]['seed']} root={rows[0]['root']}")
    Path.cwd().joinpath("recommended_matrix_profile.txt").write_text(
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
            "POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET=" + rows[0].get("seed", "0"),
            "POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=0",
            "POKEMON_EXPLORER_GENERIC_ACTION_PERIOD=30",
        ]) + "\n",
        encoding="utf-8",
    )
print(f"reports={len(rows)} output={out}")
