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
Pour comparer plusieurs racines déjà exécutées en une seule matrice, utiliser
`tools/merge_route_seed_matrix.py <root-0> <root-1> ...`; le fichier
`route_seed_matrix.tsv` est classé automatiquement par combats puis couverture.
`tools/run_frontier_cycle.ps1` écrit `cycle_status.txt=frontier-exhausted`

Pour enchaîner plusieurs explorations sans intervention, utiliser
`tools/run_frontier_campaign.ps1`. Chaque cycle réutilise la frontière du
cycle précédent et écrit `campaign_history.tsv` avec les cartes et combats.
Le lanceur compare aussi le SHA-256 des frontières : si une frontière déjà
vue réapparaît, il écrit `loop-detected` et arrête proprement la campagne.
Chaque cycle peut aussi utiliser un `RouteOffset` différent (0 à 3) pour
tester plusieurs approches de la même frontière.

Pour analyser les transitions enregistrées, utiliser
`tools/analyze_transition_chain.py map_transitions.tsv`. L’outil affiche la
plus longue chaîne connue, les arêtes répétées et peut écrire les candidats
terminaux avec `--write-targets`.
Le profil de la prochaine cible peut être généré directement avec
`tools/make_transition_probe_profile.py map_transitions.tsv next_profile.txt`.
Un hash de transition seul ne confirme pas un intérieur : utiliser
`POKEMON_EXPLORER_INTERIOR_CONFIRM_HASH` uniquement après validation visuelle.
Pour documenter toutes les transitions, activer
`POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS=1`.
La sonde du bâtiment accepte aussi `POKEMON_EXPLORER_BUILDING_APPROACH_FRAMES`
et `POKEMON_EXPLORER_BUILDING_APPROACH_TURN_FRAMES`; avec une direction de
sonde à `3`, elle teste la route bas → droite → haut.
Le bot détecte aussi les oscillations façade/porte et passe automatiquement à
la route suivante après trois répétitions.
Devant `D0922056`, les positions où A est pressé sont enregistrées dans
`building_interaction_candidates.tsv` avec une capture PNG correspondante.
Pour cibler une candidate précise, définir `POKEMON_EXPLORER_BUILDING_TARGET_X`
et `POKEMON_EXPLORER_BUILDING_TARGET_Y` dans le profil.
La chaîne actuellement observée après la façade commence par
`D0922056 -> 8B3DD206 -> 90FF5246 -> 1D8A0316` et mène jusqu’à
`F8DF9DC8`; `F16EB24A` est une salle intérieure confirmée au milieu du graphe.
Le profil `explorer_building_offset1_profile.txt` conserve le balayage long,
plus fiable pour entrer dans une salle ; `explorer_building_route2_profile.txt`
utilise le balayage court pour tester plus finement les cases du dojo.
Quand le hash de la carte Fighting Dojo sera connu, le définir avec
`POKEMON_EXPLORER_DOJO_HASH` activera une route dédiée vers les positions des
dresseurs et du maître.
Un contexte RAM peut aussi être fourni avec
`POKEMON_EXPLORER_DOJO_CONTEXT_HASH` si le hash graphique est partagé.
`tools/analyze_map_context.py` regroupe les transitions par contexte RAM ;
dans le run de référence, `48633617` mène notamment à `F16EB24A`.
Après une campagne alternative, lancer
`python3 tools/analyze_map_context.py <dossier>/map_context.tsv` pour classer
les nouvelles branches par signature RAM.
Pour une trace CPU, utiliser
`python3 tools/analyze_pc_trace.py <dossier>/pc_trace.tsv` afin d’isoler les
adresses rares potentiellement liées au lancement d’un combat.
Une plage d’événement peut ensuite être rejouée avec
`POKEMON_EXPLORER_EVENT_PC_MIN` et `POKEMON_EXPLORER_EVENT_PC_MAX` ; à zéro,
ce mode reste désactivé.
lorsqu’aucune cible ne reste, sans considérer ce cas comme une erreur.
The merger also writes `recommended_profile.txt`, a complete profile that can
be passed directly with `-ProfilePath` to `run_mesen_explorer_profile.ps1`.
Use `-DryRun` to generate and inspect all four configuration files without
launching Mesen; use `-Seed 0` through `-Seed 3` to run one variant only.
The shell wrapper `tools/scan_exterior_building_probes.sh` runs each direction
in an independent PowerShell process when the Windows loop runner is unstable.
`tools/merge_building_probe_reports.py` merges the resulting `direction-*`
folders and prints a recommended direction, prioritizing battles, then map
hashes and captures.
Les profils `explorer_frontier_probe_*.txt` utilisent
`POKEMON_EXPLORER_FRONTIER_PROBE_HASH`, `..._X`, `..._Y` et
`..._DIRECTION` pour sonder une sortie précise issue de
`exploration_frontier.tsv`; les coordonnées et hashes peuvent être écrits en
hexadécimal.

