#!/usr/bin/env python3
"""Check the minimum evidence emitted by a campaign explorer run."""
from pathlib import Path
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument("output", type=Path)
args = parser.parse_args()
required = ["exploration.tsv", "exploration_edges.tsv", "map_transitions.tsv", "battles.tsv", "exploration_summary.tsv"]
missing = [name for name in required if not (args.output / name).is_file()]
if missing:
    raise SystemExit("missing: " + ", ".join(missing))
values = {}
for line in (args.output / "exploration_summary.tsv").read_text(encoding="utf-8").splitlines():
    key, _, value = line.partition("\t")
    values[key] = value
for key in ("exterior_reached", "building_seen", "building_entered", "interior_seen", "interior_visual_seen", "route_offset", "map_hashes", "battles"):
    if key not in values:
        raise SystemExit(f"summary missing: {key}")
try:
    battle_count = int(values["battles"])
except ValueError:
    raise SystemExit("summary invalid integer: battles")
if battle_count > 0:
    battle_screens = [path for path in args.output.glob("battle_*.png") if path.is_file() and path.stat().st_size > 0]
    if not battle_screens:
        raise SystemExit("battle screenshot missing")
if values["interior_visual_seen"].lower() == "true":
    interior_screen = args.output / "interior_entry_screen.png"
    if not interior_screen.is_file() or interior_screen.stat().st_size == 0:
        raise SystemExit("interior screenshot missing")
for key in ("frontier_probe_activated", "frontier_probe_completed", "menu_recovery_timed_out"):
    if key in values and values[key].lower() not in ("true", "false"):
            raise SystemExit(f"summary invalid boolean: {key}")
if "direction_seed" in values:
    try:
        int(values["direction_seed"])
    except ValueError:
        raise SystemExit("summary invalid integer: direction_seed")
menu_fields = ("menu_recovery_button", "menu_recovery_period", "menu_recovery_hold")
if any(field in values for field in menu_fields):
    if not all(field in values for field in menu_fields):
        raise SystemExit("summary incomplete menu recovery configuration")
    try:
        if not 0 <= int(values["menu_recovery_button"], 16) <= 0xFF:
            raise ValueError
        if int(values["menu_recovery_period"]) < 1 or int(values["menu_recovery_hold"]) < 0:
            raise ValueError
    except ValueError:
        raise SystemExit("summary invalid menu recovery configuration")
if "menu_recoveries" in values:
    try:
        if int(values["menu_recoveries"]) < 0:
            raise ValueError
    except ValueError:
        raise SystemExit("summary invalid integer: menu_recoveries")
context_path = args.output / "cycle_context.tsv"
if context_path.is_file():
    def local_path(raw: str) -> Path:
        value = raw.replace("\\", "/")
        if len(value) >= 3 and value[1:3] == ":/":
            value = "/mnt/" + value[0].lower() + value[2:]
        return Path(value)

    context = {}
    for line in context_path.read_text(encoding="utf-8-sig").splitlines():
        key, _, value = line.partition("\t")
        context[key] = value
    for key in ("route_offset", "profile_template", "frontier"):
        if key not in context or not context[key]:
            raise SystemExit(f"context missing: {key}")
    if context["profile_template"] != "<generated-profile>":
        template = local_path(context["profile_template"])
        if not template.is_file():
            raise SystemExit("context profile template missing: " + context["profile_template"])
    if not local_path(context["frontier"]).is_file():
        raise SystemExit("context frontier missing: " + context["frontier"])
probe = ""
if "frontier_probe_activated" in values:
    probe = f" frontier_probe_activated={values['frontier_probe_activated']} frontier_probe_completed={values['frontier_probe_completed']}"
menu = f" menu_recoveries={values['menu_recoveries']}" if "menu_recoveries" in values else ""
diagnostic = ""
diagnostic_path = args.output / "interior_diagnostics.tsv"
if diagnostic_path.is_file():
    lines = diagnostic_path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "frame\tfrom_hash\tto_hash\tcontext_hash\tx\ty\tpc":
        raise SystemExit("interior_diagnostics invalid header")
    diagnostic = f" interior_diagnostics={max(0, len(lines) - 1)}"
checkpoints = ""
checkpoint_path = args.output / "route_checkpoints.tsv"
if checkpoint_path.is_file():
    lines = checkpoint_path.read_text(encoding="utf-8").splitlines()
    if lines and lines[0] == "frame\tnode\troute_offset\tdirection_cursor\tstagnant_frames\tdetour_y":
        for row in lines[1:]:
            fields = row.split("\t")
            if len(fields) != 6:
                raise SystemExit("route_checkpoints invalid row")
            try:
                detour = int(fields[5], 16)
            except ValueError:
                raise SystemExit("route_checkpoints invalid detour_y")
            if not 0 <= detour <= 0xFF:
                raise SystemExit("route_checkpoints detour_y out of range")
        checkpoints = f" route_checkpoints={max(0, len(lines) - 1)}"
