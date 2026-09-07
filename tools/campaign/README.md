# Mesen campaign framework

This directory contains reusable Mesen modules for controller-driven runtime
testing. It is a test framework, not proof of a complete playthrough.

## Modules

- `engine.lua`: bounded state machine; every step defines entry, success,
  timeout and recovery behavior.
- `input_queue.lua`: controller input queue with neutral frames between
  actions and immediate button release on abort.
- `memory_guard.lua`: controller-only mode with no game-memory writes, plus an
  explicitly assisted mode restricted to a whitelist and TSV audit log.
- `ram_map.lua`: only RAM offsets established by targeted probes.
- `species_plan.lua`: configurable plans for the 151 standard species or the
  159 species-name slots present in this ROM.
- `mesen_campaign_prototype.lua`: historical early-game route used by the
  French non-regression suite.
- `mesen_campaign_explorer.lua`: controller-only frontier explorer (in the
  parent `tools` directory). It
  replays the opening stream, then records stable screen/coordinate signatures
  and screenshots while performing a bounded depth-first exploration. It keeps
  an edge log with blocked/moved outcomes and is intended
  to supply evidence for extending the route toward the dojo, not to claim a
  complete campaign.

Example explorer invocation:

```powershell
.\tools\run-mesen-pokemon-scenario.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -ScriptPath .\tools\mesen_campaign_explorer.lua `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputDirectory .\build\emulator-runs\campaign-explorer
```

The explorer's raw-input bootstrap is intentionally diagnostic: on the
restored English ROM it currently reaches the bedroom/house map, not a proven
laboratory exit.  The FM3 early-campaign trace remains the authoritative
state-driven bootstrap for the lab and first battle; route exploration must
not claim Route 1 coverage until that bootstrap is connected.

Checkpoint experiments can set `POKEMON_EXPLORER_START_FRAME` and
`POKEMON_EXPLORER_MAX_FRAMES`; defaults are 4917 and 18000. The 4917
checkpoint is the currently verified post-rival state with the richest
autonomous exploration.

The same config file may override `POKEMON_EXPLORER_MOVE_HOLD_FRAMES` and
`POKEMON_EXPLORER_SETTLE_FRAMES` when tuning collision and door approaches.
The default hold is 60 frames, selected from the profile comparison for the
highest observed movement coverage.
`POKEMON_EXPLORER_EDGE_HOLD_FRAMES` controls longer pushes toward exits; a
180-frame edge profile has now produced the second stable map hash
`CFF1898C` (`downstairs_candidate`) in runtime testing.
The corresponding capture shows the downstairs room with the stairs and
front-door exit visible; this is the first verified map transition found by
the autonomous explorer.
Route 3 (`POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3`) has now crossed the exterior
door as well: capture 078 shows the outdoor house map, with transition
`CFF1898C → C3601464` at frame 9976.
`POKEMON_EXPLORER_GUIDE_HOUSE_EXIT=1` enables the optional coordinate-guided
alignment from the bedroom spawn toward the right-side stair/exit corridor
before falling back to DFS. The guide is opt-in because collision timing still
needs runtime confirmation on each restored language build.
`POKEMON_EXPLORER_DIRECT_TRANSITION=1` uses the observed bedroom alignment
(`x≈C0,y≈70`, then left) to reproduce the first verified map transition before
returning control to the explorer.
`POKEMON_EXPLORER_DIRECT_TRANSITION_BUDGET` limits this alignment phase (900 by
default; longer budgets are experimental because they can miss the door).
`POKEMON_EXPLORER_TRANSITION_SEED=1` enables a targeted left-push retry near
the observed `x=C0,y=60` transition position.
`POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=1..3` selects one of the bounded exit
search patterns used after entering the downstairs map.
`POKEMON_EXPLORER_GUIDE_EXTERIOR=1` enables a long outdoor sweep after the
first exterior transition, alternating vertical and horizontal searches before
returning to DFS.
`POKEMON_EXPLORER_EXTERIOR_SWEEP_HOLD` controls the duration of each outdoor
direction segment (600 by default; 1200 was tested for the scrolling map).
`POKEMON_EXPLORER_EXTERIOR_ACTION_PERIOD` controls how often the bot presses A
while sweeping outdoor buildings (120 by default; 30 was tested).
`POKEMON_EXPLORER_EXTERIOR_ROUTE_OFFSET` selects a starting sweep variant
(0..3). When the explorer detects prolonged stagnation outdoors, it advances
this offset automatically and restarts the sweep.
`POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=1` enables a targeted approach to the
building view discovered at hash `143B5DCC`.
`POKEMON_EXPLORER_BUILDING_PROBE_DIRECTION=1..4` selects right, left, down, or
up for that approach (left was tested in addition to the default right).
Value `0` cycles through all four directions as a bounded grid probe.
`POKEMON_EXPLORER_BUILDING_PROBE_BUDGET` extends the targeted approach window
(300 by default; the recommended profile uses 900).
Once `exterior_reached=true`, an empty local frontier is now treated as a
camera/scroll boundary and the explorer rotates its seed direction instead of
stopping the whole campaign.

Explorer output files are:

- `exploration.tsv`: stable position captures and RAM context;
- `exploration_edges.tsv`: DFS edges with moved/blocked outcomes;
- `map_transitions.tsv`: detected nametable-hash changes;
- `battles.tsv`: combat entry/exit events;
- `battle_###_<frame>.png`: rendered screenshot captured at each newly
  detected combat entry;