`tools/scan_explorer_checkpoints.ps1` can run a list of candidate start frames
and compare their summaries, which is useful when a reference checkpoint name
does not match the visible map state.

`tools/scan_explorer_profiles.ps1` compares movement-hold profiles and writes
`profile_comparison.tsv` with the same usability classification.
It also writes `recommended_profile.txt` for the usable profile with the
highest moved-edge count.
`profile_comparison.tsv` records additionally the termination reason when a
campaign emits `termination_reason.tsv`, ainsi que la `direction_seed` de
chaque variante.
Le profil recommandé privilégie désormais une terminaison `interior`, puis
`battle`, avant la simple couverture d’arêtes.

`tools/run_mesen_explorer_profile.ps1` accepts that profile file and launches
the explorer with it automatically.

`tools/analyze_explorer_frontier.py` ranks remaining directions by distance to
the screen edge, highlighting likely exit candidates.
Ses options `--direction-seed`, `--menu-button`, `--menu-period` et
`--menu-hold`, `--max-frames` et `--max-budget` sont recopiées dans le profil
généré pour varier l’exploration, la récupération des menus et la durée de
campagne. `--stop-on-interior` active en plus l’arrêt dès qu’une pièce est
confirmée, et `--stop-on-menu-timeout` arrête une sonde sur menu bloqué.
`--stop-on-battle` arrête également la sonde au premier combat détecté.
`--capture-all-transitions` active la capture des écrans de toutes les
transitions rencontrées par la sonde.
`--trace-pc` ajoute également `pc_trace.tsv` pour relier ces transitions au
code CPU exécuté.
`--checkpoint-period` règle la fréquence des sauvegardes intermédiaires
(`600` frames par défaut, `0` pour les désactiver).

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
signatures and logs cannot be reused as English evidence. The current credited
target is `d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4`.

Example invocation:

```powershell
.\tools\run-mesen-english-regression-suite.ps1 `
  -RomPath .\build\full-control-candidate-yellow-title-2.nes `
  -OutputDirectory .\build\emulator-runs\mesen-english-final `
  -ExpectedRomSha256 d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4
```

## Matrix exploration

Pour tester plusieurs itinéraires sans perdre les résultats intermédiaires,
utiliser `tools/run_mesen_explorer_matrix.ps1`. Chaque profil est exécuté dans
son propre sous-dossier et `matrix_summary.tsv` rassemble les compteurs de
transitions, cartes, bâtiments et combats.

```powershell
.\tools\run_mesen_explorer_matrix.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputDirectory ..\mesen\explorer-matrix `
  -ProfilePath .\tools\campaign\explorer_building_offset1_profile.txt, .\tools\campaign\explorer_building_route2_profile.txt
```

Les événements de récupération sont résumés avec :

```powershell
python .\tools\analyze_recovery.py ..\mesen\explorer-run\recovery.tsv
```

Pour classer les profils après une matrice :

```powershell
python .\tools\rank_matrix_summary.py ..\mesen\explorer-matrix\matrix_summary.tsv
```

Les frontières de plusieurs sessions peuvent être fusionnées avant de
générer le prochain profil :

