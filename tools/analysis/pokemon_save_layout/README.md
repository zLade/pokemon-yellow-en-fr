# NJ046 save-memory layout

This document summarizes fields established by static analysis and targeted
Mesen probes. CPU addresses are NES addresses; `.sav` offsets start at zero in
the 8 KiB battery file.

## Persistent blocks

| Role | CPU address | `.sav` offset | Size |
| --- | ---: | ---: | ---: |
| Active primary state | `$6000-$67FF` | `$0000-$07FF` | 2,048 |
| Copy created by SAVE | `$6C00-$73FF` | `$0C00-$13FF` | 2,048 |
| Save marker | `$7C21-$7C24` | `$1C21-$1C24` | 4 |

The save marker is `AA 55 A5 5A`. Regions `$6800-$6BFF` and `$7400-$7FFF`
also serve as code/graphics/work RAM and must not be treated as ordinary
campaign fields.

No primary-state checksum has been identified. Conservative editing should
update the primary block, copy it to offset `$0C00`, and preserve the marker.
Targeted one-byte corruption tests showed asymmetric recovery, but do not
prove the behavior for truncated files, multiple corruptions, interrupted
writes or physical mapper-163 hardware.

## Standard Pokédex, #001–#151

| Field | CPU | `.sav` offset |
| --- | ---: | ---: |
| Pokédex enabled | `$6000`, bit 5 | `$0000`, mask `20` |
| Seen count | `$6031` | `$0031` |
| Caught count | `$6032` | `$0032` |
| Caught bitmap | `$609F-$60B1` | `$009F-$00B1` |
| Seen bitmap | `$60B3-$60C5` | `$00B3-$00C5` |
| Highest seen number | `$60C8` | `$00C8` |

For species `n` from 1 through 151:

```text
byte = (n - 1) >> 3
mask = 1 << ((n - 1) & 7)
```

Bits are LSB-first. The safe complete bitmap is eighteen `FF` bytes followed
by `7F`; bit 7 of the final byte would represent #152 and must remain clear.
The eight additional species names found in ROM tables are not covered by the
151-entry Pokédex UI proof.

## Party and trainer fields

| Field | CPU | `.sav` offset |
| --- | ---: | ---: |
| Party count | `$6030` | `$0030` |
| Stored species per slot | `$6033 + slot` | `$0033 + slot` |
| Level per slot | `$6039 + slot` | `$0039 + slot` |
| Visible order | `$60C9-$60CE` | `$00C9-$00CE` |
| Badge bitmap | `$60C7` | `$00C7` |
| Money | `$6023-$6025` | `$0023-$0025` |

The party record uses 18 one-byte fields spaced by six slots, ending at
`$6099`. Field meanings beyond those proven above are deliberately unnamed.

## Reproducible tools

- `tools/pokemon_save_layout.py`: decode, validate and synchronize battery
  blocks;
- `tools/test_pokemon_save_layout.py`: synthetic layout tests;
- `tools/mesen_pokedex_ram_probe.lua`: standard Pokédex bitmap checks;
- `tools/mesen_trainer_ram_probe.lua`: trainer profile and badge tracing;
- `tools/run-mesen-battery-persistence.ps1`: save/reload/corruption harness;
- `tools/verify_mesen_battery_corruption.py`: evidence verifier.

The underlying memory layout is language-neutral. Display-string assertions
must use English-specific probes when validating the English branch.
