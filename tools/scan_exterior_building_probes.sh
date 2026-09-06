#!/usr/bin/env bash
set -u
rom="$1"
input="$2"
root="${3:-../mesen/building-probes-shell}"
mkdir -p "$root"
for direction in 0 1 2 3 4; do
  out="$root/direction-$direction"
  mkdir -p "$out"
  {
    printf 'POKEMON_EXPLORER_START_FRAME=4917\n'
    printf 'POKEMON_EXPLORER_MAX_FRAMES=7000\n'
    printf 'POKEMON_EXPLORER_MOVE_HOLD_FRAMES=60\n'
    printf 'POKEMON_EXPLORER_SETTLE_FRAMES=12\n'
    printf 'POKEMON_EXPLORER_EDGE_HOLD_FRAMES=180\n'
    printf 'POKEMON_EXPLORER_DIRECT_TRANSITION=1\n'
    printf 'POKEMON_EXPLORER_GUIDE_DOWNSTAIRS=1\n'
    printf 'POKEMON_EXPLORER_DOWNSTAIRS_ROUTE=3\n'
    printf 'POKEMON_EXPLORER_GUIDE_EXTERIOR=1\n'
    printf 'POKEMON_EXPLORER_EXTERIOR_BUILDING_PROBE=1\n'
    printf 'POKEMON_EXPLORER_BUILDING_PROBE_DIRECTION=%s\n' "$direction"
  } > "$out/explorer_config.txt"
  powershell.exe -NoProfile -File "$(wslpath -w "$(dirname "$0")/run_mesen_explorer_profile.ps1")" \
    -RomPath "$(wslpath -w "$rom")" -InputPath "$(wslpath -w "$input")" \
    -OutputDirectory "$(wslpath -w "$out")" || true
done
printf 'direction\tframes\tcaptures\tmap_hashes\tbattles\texterior_reached\tbuilding_seen\tbuilding_entered\tinterior_seen\n'
for summary in "$root"/direction-*/exploration_summary.tsv; do
  direction="${summary##*/direction-}"; direction="${direction%/*}"
  awk -F '\t' -v d="$direction" 'BEGIN{printf "%s",d} {if ($1=="frames"||$1=="captures"||$1=="map_hashes"||$1=="battles"||$1=="exterior_reached"||$1=="building_seen"||$1=="building_entered"||$1=="interior_seen") printf "\t%s",$2} END{print ""}' "$summary"
done