`POKEMON_EXPLORER_BATTLE_PC_MIN` and `POKEMON_EXPLORER_BATTLE_PC_MAX` can
override the CPU address interval used by the combat detector; decimal and
`0x` hexadecimal values are accepted.
- `exploration_summary.tsv`: periodic coverage counters.
- `building_seen` in `exploration_summary.tsv`: whether the targeted outdoor
  building view (`143B5DCC`) was observed during the run.
- `building_entered`: whether the verified transition to `68EAC002` occurred.
- `interior_seen`: whether the interior hash remained stable for the configured
  settle window; transient door-animation hashes do not count.
- `interior_visual_seen`: reserved for a confirmed rendered interior capture;
  it remains false until the delayed screenshot is visibly distinct.
After entry, the controller holds position on `68EAC002` for 900 frames with
periodic A presses before returning to exploration, preventing an immediate
door re-exit.
`POKEMON_EXPLORER_INTERIOR_HOLD_BUDGET` controls this wait (the recommended
profile uses 1800 frames).
After that hold, `POKEMON_EXPLORER_INTERIOR_SWEEP_SEGMENT` controls four
directional interior probes (360 frames per direction in the profile).
`POKEMON_EXPLORER_INTERIOR_DOOR_PROBE=1` replaces the hold with a systematic
probe: A alone, then right/down/left/up with periodic A presses. In the latest
run it exposed the additional transient hash `4091785A` before returning to the
facade, confirming that the first transition is still a door/transition state,
not yet a confirmed dojo room.
- `exploration_graph.dot`: Graphviz view of moved and blocked edges;
- `exploration_frontier.tsv`: directions already tried and remaining per node.

`explorer_exterior_profile.txt` contains the tested controller-only settings
for reproducing the bedroom → downstairs → outdoor sequence.
Use `tools/run_mesen_explorer_profile.ps1` with this profile to reproduce the
run and inspect `exploration_summary.tsv` for `exterior_reached` and
`building_seen`.
Its default exploration budget is 9000 frames after the checkpoint, allowing
the outdoor sweep to revisit late-scrolling building views.
`tools/scan_exterior_building_probes.ps1` runs directions 0–4 and writes a
`probe_comparison.tsv` summary for selecting the most promising building
approach.
Pass `-Direction 0` through `-Direction 4` to run exactly one probe when the
Mesen host is unable to keep a multi-run loop alive.
`tools/scan_exterior_route_seeds.ps1` runs four independent exterior sweep
variants and writes `seed_comparison.tsv`; use
`tools/merge_route_seed_reports.py <output-root>` to rank even partial runs by
combat count, map coverage, and captures.
Use `tools/merge_route_seed_matrix.py <root-0> <root-1> ...` to compare
existing runs in one matrix. `route_seed_matrix.tsv` is ranked by battles,
then coverage. `tools/run_frontier_cycle.ps1` writes
`cycle_status.txt=frontier-exhausted` when no targets remain; this is not an error.

