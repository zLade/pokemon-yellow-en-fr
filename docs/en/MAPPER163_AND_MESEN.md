# Mapper 163 and Mesen validation

## Static cartridge contract

The target is a 2,097,168-byte iNES image with:

- mapper 163;
- 2 MiB PRG;
- CHR-ROM size zero and 8 KiB CHR-RAM behavior;
- vertical mirroring and battery-backed SRAM;
- text pointers constrained to their 32 KiB PRG pair;
- protected bank tails, pointer tables and graphical text records.

Validate the credited English target with:

```sh
python3 tools/validate_mapper163.py \
  --rom build/full-control-candidate-yellow-title-2.nes \
  --base-rom 'Pokemon Yellow English 9-23-2015.nes' \
  --profile en-US \
  --title-logo yellow-version \
  --title-reference-rom yellow.nes \
  --title-credits 'LUIGA2009, ZLADE, CHPEXO' \
  --title-credits-mode shared
```

The credited target passed this static validator with changes confined to PRG
pairs 6/7 and the approved title area in bank 14; the original English font in
bank 15 remained unchanged.

## Mesen suite

Use the English-specific wrapper rather than the historical French runner:

```powershell
.\tools\run-mesen-english-regression-suite.ps1 `
  -RomPath .\build\full-control-candidate-yellow-title-2.nes `
  -OutputDirectory .\build\emulator-runs\mesen-english-final `
  -ExpectedRomSha256 d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4
```

The suite binds every log to the candidate SHA and tests Dendy, NTSC and PAL
profiles with strict hardware and full debugging. It includes mapper boot and
runtime probes, English intro/charset/menu probes, the true Yellow title and
credits, Route 1 alignment, battery persistence, and assisted restored-text
samples from both text PRG pairs.

The title-specific Mesen probe passed on the credited target and observed
`YELLOW VERSION`, `NEW/LOAD`, and `LUIGA2009_ZLADE_CHPEXO`.

## Exact limitations

- Mesen coverage is not a complete human playthrough.
- Assisted restoration sampling is not natural traversal of every restored
  dialogue branch.
- The inherited uninitialized-RAM condition remains unresolved.
- Harmlessness of that inherited condition is not proven.
- Physical mapper-163 cartridge/console validation is **NOT TESTED**.
