"""Create a frontier-probe profile for the last destination in a transition log."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("transitions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with args.transitions.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.reader(handle, delimiter="\t") if len(row) >= 5]
    if not rows:
        raise SystemExit("transition log is empty")
    _, _, target, x, y = rows[-1]
    profile = "\n".join([
        "POKEMON_EXPLORER_START_FRAME=4917",
        "POKEMON_EXPLORER_MAX_FRAMES=30000",
        "POKEMON_EXPLORER_MOVE_HOLD_FRAMES=60",
        "POKEMON_EXPLORER_SETTLE_FRAMES=12",
        "POKEMON_EXPLORER_DIRECT_TRANSITION=1",
        "POKEMON_EXPLORER_GUIDE_DOWNSTAIRS=1",
        "POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3",
        "POKEMON_EXPLORER_GUIDE_EXTERIOR=1",
        "POKEMON_EXPLORER_EXTERIOR_SWEEP_HOLD=1200",
        "POKEMON_EXPLORER_EXTERIOR_ACTION_PERIOD=30",
        "POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET=2",
        f"POKEMON_EXPLORER_FRONTIER_PROBE_HASH=0x{int(target, 16):08X}",
        f"POKEMON_EXPLORER_FRONTIER_PROBE_X=0x{int(x, 16):02X}",
        f"POKEMON_EXPLORER_FRONTIER_PROBE_Y=0x{int(y, 16):02X}",
        "POKEMON_EXPLORER_FRONTIER_PROBE_DIRECTION=1",
        "POKEMON_EXPLORER_FRONTIER_PROBE_BUDGET=1200",
        "POKEMON_EXPLORER_FRONTIER_PROBE_ALL=1",
        "POKEMON_EXPLORER_GENERIC_ACTION_PERIOD=30",
    ]) + "\n"
    args.output.write_text(profile, encoding="utf-8")
    print(f"target={target} x={x} y={y} profile={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