```powershell
python .\tools\merge_explorer_frontiers.py ..\mesen\run-a\exploration_frontier.tsv ..\mesen\run-b\exploration_frontier.tsv --output ..\mesen\merged-frontier.tsv
```

Une campagne ordonnée peut utiliser une liste de profils et s’arrêter au
premier combat :

```powershell
.\tools\run_mesen_explorer_matrix.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputDirectory ..\mesen\dojo-campaign `
  -ProfileListPath .\tools\campaign\recommended_dojo_matrix_profiles.txt `
  -StopOnBattle
```

Pour enchaîner automatiquement les frontières découvertes :

```powershell
.\tools\run_frontier_campaign.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -FrontierPath ..\mesen\target-e90610aa-run\exploration_frontier.tsv `
  -OutputRoot ..\mesen\dojo-frontier-campaign `
  -MaxCycles 8 -InitialRouteOffset 2 -StopOnBattle -StopOnNoGrowth
```

Une campagne interrompue peut reprendre directement depuis son contexte :

```powershell
.\tools\run_frontier_campaign.ps1 `
  -RomPath .\build\restored\en\Pokemon_Yellow_EN_Chinese_Dojo.nes `
  -InputPath .\build\campaign-reference\LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin `
  -OutputRoot ..\mesen\dojo-resume `
  -ContextPath ..\mesen\cycle-01\cycle_context.tsv `
  -StopOnBattle -StopOnNoGrowth -NoGrowthLimit 2
