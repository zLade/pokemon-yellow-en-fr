# English full-text review — 2026-08-16

## Scope and authority

This review inventories the complete canonical locale and distinguishes live
ROM surfaces from shadowed overlap cells:

- 1,929 catalogue records: 1,844 `MAIN` and 85 `RESTORED`; two `MAIN` rows are
  proven shadowed/non-live, leaving 1,927 live catalogue records;
- all 1,055 dialogue records, 159 Pokédex records, menus, battle/system
  fragments, items, shops, fixed labels, and dynamic suffixes;
- all seven declared pointer variants;
- the separate 114-entry two-line graphical move-name plan.

The Chinese NJ046 record is the semantic authority. Matching scenes were
checked against the local `pret/pokered` and `pret/pokeyellow` English sources
for natural Red/Blue/Yellow US phrasing. Source-specific Hoenn/Johto material,
creator cameos, the Fighting Dojo additions, and other NJ046-only facts were
retained rather than replaced with unrelated Game Boy dialogue.

`locales/en-US/FULL_TEXT_REVIEW_20260816.csv` is the row-for-row review witness.
It contains exactly 1,936 unique catalogue/variant witnesses: 1,934 live ROM
surfaces and two explicitly classified `shadowed_nonlive` rows. It records the
source, previous wording, reviewed wording, disposition, constraint, and
rationale.

## Applied policy

- English must be grammatical and idiomatic, with complete clauses where the
  source contains them.
- No displayed word may be clipped or divided accidentally.
- Official Gen I names and trainer classes are used when applicable.
- Generic trainer-class labels are omitted from single-speaker field dialogue,
  matching Red/Blue/Yellow presentation: the sprite and encounter identify the
  speaker. Proper names remain. Labels remain inside multi-speaker payloads,
  where omitting them would make a speaker change ambiguous; those labels use
  official classes such as `BLACK BELT` and `SWIMMER`.
- Ambiguous source readings were not silently rewritten.

The deterministic pass changes 822 live catalogue records and four pointer
variants. The count includes semantically neutral removal of redundant
single-speaker labels, which was required to keep the complete naturalized
corpus inside the original PRG text-bank budget. Two shadowed catalogue cells
are excluded from that count because pointer proof shows they are not live;
their canonical bytes were left unchanged because altering them changed the
deterministic build even though no live pointer displays them.

## Shadowed overlap classification

Two raw catalogue cells were initially liable to be mistaken for live
dialogues. Pointer resolution proves otherwise:

| Shadowed row | Pointer | Exact live owner | Final target |
| --- | --- | --- | --- |
| `MAIN:0x039D3B` | `0x038347` | `RESTORED:0x038347` | `0x03A2CE` |
| `MAIN:0x03DF0D` | `0x03CF60` | `MAIN:0x03D7CB` | `0x03B1E6` |

The report assigns both rows domain/status `shadowed_nonlive`; neither is
counted among the 1,934 live surfaces. A focused test pins all three pieces of
ownership evidence and prevents a future raw-layout false positive.

## Certain executable-context corrections

| Stable key | Pointer reference | Final text | Evidence |
| --- | --- | --- | --- |
| `MAIN:0x0349E5` | `0x0348FD` | `Got Ether!` | Live item slot is Ether; its description restores 10 PP. |
| `MAIN:0x0349F2` | `0x0348FF` | `Got Max Ether!` | Live item slot is Max Ether; its description restores all PP. |
| `MAIN:0x038F91` | `0x0382B5` | `Got TM35!` | Brock's following text and the executable TM table identify TM35/Harden. |

The executable witness is `tools/audit_brock_tm_reward.py`; the catalogue
validator independently pins all three final payloads.

## Narrow item-description renderer

The item-description table at references `0x031971` through `0x0319B3` uses
three rows of seven cells, not two. Exactly 31 unique catalogue records are
marked `fixed_grid_7x3`; every encoded payload is at most 21 bytes.

The three Ball variants are:

| Pointer | Encoded rows | Length |
| --- | --- | ---: |
| `0x031971` | `Catch` / `Pokémon` / blank | 14 |
| `0x031973` | `Better` / `than a` / `Poké B.` | 21 |
| `0x031975` | `Better` / `than a` / `Great B` | 21 |

This preserves the Chinese comparison chain instead of replacing it with a
vague capture-rate headline.