exploration_checkpoints = ""
exploration_checkpoint_path = args.output / "exploration_checkpoint.tsv"
if exploration_checkpoint_path.is_file():
    lines = exploration_checkpoint_path.read_text(encoding="utf-8-sig").splitlines()
    expected = "frame\tcaptures\tmoved_edges\tblocked_edges\tstagnant_frames"
    if not lines or lines[0] != expected:
        raise SystemExit("exploration_checkpoint invalid header")
    for row in lines[1:]:
        fields = row.split("\t")
        if len(fields) != 5:
            raise SystemExit("exploration_checkpoint invalid row")
        try:
            numbers = [int(value) for value in fields]
        except ValueError:
            raise SystemExit("exploration_checkpoint invalid integer")
        if any(value < 0 for value in numbers):
            raise SystemExit("exploration_checkpoint negative value")
    exploration_checkpoints = f" exploration_checkpoints={max(0, len(lines) - 1)}"
manifest = ""
manifest_path = args.output / "explorer_run_manifest.tsv"
if manifest_path.is_file():
    manifest_values = {}
    for line in manifest_path.read_text(encoding="utf-8-sig").splitlines():
        key, _, value = line.partition("\t")
        manifest_values[key] = value
    for key in ("rom_sha256", "input_sha256", "script_sha256", "timeout_seconds"):
        if not manifest_values.get(key):
            raise SystemExit(f"manifest missing: {key}")
    for key in ("rom_sha256", "input_sha256", "script_sha256"):
        if not re.fullmatch(r"[0-9A-Fa-f]{64}", manifest_values[key]):
            raise SystemExit(f"manifest invalid sha256: {key}")
    try:
        if int(manifest_values["timeout_seconds"]) < 5:
            raise ValueError
    except ValueError:
        raise SystemExit("manifest invalid timeout_seconds")
    manifest = " manifest=valid"
interior_stop = ""
interior_stop_path = args.output / "interior_stop.tsv"
if interior_stop_path.is_file():
    lines = interior_stop_path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) != 2 or lines[0] != "frame\thash\tx\ty\tpc":
        raise SystemExit("interior_stop invalid rows")
    fields = lines[1].split("\t")
    if len(fields) != 5:
        raise SystemExit("interior_stop invalid row")
    try:
        int(fields[0]); int(fields[1], 16); int(fields[2], 16); int(fields[3], 16); int(fields[4], 16)
    except ValueError:
        raise SystemExit("interior_stop invalid value")
    interior_stop = " interior_stop=valid"
battle_config = ""
battle_config_path = args.output / "battle_config.tsv"
if battle_config_path.is_file():
    config_values = {}
    for line in battle_config_path.read_text(encoding="utf-8-sig").splitlines():
        key, _, value = line.partition("\t")
        config_values[key] = value
    if set(("field", "period", "hold", "button", "max_frames", "cooldown_frames")) - set(config_values):
        raise SystemExit("battle_config missing field")
    try:
        if int(config_values["period"]) < 1 or int(config_values["hold"]) < 0:
            raise ValueError
        if not 0 <= int(config_values["button"], 16) <= 0xFF:
            raise ValueError
        if "alternate_button" in config_values and not 0 <= int(config_values["alternate_button"], 16) <= 0xFF:
            raise ValueError
        int(config_values["max_frames"]); int(config_values["cooldown_frames"])
    except ValueError:
        raise SystemExit("battle_config invalid value")
    battle_config = " battle_config=valid"
menu_timeout = ""
menu_timeout_path = args.output / "menu_recovery_timeout.tsv"
if menu_timeout_path.is_file():
    lines = menu_timeout_path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) != 2 or lines[0] != "frame\thash\trecoveries":
        raise SystemExit("menu_recovery_timeout invalid rows")
    fields = lines[1].split("\t")
    if len(fields) != 3:
        raise SystemExit("menu_recovery_timeout invalid row")
    try:
        if int(fields[0]) < 0 or int(fields[1], 16) < 0 or int(fields[2]) < 1:
            raise ValueError
    except ValueError:
        raise SystemExit("menu_recovery_timeout invalid value")
    timeout_screen = args.output / "menu_timeout_screen.png"
    if not timeout_screen.is_file() or timeout_screen.stat().st_size == 0:
        raise SystemExit("menu_timeout_screen.png missing")
    menu_timeout = " menu_recovery_timeout=valid"
termination = ""
termination_path = args.output / "termination_reason.tsv"
if termination_path.is_file():
    lines = termination_path.read_text(encoding="utf-8-sig").splitlines()
    if len(lines) != 2 or lines[0] != "reason" or lines[1] not in ("budget", "battle", "interior", "menu-timeout"):
        raise SystemExit("termination_reason invalid value")
    termination = f" termination_reason={lines[1]}"
detour = f" detour_y={values['detour_y']}" if "detour_y" in values else ""
seed = f" direction_seed={values['direction_seed']}" if "direction_seed" in values else ""
menu_timed_out = f" menu_recovery_timed_out={values['menu_recovery_timed_out']}" if "menu_recovery_timed_out" in values else ""
print(f"artifacts-ok exterior_reached={values['exterior_reached']} building_seen={values['building_seen']} building_entered={values['building_entered']} interior_seen={values['interior_seen']} interior_visual_seen={values['interior_visual_seen']} route_offset={values['route_offset']} map_hashes={values['map_hashes']} battles={values['battles']}{probe}{menu}{diagnostic}{checkpoints}{exploration_checkpoints}{manifest}{interior_stop}{battle_config}{menu_timeout}{menu_timed_out}{termination}{seed}{detour}")