Use `tools/run_frontier_campaign.ps1` for unattended exploration. Each cycle
reuses the preceding frontier and records maps and battles in
`campaign_history.tsv`. Repeated frontier SHA-256 hashes produce
`loop-detected` and a clean stop. Different `RouteOffset` values (0–3) test
alternative approaches to the same frontier.

`tools/analyze_transition_chain.py map_transitions.tsv` reports the longest
known chain and repeated edges; `--write-targets` exports terminal candidates.
Generate the next probe with
`tools/make_transition_probe_profile.py map_transitions.tsv next_profile.txt`.
A transition hash alone is not proof of an interior: set
`POKEMON_EXPLORER_INTERIOR_CONFIRM_HASH` only after visual verification.
Enable `POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS=1` to capture all transitions.

The building probe also accepts `POKEMON_EXPLORER_BUILDING_APPROACH_FRAMES`
and `POKEMON_EXPLORER_BUILDING_APPROACH_TURN_FRAMES`. Probe direction `3`
tests down → right → up. Three repeated facade/door oscillations trigger the
next route. A-button positions at `D0922056` are recorded in
`building_interaction_candidates.tsv`, with matching PNG captures.
Set `POKEMON_EXPLORER_BUILDING_TARGET_X` and
`POKEMON_EXPLORER_BUILDING_TARGET_Y` to probe a specific candidate.

The observed chain begins at `D0922056 -> 8B3DD206 -> 90FF5246 -> 1D8A0316`
and reaches `F8DF9DC8`; `F16EB24A` is a visually confirmed interior within it.
`explorer_building_offset1_profile.txt` retains the long sweep, which is more
reliable for entry; `explorer_building_route2_profile.txt` uses a shorter
sweep to probe dojo tiles more precisely.

Once identified, `POKEMON_EXPLORER_DOJO_HASH` enables the dedicated trainer
and master route. If the visual hash is shared, supply the RAM context with
`POKEMON_EXPLORER_DOJO_CONTEXT_HASH`. `tools/analyze_map_context.py` groups
transitions by RAM context; the reference context `48633617` reaches `F16EB24A`.
Run `python3 tools/analyze_map_context.py <directory>/map_context.tsv` to
classify new branches, or `python3 tools/analyze_pc_trace.py <directory>/pc_trace.tsv`
to locate rare CPU addresses potentially associated with battle entry.
Replay an event range with `POKEMON_EXPLORER_EVENT_PC_MIN` and
`POKEMON_EXPLORER_EVENT_PC_MAX`; zero leaves this mode disabled.
The merger also writes `recommended_profile.txt`, a complete profile that can
be passed directly with `-ProfilePath` to `run_mesen_explorer_profile.ps1`.
Use `-DryRun` to generate and inspect all four configuration files without
launching Mesen; use `-Seed 0` through `-Seed 3` to run one variant only.
The shell wrapper `tools/scan_exterior_building_probes.sh` runs each direction
in an independent PowerShell process when the Windows loop runner is unstable.
`tools/merge_building_probe_reports.py` merges the resulting `direction-*`
folders and prints a recommended direction, prioritizing battles, then map
hashes and captures.
The `explorer_frontier_probe_*.txt` profiles use
`POKEMON_EXPLORER_FRONTIER_PROBE_HASH`, `..._X`, `..._Y` and `..._DIRECTION`
to probe a specific exit from `exploration_frontier.tsv`. Coordinates and
hashes may be hexadecimal.
`tools/scan_explorer_checkpoints.ps1` can run a list of candidate start frames
and compare their summaries, which is useful when a reference checkpoint name
does not match the visible map state.

