# NJ046 English Fidelity 2.0.2

> Canonical branch: **`en` (English only)**
> French release branch: **`fr`**

This branch develops a faithful English localization of the Famicom game
`Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046)`.

## Translation policy

- The Chinese ROM and the pinned Unicode extraction are the semantic source
  of record.
- Official English Red/Blue/Yellow wording and terminology are preferred when
  the NJ046 scene is clearly imitating those games and the meaning matches.
- The English anime is a secondary reference for anime-specific material.
- NJ046-specific names, cameos, locations and plot details are preserved.
- The 2015 English ROM is a technical build base and comparison source, not an
  editorial authority.
- French 2.0 is retained only as a secondary gloss and structural
  non-regression reference.

## Repository layout

- `locales/en-US/catalog.csv`: canonical corpus with 1,844 main records and
  85 restored records;
- `locales/en-US/review_batches/`: source-review decisions;
- `locales/en-US/ENGLISH_REVIEW_SHEET.csv`: generated CSV table for
  human review;
- `data/source/chinese-english-fidelity/`: pinned Chinese extraction and
  alignment evidence;
- `tools/build_english_release.py`: deterministic English release builder;
- `tools/run-mesen-english-regression-suite.ps1`: English Mesen runtime suite;
- `releases/en/2.0.2/`: current patch-only English release;
- `docs/en/`: active English documentation.

Project maintenance rules are in [`CONTRIBUTING.md`](CONTRIBUTING.md), release
history in [`CHANGELOG.md`](CHANGELOG.md), and third-party scope in
[`NOTICE.md`](NOTICE.md).

The review table in `locales/en-US/ENGLISH_REVIEW_SHEET.csv` contains all
1,929 records and editable human-review status columns.

The French source corpus and French non-regression tools remain in this
branch only where the English build consumes them as pinned technical input.
They are not the active English documentation. The maintained French project
and its releases live on `fr`.

## Quick validation

After restoring the input ROMs with the hashes listed in
`data/source-inputs.sha256`:

```sh
python3 tools/validate_branch_separation.py --language en
python3 tools/validate_english_catalog.py
python3 -m unittest tools.test_validate_english_catalog \
  tools.test_validate_english_repacked \
  tools.test_validate_mapper163_profiles
```

The complete release command and its additional build inputs are documented
in [`docs/en/BUILD_AND_RELEASE.md`](docs/en/BUILD_AND_RELEASE.md).

## Current release

The credited English target has SHA-256
`703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3`.
It uses mapper 163, the true `YELLOW VERSION` title from canonical
`yellow.nes`, and the title credits `LUIGA2009, ZLADE, CHPEXO`.

Release 2.0.2 includes the completed source review, natural battle and
move-learning wording, two-line long-move labels and the verified interactive
move-forgetting cursor, plus the corrected NES pitch table. Its independent release gates cover IPS integrity,
mapper 163, all 1,912 expected pointers and 101 dynamic-layout scenarios.

Only IPS/BPS patches are distributed. No complete ROM is tracked. Hardware
testing on a physical mapper-163 cartridge remains **NOT TESTED**. Editorial
status remains: **AI-assisted full source review; human playthrough pending**.