```

La couverture la plus large obtenue vient actuellement de la branche
`E90610AA` (90 cartes), puis de l’offset 2 (97 cartes sur la branche
`A284878C`). Les offsets 1 et 3 sont conservés comme variantes de secours,
mais leurs essais récents ont produit moins de 10 cartes.

The route remains a diagnostic, not a full campaign. Physical mapper-163
hardware is **NOT TESTED**. The inherited uninitialized-RAM condition remains
`inherited_source_engine_quirk_unresolved`; harmlessness is not proven.

La branche intérieure confirmée `152085AA -> D0099A6C -> 9BA474C0` est
explorable avec `explorer_indoor_9ba_interaction_profile.txt`. Elle est
visuellement validée comme une pièce, mais les campagnes actuelles rapportent
`battles=0`; elle sert donc de point de départ pour les prochaines sondes.
Un profil peut définir `POKEMON_EXPLORER_STOP_ON_BATTLE=1` pour écrire les
artefacts et arrêter l’émulateur dès le premier combat détecté.
La matrice active automatiquement ce réglage avec `-StopOnBattle`.
`run_frontier_campaign.ps1` le propage également à chaque cycle Frontier.
Le profil `battle_stop_smoke_profile.txt` force une détection PC contrôlée et
sert de test reproductible : il doit produire exactement un événement dans
`battles.tsv` et une capture `battle_001_*.png`.
Commande correspondante :
`tools/test_explorer_smoke.ps1 -ProfilePath tools/campaign/battle_stop_smoke_profile.txt -ExpectBattle`.

La variante `explorer_coordinate_door_offset0_detour60_profile.txt` est
validée sur la ROM restaurée : elle atteint `152085AA`, puis
`D0099A6C -> 9BA474C0`, avec `building_entered=true` et
`interior_visual_seen=true`.
Le profil `dojo_entry_battle_probe_profile.txt` réutilise cette trajectoire
et confirme l’arrêt sur le hash intérieur avec `battles=1`; les captures de
combat sont écrites sans filtrage visuel.
Commande de reproduction :
`tools/run_mesen_explorer_profile.ps1 -ProfilePath tools/campaign/dojo_entry_battle_probe_profile.txt -TimeoutSeconds 180`.
La cadence du bot de combat est réglable avec
`POKEMON_EXPLORER_BATTLE_ACTION_PERIOD` et
`POKEMON_EXPLORER_BATTLE_ACTION_HOLD`, ainsi que le bouton via
`POKEMON_EXPLORER_BATTLE_ACTION_BUTTON` (`0x01` = A par défaut).
`POKEMON_EXPLORER_BATTLE_MAX_FRAMES` limite aussi la durée d'un mode combat
qui resterait bloqué sur un faux positif (1800 frames par défaut) ; à l'expiration,
le bot écrit `timeout` dans `battles.tsv` puis reprend l'exploration.
Après une expiration ou une sortie de combat, `POKEMON_EXPLORER_BATTLE_COOLDOWN_FRAMES`
(180 par défaut) empêche une ré-entrée immédiate sur le même faux positif.
Pour les campagnes autonomes, `POKEMON_EXPLORER_EXTEND_ON_NEW_MAP=1` ajoute
`POKEMON_EXPLORER_NEW_MAP_EXTENSION_FRAMES` à chaque nouvelle carte, sans
dépasser `POKEMON_EXPLORER_MAX_BUDGET`; les extensions sont consignées dans
`budget_extensions.tsv`.
Le profil prêt à l'emploi `explorer_adaptive_dojo_profile.txt` reprend la
route dojo validée et active cette prolongation bornée jusqu'à 60 000 frames.
Le paramètre `POKEMON_EXPLORER_CHECKPOINT_PERIOD` (600 frames par défaut)
sauvegarde périodiquement `exploration_graph.dot`, `exploration_frontier.tsv`
et l'historique `exploration_checkpoint.tsv`.
Chaque lancement via `run_mesen_explorer_profile.ps1` écrit aussi
`explorer_run_manifest.tsv`, avec les empreintes SHA-256 de la ROM, des
entrées, du script Lua et du profil utilisé.
Le balayage `scan_explorer_profiles.ps1` passe par ce même runner, donc chaque
variante testée reçoit également son manifeste de reproductibilité.
`POKEMON_EXPLORER_DIRECTION_SEED` permet de varier l’ordre initial des
directions entre campagnes (la valeur `0` conserve la route par défaut).
`POKEMON_EXPLORER_MENU_RECOVERY_BUTTON` configure le bouton envoyé lorsqu’un
hash de menu est détecté (`0x02` = B par défaut, `0x08` = Start).
`POKEMON_EXPLORER_MENU_RECOVERY_PERIOD` et `POKEMON_EXPLORER_MENU_RECOVERY_HOLD`
permettent de régler la période et la durée de l’impulsion (30/6 frames par
défaut).
`POKEMON_EXPLORER_MENU_RECOVERY_MAX_FRAMES` borne le temps passé sur un menu
(600 frames par défaut, ou illimité avec `0`).
Lorsqu’une limite est atteinte, `menu_recovery_timeout.tsv` conserve le frame,
le hash du menu et le nombre de tentatives avant la reprise de l’exploration.
Avec `POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1`, la campagne s’arrête plutôt
avec `termination_reason=menu-timeout` après avoir sauvegardé ses artefacts.
Le smoke test accepte `-ExpectMenuTimeout` pour vérifier ce scénario et sa
trace `menu_recovery_timeout.tsv`.
Le profil `menu_timeout_smoke_profile.txt` fournit une configuration prête à
lancer pour ce scénario.
Son paramètre `-TimeoutSeconds` permet d’adapter la durée maximale de chaque
variante (120 secondes par défaut).
`-DirectionSeed` est recopié dans chaque profil du balayage pour tester un
ordre de directions déterministe différent.
`-CaptureAllTransitions` active la capture visuelle de toutes les transitions
pour chaque variante.
`-TracePc` active de même `pc_trace.tsv` dans chaque variante.
`-StopOnBattle` arrête chaque variante au premier combat détecté.
`-StopOnInterior` arrête chaque variante à la première pièce confirmée.
`-StopOnMenuTimeout` arrête chaque variante lorsqu’un menu atteint sa limite.
`-BattleButton`, `-BattleAlternateButton`, `-BattlePeriod` et `-BattleHold`
configurent de la même façon la stratégie de combat injectée dans chaque profil.
Les valeurs hexadécimales des profils (`0x...`) sont interprétées directement
par le parseur Lua ; les hashes et plages PC des profils dojo sont donc actifs.
Le profil `battle_action_smoke_profile.txt` vérifie la cadence et le bouton
de combat avec `tools/test_explorer_smoke.ps1 -ExpectBattle`.
Pour tester l’alternance A/B, utiliser `battle_action_alternate_smoke_profile.txt`
avec `tools/test_explorer_smoke.ps1 -ExpectBattle -ExpectAlternateBattle` ;
le bouton secondaire est enregistré dans `battle_config.tsv`.
Le raccourci `tools/run_alternate_battle_smoke.ps1` exécute directement cette
procédure avec les chemins ROM et input par défaut, tout en conservant les
options `-RomPath`, `-InputPath`, `-OutputDirectory` et `-TimeoutSeconds`.

Pour arrêter une campagne dès qu'une pièce est confirmée, ajouter
`-StopOnInterior` à `run_frontier_campaign.ps1` ; l'événement est enregistré
dans `campaign_history.tsv` sous `interior-detected`.
Un profil direct peut aussi définir `POKEMON_EXPLORER_STOP_ON_INTERIOR=1` :
le script Lua écrit alors le résumé, le graphe et la frontière dès que
`POKEMON_EXPLORER_INTERIOR_CONFIRM_HASH` est confirmé, puis termine Mesen.
Dans ce mode, `interior_stop.tsv` conserve le frame, le hash, les coordonnées
et le PC exacts de l’arrêt.
Les campagnes écrivent également `battle_config.tsv` avec la cadence, le
bouton, le timeout et le refroidissement du bot de combat.
Le smoke test accepte `-ExpectInterior` pour exiger `interior_seen=true` et
`interior_visual_seen=true` dans le résumé, et vérifie également le manifeste
de reproductibilité du lancement.
Avec `-ExpectInterior`, il exige également la trace `interior_stop.tsv` de
l’arrêt exact sur le hash intérieur.
Pour lancer directement la route adaptative dojo :
`tools/run_adaptive_dojo_explorer.ps1` (timeout configurable avec
`-TimeoutSeconds`).
Ce lanceur exige également `termination_reason=interior`, afin de garantir
que la campagne s’est arrêtée sur l’objectif et non sur son budget.
### Guidage coordonné des façades

Le profil `explorer_coordinate_door_locked_profile.txt` utilise une cible
`BUILDING_TARGET_X/Y` et une rangée de contournement `BUILDING_DETOUR_Y`.
`LOCK_ROUTE_OFFSET=1` conserve le même offset pendant une tentative ; après
stagnation, le bot alterne automatiquement les rangées `0x40` et `0xA0`.
Les fichiers `building_probe.tsv` et `route_checkpoints.tsv` conservent les
coordonnées, commandes et rangées utilisées pour chaque essai.

La matrice accepte aussi `-StopOnInterior` pour interrompre automatiquement
les profils suivants dès qu’un profil confirme `interior_seen=true`.
Elle accepte également `-ProfileTimeoutSeconds` (1800 secondes par défaut) :
un profil qui dépasse cette limite est arrêté, inscrit avec
`status=timeout` dans `matrix_summary.tsv`, puis le profil suivant démarre.
Pour une vérification rapide du runner, utiliser
`tools/test_explorer_smoke.ps1` ; son délai est limité à 60 secondes par défaut
et ses artefacts sont vérifiés automatiquement.
La matrice transmet également son `-ProfileTimeoutSeconds` au runner enfant,
afin que les deux niveaux s’arrêtent sur la même échéance.
Pour comparer une réussite historique à un nouveau parcours, utiliser
`python3 tools/compare_explorer_runs.py reference/exploration_summary.tsv candidate/exploration_summary.tsv`.
Le même garde-fou est disponible pour les campagnes Frontier avec
`-ProfileTimeoutSeconds` sur `run_frontier_campaign.ps1`.
Une expiration est inscrite dans `campaign_history.tsv`, puis la campagne
réessaie la même frontière avec l’offset du cycle suivant.
Les campagnes Frontier exposent aussi `-BattleButton`, `-BattleAlternateButton`,
`-BattlePeriod` et `-BattleHold`; ces options sont transmises au profil généré
par chaque cycle.