`tools/scan_explorer_profiles.ps1` compares movement-hold profiles and writes
`profile_comparison.tsv` with the same usability classification.
It also writes `recommended_profile.txt` for the usable profile with the
highest moved-edge count.
`profile_comparison.tsv` records additionally the termination reason when a
campaign emits `termination_reason.tsv`, along with each variant's
`direction_seed`. Recommendations prioritize `interior` termination, then
`battle`, before edge coverage alone.
`tools/run_mesen_explorer_profile.ps1` accepts that profile file and launches
the explorer with it automatically.

`tools/analyze_explorer_frontier.py` ranks remaining directions by distance to
the screen edge, highlighting likely exit candidates.
The options `--direction-seed`, `--menu-button`, `--menu-period`,
`--menu-hold`, `--max-frames` and `--max-budget` are copied into the generated
profile to vary exploration, menu recovery and the run budget.
`--stop-on-interior` stops on a confirmed room; `--stop-on-menu-timeout`
stops on a stuck menu, and `--stop-on-battle` stops on the first detected battle.
`--capture-all-transitions` captures every transition and `--trace-pc` adds
`pc_trace.tsv` to connect transitions to CPU execution.
`--checkpoint-period` controls intermediate saves (600 frames by default;
zero disables them).
```powershell
.\tools\run_mesen_explorer_profile.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputDirectory ..\mesen\explorer-run `
  -ProfilePath ..\mesen\explorer-profiles\recommended_profile.txt
```

Example profile scan:

```powershell
.\tools\scan_explorer_profiles.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin
```

## English runtime coverage

The English branch uses dedicated probes and the wrapper
`tools/run-mesen-english-regression-suite.ps1`. It covers boot/runtime mapper
behavior, introduction prompts, the English charset, the `YELLOW VERSION`
title and credits, the English player menu, Route 1 alignment, battery
persistence, and assisted samples from both restored-dialogue PRG pairs.

All runtime evidence must be tied to the exact candidate SHA. Archived French
signatures and logs cannot be reused as English evidence. The historical credited
target used by this example is `d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4`.

Example invocation:

```powershell
.\tools\run-mesen-english-regression-suite.ps1 `
  -RomPath .\build\full-control-candidate-yellow-title-2.nes `
  -OutputDirectory .\build\emulator-runs\mesen-english-final `
  -ExpectedRomSha256 d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4
```

## Matrix exploration

Use `tools/run_mesen_explorer_matrix.ps1` to test multiple routes while
retaining intermediate results. Each profile has its own output directory;
`matrix_summary.tsv` collects transition, map, building and battle counts.
```powershell
.\tools\run_mesen_explorer_matrix.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputDirectory ..\mesen\explorer-matrix `
  -ProfilePath .\tools\campaign\explorer_building_offset1_profile.txt, .\tools\campaign\explorer_building_route2_profile.txt
```

Summarize recovery events with:

```powershell
python .\tools\analyze_recovery.py ..\mesen\explorer-run\recovery.tsv
```

Rank profiles after a matrix run with:

```powershell
python .\tools\rank_matrix_summary.py ..\mesen\explorer-matrix\matrix_summary.tsv
```

Frontiers from multiple sessions can be merged before generating the next profile:

```powershell
python .\tools\merge_explorer_frontiers.py ..\mesen\run-a\exploration_frontier.tsv ..\mesen\run-b\exploration_frontier.tsv --output ..\mesen\merged-frontier.tsv
```

An ordered campaign can use a profile list and stop at the first battle:
```powershell
.\tools\run_mesen_explorer_matrix.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputDirectory ..\mesen\dojo-campaign `
  -ProfileListPath .\tools\campaign\recommended_dojo_matrix_profiles.txt `
  -StopOnBattle
```

To chain newly discovered frontiers automatically:
```powershell
.\tools\run_frontier_campaign.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -FrontierPath ..\mesen\target-e90610aa-run\exploration_frontier.tsv `
  -OutputRoot ..\mesen\dojo-frontier-campaign `
  -MaxCycles 8 -InitialRouteOffset 2 -StopOnBattle -StopOnNoGrowth
