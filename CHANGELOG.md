# Changelog

## English Fidelity 2.0.3

- Final IPS applies directly to the original Chinese NJ046 ROM.
- Resulting ROM is byte-identical to 2.0.2.
- Title reconstruction uses the 2015 technical base and a guarded 187-byte delta; no additional intermediate ROM is required.


This file records user-facing changes to the English branch. Complete ROM
images are never distributed.

## Repository tooling — 2026-09-07

- Removed the automated campaign prototype, route replays and dependent runtime checks.
- Retained targeted Mesen diagnostics and static verification of all restored text.
- Made the README the single contributor and build guide.
- Removed redundant navigation pages and unused legacy patch/save utilities.
- Consolidated editable translation inputs under `translation/`.
- Added `python build.py check` and `python build.py build` as the entry points.
- Removed obsolete French inputs, duplicate review exports and superseded tools.
- Kept technical source evidence and validation rules separate from translation text.
- Simplified the contributor guides; the published game version remains 2.0.2.
- Kept headers, editorial annotations, tool messages and documentation in English.
- Added source and ownership regression checks without pinning editable wording.
- Verified that the cleanup reproduces the existing 2.0.2 ROM and IPS exactly.

## English Fidelity 2.0.2 — 2026-08-26

- Added the corrected NES pitch table.
- Preserved every English 2.0.1 localization, graphics and runtime byte outside
  the expected 69-byte musical change set.
- Published a combined IPS patch for the canonical clean the previous intermediate base base.
- Passed the 1,912/1,912 pointer manifest and Mesen 2.2.1 Dendy boot probe.
- Final target SHA-256:
  `703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3`.

## English Fidelity 2.0.1 — 2026-08-24

- Completed the full dialogue, menu, battle-opening and battle-ending review
  in natural English faithful to Pokémon Red/Blue/Yellow terminology.
- Corrected battle and move-learning wording, graphical menu labels and the
  interactive move-forgetting cursor.
- Added two-line rendering for long official move names and checked dynamic
  variants against their window borders.
- Independently certified IPS integrity, mapper 163, all 1,912 expected
  pointers and 101 dynamic-layout scenarios.
- Final target SHA-256:
  `0d9150ab4cc7281ee9c449d6fc0d0c813ed1d3d5c2c5312a6791c8e66acd7483`.

## English Fidelity 2.0.0 — 2026-08-12

- Retranslated and source-reviewed 1,844 main records plus 85 restored
  dialogue records from the pinned Chinese NJ046 extraction.
- Restored 80 removed dialogue slots, four incorrect pointer redirections and
  the distinct Anti-Paralyze message.
- Split five pointer-specific meanings that the legacy English ROM had merged.
- Reconciled scenes with official English Red/Blue/Yellow wording when the
  Chinese scene and facts match, while retaining NJ046-specific material.
- Added the canonical `YELLOW VERSION` title and credits `LUIGA2009, ZLADE,
  CHPEXO` in title-screen pixel lettering derived from the original style.
- Published three verified patch routes targeting the same mapper-163 ROM,
  SHA-256 `d68597ad34d7772435af7422d37dee1b1e0dc78714b37098c9145290be04b9d4`.

Known limits: a complete human editorial playthrough and physical mapper-163
hardware test remain pending. See `docs/en/VALIDATION_STATUS.md`.