## Dynamic boundary proof

The combat window has 25 interior cells (columns 4 through 28). The stock
routine erased only 24 of them, which allowed the last character of a full
line to survive into the next message. The reviewed engine now clears all 25
cells without touching column 29 or the border. A guarded `0x0A` control can
move an approved first-row fragment to row two and refuses a third row.

The cross-language executable-topology matrix covers 101 pointer fragments,
including the less obvious evolution and move-learning callsites. It records
the exact producer, starting row, dynamic fields, worst-case width, and joining
spaces. The English candidate has zero width failures and zero joining-space
failures. Notable maximum cases are:

- Pokémon name plus ` wants to learn`: 25/25 cells;
- `Give up on` / `learning <MOVE>?`: 10 cells then at most 20;
- `The move <MOVE>` / `was forgotten!`: at most 19 then 14;
- `Learned move:` / `<MOVE>`: at most 13 then 10;
- full `No longer badly poisoned!`: 25/25 cells.

Both bad-poison and flinch variants still own their leading joining space.
The pointer manifest and exact-rebuild validator reject any future relocation
that loses a separator, a line-break control, or one of the three engine
patches (25-cell clear, guarded newline, and autonomous already-status result).

## Validation

The following gates pass on the reviewed sources and text candidate:

- `python3 tools/english_full_text_review.py --check`;
- `python3 tools/export_english_review_sheet.py --check`;
- `python3 tools/validate_english_catalog.py` — 1,929 catalogue rows and seven
  variants;
- 119 English-focused unit tests for layout, catalogue, review determinism,
  workflow, release gates, and pointer-manifest logic;
- eight focused pointer-variant unit tests, including both joining spaces;
- `tools/validate_english_repacked.py` — exact byte-for-byte rebuild, 85
  restorations, four secondary variants, and 114 graphical move composites;
- `tools/english_pointer_manifest.py` — 1,912/1,912 live structural references;
- `tools/validate_mapper163.py` — mapper 163, English font, title, reset vectors,
  move graphics, and restored Chinese Dojo deputy;
- IPS round-trip reproduction for text, title, and final candidates.

The complete `tools/test_assistant_pointer_variants.py` suite remains red at
8/10 despite all eight focused pointer-variant unit tests passing. Its generic
synthetic-ROM smoke has a pre-existing fixture incompatibility with the default
graphical move plan (121/177 unique synthetic targets). Its French-profile
smoke also pins an obsolete expected SHA-256 (`fe0171...`) while the current
output is `e98c1a...`. The real canonical English ROM build and its independent
exact-rebuild validator pass; neither unrelated fixture failure is hidden as a
successful test.

## Candidate artifacts

Artifacts from this review are local build outputs.

| Artifact | SHA-256 |
| --- | --- |
| `Pokemon_Yellow_EN_Full_Text_Review_text.nes` | `aa9bced0e7ad3d7dc622eca6d2856ae1ba43a961ffef275a51b906904490a35b` |
| `Pokemon_Yellow_EN_Full_Text_Review_text.ips` | `d83f4200c813d10157c9a22296fd24109f557cfd15a6be37dff083fa3b39e8d2` |
| `Pokemon_Yellow_EN_Full_Text_Review_final.nes` | `0d9150ab4cc7281ee9c449d6fc0d0c813ed1d3d5c2c5312a6791c8e66acd7483` |
| `Pokemon_Yellow_EN_Full_Text_Review_final.ips` | `43e48d41414cbaab1529d06b7d0e05cd043204454473b9c26f3b5de46078d941` |

The constrained PRG pair retains 2,654 free bytes, and
`fixed_overflow.csv` contains no data rows.

## Deliberately retained source-specific wording and remaining proof

- Bruno remains NJ046's Ground-type master and Agatha its Ghost-type master;
  these differ from Game Boy continuity but are explicit source facts.
- Creator cameos and the source stage direction `(He vanishes.)` remain.
- Short conversational replies and taunts that are complete in context remain
  fragments when changing them would invent content.
- Static validation and targeted executable checks are complete. Controlled
  Mesen probes confirm the three-row Ball renderer and the 25-cell
  clear/newline behavior without border damage or stale characters. A full
  human story playthrough of every one of the 1,934 live text surfaces is still
  not claimed.