```

To resume an interrupted campaign from its recorded context:
```powershell
.\tools\run_frontier_campaign.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputRoot ..\mesen\dojo-resume `
  -ContextPath ..\mesen\cycle-01\cycle_context.tsv `
  -StopOnBattle -StopOnNoGrowth -NoGrowthLimit 2
```

The broadest recorded coverage comes from branch `E90610AA` (90 maps),
followed by offset 2 (97 maps on branch `A284878C`). Offsets 1 and 3 remain
fallback variants, but their recent runs covered fewer than ten maps.
The route remains a diagnostic, not a full campaign. Physical mapper-163
hardware is **NOT TESTED**. The inherited uninitialized-RAM condition remains
`inherited_source_engine_quirk_unresolved`; harmlessness is not proven.

The confirmed interior chain `152085AA -> D0099A6C -> 9BA474C0` can be
explored with `explorer_indoor_9ba_interaction_profile.txt`. It is visually
confirmed as a room, but the recorded campaigns report `battles=0`.

## Stop conditions and battle controls

`POKEMON_EXPLORER_STOP_ON_BATTLE=1` saves artifacts and stops Mesen at the
first detected battle. The matrix enables it with `-StopOnBattle`;
`run_frontier_campaign.ps1` propagates it to every cycle.
`battle_stop_smoke_profile.txt` forces a controlled PC-based detection: expect
exactly one event in `battles.tsv` and one `battle_001_*.png` capture.
Run `tools/test_explorer_smoke.ps1 -ProfilePath tools/campaign/battle_stop_smoke_profile.txt -ExpectBattle`.

The tested `explorer_coordinate_door_offset0_detour60_profile.txt` route
reaches `152085AA`, then `D0099A6C -> 9BA474C0`, with
`building_entered=true` and `interior_visual_seen=true`.
`dojo_entry_battle_probe_profile.txt` reuses this route and records a stop on
the interior hash with `battles=1`; battle captures are not visually filtered.
Reproduce it with `tools/run_mesen_explorer_profile.ps1 -ProfilePath tools/campaign/dojo_entry_battle_probe_profile.txt -TimeoutSeconds 180`.

`POKEMON_EXPLORER_BATTLE_ACTION_PERIOD` and
`POKEMON_EXPLORER_BATTLE_ACTION_HOLD` set the battle input timing;
`POKEMON_EXPLORER_BATTLE_ACTION_BUTTON` selects the button (`0x01`, A, by default).
`POKEMON_EXPLORER_BATTLE_MAX_FRAMES` bounds a potentially false battle mode
(1,800 frames by default). On expiry the bot writes `timeout` to `battles.tsv`
and resumes exploration. `POKEMON_EXPLORER_BATTLE_COOLDOWN_FRAMES` defaults
to 180 and prevents immediate re-entry after a battle or timeout.

For unattended runs, `POKEMON_EXPLORER_EXTEND_ON_NEW_MAP=1` adds
`POKEMON_EXPLORER_NEW_MAP_EXTENSION_FRAMES` for each new map, up to
`POKEMON_EXPLORER_MAX_BUDGET`. Extensions appear in `budget_extensions.tsv`.
`explorer_adaptive_dojo_profile.txt` combines the tested dojo route with a
bounded extension up to 60,000 frames.
`POKEMON_EXPLORER_CHECKPOINT_PERIOD` (600 frames by default) periodically
saves `exploration_graph.dot`, `exploration_frontier.tsv` and
`exploration_checkpoint.tsv`.

Every `run_mesen_explorer_profile.ps1` launch writes `explorer_run_manifest.tsv`
with SHA-256 hashes for the ROM, inputs, Lua script and profile.
`scan_explorer_profiles.ps1` uses the same runner, so each variant gets a manifest.
`POKEMON_EXPLORER_DIRECTION_SEED` varies the initial direction order; zero
retains the default route.

## Menu recovery and smoke tests

`POKEMON_EXPLORER_MENU_RECOVERY_BUTTON` selects the recovery button (`0x02`
for B by default, or `0x08` for Start). `POKEMON_EXPLORER_MENU_RECOVERY_PERIOD`
and `POKEMON_EXPLORER_MENU_RECOVERY_HOLD` default to 30 and 6 frames.
`POKEMON_EXPLORER_MENU_RECOVERY_MAX_FRAMES` defaults to 600; zero is unlimited.
When reached, `menu_recovery_timeout.tsv` records the frame, menu hash and
attempt count. With `POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1`, the run saves
its artifacts and stops with `termination_reason=menu-timeout`.
Use `menu_timeout_smoke_profile.txt` and `-ExpectMenuTimeout` to test this path.

The profile scanner accepts `-TimeoutSeconds` (120 seconds by default),
`-DirectionSeed`, `-CaptureAllTransitions`, `-TracePc`, `-StopOnBattle`,
`-StopOnInterior` and `-StopOnMenuTimeout`. Battle settings `-BattleButton`,
`-BattleAlternateButton`, `-BattlePeriod` and `-BattleHold` are copied into
each generated profile. Hexadecimal profile values (`0x...`) are interpreted
directly by the Lua parser, including dojo hashes and PC ranges.

`battle_action_smoke_profile.txt` verifies battle timing and buttons with
`tools/test_explorer_smoke.ps1 -ExpectBattle`. To test alternating A/B input,
use `battle_action_alternate_smoke_profile.txt` with
`tools/test_explorer_smoke.ps1 -ExpectBattle -ExpectAlternateBattle`;
`battle_config.tsv` records the secondary button.
`tools/run_alternate_battle_smoke.ps1` supplies the default ROM/input paths
and also accepts `-RomPath`, `-InputPath`, `-OutputDirectory` and `-TimeoutSeconds`.

## Confirmed interiors and coordinate-guided approaches

`-StopOnInterior` on `run_frontier_campaign.ps1` records `interior-detected`
in `campaign_history.tsv`. A direct profile can set
`POKEMON_EXPLORER_STOP_ON_INTERIOR=1`; once
`POKEMON_EXPLORER_INTERIOR_CONFIRM_HASH` is confirmed, Lua saves the summary,
graph and frontier and stops Mesen. `interior_stop.tsv` records the exact
frame, hash, coordinates and PC. Campaigns also write `battle_config.tsv`
with button timing, timeout and cooldown settings.

The smoke test's `-ExpectInterior` requires `interior_seen=true`,
`interior_visual_seen=true`, the launch manifest and `interior_stop.tsv`.
`tools/run_adaptive_dojo_explorer.ps1` runs the adaptive dojo route; its
`-TimeoutSeconds` is configurable, and it requires `termination_reason=interior`
so that reaching a budget is not mistaken for reaching the destination.

`explorer_coordinate_door_locked_profile.txt` uses `BUILDING_TARGET_X/Y`
and a `BUILDING_DETOUR_Y` bypass row. `LOCK_ROUTE_OFFSET=1` keeps a route
offset for an attempt; after stagnation the bot alternates rows `0x40` and
`0xA0`. `building_probe.tsv` and `route_checkpoints.tsv` retain coordinates,
commands and rows for every attempt.

The matrix accepts `-StopOnInterior` to skip remaining profiles once an
interior is confirmed. `-ProfileTimeoutSeconds` defaults to 1,800 seconds;
an expired profile is stopped and marked `status=timeout` in
`matrix_summary.tsv` before the next starts. The same deadline is passed to
the child runner. `tools/test_explorer_smoke.ps1` provides a quick runner
check, with a 60-second default timeout and automatic artifact checks.
Compare a reference and candidate with
`python3 tools/compare_explorer_runs.py reference/exploration_summary.tsv candidate/exploration_summary.tsv`.

Frontier campaigns also accept `-ProfileTimeoutSeconds`. Expiry is recorded
in `campaign_history.tsv`, then the same frontier is retried with the next
cycle's offset. `-BattleButton`, `-BattleAlternateButton`, `-BattlePeriod` and
`-BattleHold` are passed to each cycle's generated profile.
