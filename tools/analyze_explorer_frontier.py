"""Rank unexplored frontier nodes that are likely to contain a map exit."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("frontier", type=Path)
    parser.add_argument("--write-profile", type=Path)
    parser.add_argument("--route-offset", type=int, default=2)
    parser.add_argument("--direction-seed", type=int, default=0)
    parser.add_argument("--menu-button", type=lambda value: int(value, 0), default=0x02)
    parser.add_argument("--menu-period", type=int, default=30)
    parser.add_argument("--menu-hold", type=int, default=6)
    parser.add_argument("--max-frames", type=int, default=30000)
    parser.add_argument("--max-budget", type=int, default=60000)
    parser.add_argument("--stop-on-interior", action="store_true")
    parser.add_argument("--stop-on-menu-timeout", action="store_true")
    parser.add_argument("--stop-on-battle", action="store_true")
    parser.add_argument("--battle-alternate-button", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--battle-button", type=lambda value: int(value, 0), default=0x01)
    parser.add_argument("--battle-period", type=int, default=45)
    parser.add_argument("--battle-hold", type=int, default=8)
    parser.add_argument("--capture-all-transitions", action="store_true")
    parser.add_argument("--trace-pc", action="store_true")
    parser.add_argument("--checkpoint-period", type=int, default=600)
    parser.add_argument("--exclude-node", action="append", default=[])
    args = parser.parse_args()
    with args.frontier.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    ranked = []
    for row in rows:
        if row.get("node", "") in set(args.exclude_node):
            continue
        node_value = row.get("node", "")
        remaining_value = row.get("remaining", "")
        parts = node_value.split(":")
        if len(parts) < 3:
            raise SystemExit("frontier invalid node")
        try:
            x, y = int(parts[-2], 16), int(parts[-1], 16)
        except ValueError as exc:
            raise SystemExit("frontier invalid coordinates") from exc
        if not 0 <= x <= 0xFF or not 0 <= y <= 0xFF:
            raise SystemExit("frontier coordinates out of range")
        try:
            map_hash = int(parts[0], 16)
        except ValueError as exc:
            raise SystemExit("frontier invalid map hash") from exc
        if not 0 <= map_hash <= 0xFFFFFFFF:
            raise SystemExit("frontier map hash out of range")
        remaining = [item for item in remaining_value.split(",") if item]
        if any(item not in {"up", "right", "down", "left"} for item in remaining):
            raise SystemExit("frontier invalid direction")
        if not remaining:
            continue
        edge = min(x, y, 0xFF - x, 0xFF - y)
        ranked.append((edge, row["node"], ",".join(remaining)))
    ranked.sort()
    print("node\tremaining\tedge_distance")
    for edge, node, remaining in ranked:
        print(f"{node}\t{remaining}\t{edge}")
    if not ranked:
        return 2
    if args.write_profile and ranked:
        _, node, remaining = ranked[0]
        parts = node.split(":")
        first_direction = remaining.split(",")[0]
        try:
            direction = {"up": 1, "right": 2, "down": 3, "left": 4}[first_direction]
        except KeyError as exc:
            raise SystemExit("frontier invalid direction") from exc
        selected_map_hash = int(parts[0], 16)
        args.write_profile.write_text(
            "\n".join([
                "POKEMON_EXPLORER_START_FRAME=4917",
                f"POKEMON_EXPLORER_MAX_FRAMES={max(1, args.max_frames)}",
                f"POKEMON_EXPLORER_MAX_BUDGET={max(max(1, args.max_frames), args.max_budget)}",
                f"POKEMON_EXPLORER_CHECKPOINT_PERIOD={max(0, args.checkpoint_period)}",
                "POKEMON_EXPLORER_MOVE_HOLD_FRAMES=60",
                "POKEMON_EXPLORER_SETTLE_FRAMES=12",
                "POKEMON_EXPLORER_DIRECT_TRANSITION=1",
                "POKEMON_EXPLORER_GUIDE_DOWNSTAIRS=1",
                "POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3",
                "POKEMON_EXPLORER_GUIDE_EXTERIOR=1",
                "POKEMON_EXPLORER_EXTERIOR_SWEEP_HOLD=1200",
                "POKEMON_EXPLORER_EXTERIOR_ACTION_PERIOD=30",
                f"POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET={args.route_offset % 4}",
                f"POKEMON_EXPLORER_DIRECTION_SEED={args.direction_seed}",
                f"POKEMON_EXPLORER_MENU_RECOVERY_BUTTON=0x{args.menu_button:02X}",
                f"POKEMON_EXPLORER_MENU_RECOVERY_PERIOD={max(1, args.menu_period)}",
                f"POKEMON_EXPLORER_MENU_RECOVERY_HOLD={max(0, args.menu_hold)}",
                "POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=0",
                f"POKEMON_EXPLORER_FRONTIER_PROBE_HASH=0x{selected_map_hash:08X}",
                f"POKEMON_EXPLORER_FRONTIER_PROBE_X=0x{int(parts[1], 16):02X}",
                f"POKEMON_EXPLORER_FRONTIER_PROBE_Y=0x{int(parts[2], 16):02X}",
                f"POKEMON_EXPLORER_FRONTIER_PROBE_DIRECTION={direction}",
                "POKEMON_EXPLORER_FRONTIER_PROBE_ANY_POSITION=1",
                "POKEMON_EXPLORER_FRONTIER_PROBE_EXTEND_ON_ACTIVATION=1",
                "POKEMON_EXPLORER_FRONTIER_PROBE_EXTENSION_FRAMES=6000",
                "POKEMON_EXPLORER_FRONTIER_PROBE_BUDGET=1200",
                "POKEMON_EXPLORER_STOP_ON_INTERIOR=1" if args.stop_on_interior else "POKEMON_EXPLORER_STOP_ON_INTERIOR=0",
                "POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1" if args.stop_on_menu_timeout else "POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=0",
                "POKEMON_EXPLORER_STOP_ON_BATTLE=1" if args.stop_on_battle else "POKEMON_EXPLORER_STOP_ON_BATTLE=0",
                f"POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON=0x{max(0, min(0xFF, args.battle_alternate_button)):02X}",
                f"POKEMON_EXPLORER_BATTLE_ACTION_BUTTON=0x{max(0, min(0xFF, args.battle_button)):02X}",
                f"POKEMON_EXPLORER_BATTLE_ACTION_PERIOD={max(1, args.battle_period)}",
                f"POKEMON_EXPLORER_BATTLE_ACTION_HOLD={max(0, args.battle_hold)}",
                "POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS=1" if args.capture_all_transitions else "POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS=0",
                "POKEMON_EXPLORER_TRACE_PC=1" if args.trace_pc else "POKEMON_EXPLORER_TRACE_PC=0",
                "POKEMON_EXPLORER_FRONTIER_PROBE_ALL=1",
                "POKEMON_EXPLORER_GENERIC_ACTION_PERIOD=30",
                "POKEMON_EXPLORER_MOVE_ACTION_SWEEP=1",
                "POKEMON_EXPLORER_MOVE_ACTION_PERIOD=120",
                "POKEMON_EXPLORER_BLOCKED_EDGE_PROBE=1",
                "POKEMON_EXPLORER_RECOVERY_ACTION_SWEEP=1",
                "POKEMON_EXPLORER_RECOVERY_ACTION_PERIOD=90",
                "POKEMON_EXPLORER_MENU_HASH=0xAAD2FACE",
            ]) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
