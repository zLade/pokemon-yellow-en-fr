# Pokemon Yellow NJ046 - English translation

This project translates the unofficial Famicom/NES game **Lei Dian Huang Bi
Ka Qiu Chuan Shuo (NJ046)** from Chinese into natural English. The Chinese
game is the source of meaning; the 2015 English ROM supplies the technical
build base, not the translation authority.

Current game release: **English Fidelity 2.0.3**. This is the **en** branch.
The [French project](https://github.com/zLade/pokemon-yellow-en-fr/tree/fr)
is maintained separately and is not required to work on this translation.

## Play the translation

Apply the [2.0.3 IPS patch](releases/en/2.0.3/Pokemon_Yellow_NJ046_EN_v2.0.3.ips)
to the original Chinese NES ROM `Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes`, matching the base hash in the
[release instructions](releases/en/2.0.3/README.md). This is **not** the Game
Boy game. No ROM images are distributed.

Version 2.0.3 changes only the patch base: the resulting ROM is identical to 2.0.2. Do not apply this IPS to an English translation or an already patched ROM. IPS does not verify the input identity: check its SHA-256 first. Only the Chinese ROM is needed to apply the published patch; the other images below are internal build references.

## Help with the translation

You can help by checking the Chinese meaning, improving English wording,
or reporting on-screen problems. You do not need ROMs to edit the text and
run the static checks.

### 1. Get the project

Install Git and Python 3.12 or later. No additional Python packages are needed.
Fork the repository if you plan to submit a pull request, then clone your fork
with `--branch en`. To inspect the upstream project directly:

```sh
git clone --branch en --single-branch https://github.com/zLade/pokemon-yellow-en-fr.git
cd pokemon-yellow-en-fr
```

Run the commands below from this directory. Keep a real Git checkout: the
build safety checks need Git metadata, which a downloaded ZIP does not include.

### 2. Find and edit a message

All editable translation text is in **[translation/](translation/)**:

| File | Use |
| --- | --- |
| [catalog_part_1.csv](translation/catalog_part_1.csv) | First part of the catalogue: compare `chinese_text` and edit `english_v2`. |
| [catalog_part_2.csv](translation/catalog_part_2.csv) | Continuation of the same catalogue, with identical columns. Together the two parts contain 1,844 MAIN and 85 RESTORED records. |
| [pointer_variants.csv](translation/pointer_variants.csv) | Context-specific `english_v2` for Chinese messages merged by the old English translation. |
| [move_labels_two_line.csv](translation/move_labels_two_line.csv) | Graphical attack names: `full_name` is the name; `line_1` and `line_2` control its display. |

For most changes, edit only `english_v2` in either catalogue part. Search by Chinese
text, current English text or `stable_key`. `english_2015` is a comparison
with the older translation and can contain mistakes. Menus, names and
descriptions are included; not every record is spoken dialogue.

The scripts read `catalog_part_1.csv` followed by `catalog_part_2.csv` automatically. The CLI catalogue argument is the `translation` directory, not one individual part. Do not recreate a merged editable catalogue. Both parts must keep identical headers, unique stable keys and the original combined row order. Each file must stay below 512 KiB for GitHub table rendering; `build.py check` enforces this. If one grows too large, move complete rows across the boundary without changing the combined order.

Save CSV files as UTF-8 with the existing headers and row order. Use an editor
that preserves quoted commas, line breaks and leading/trailing spaces. Keep
identifiers, offsets, pointer references and layout fields unchanged for a
wording-only contribution. Lengths are calculated automatically.

Check `pointer_variants.csv` when the main row has variants. A primary variant
must match its MAIN row exactly: update both `english_v2` values if changing
that shared wording. Secondary variants keep their own contextual meaning.
The validator reports a mismatch; do not change pointer references to bypass it.

Translation rules:

- Follow the Chinese meaning and preserve NJ046-specific names, story and cameos.
- Prefer official English Red/Blue/Yellow terminology when the scene and meaning match.
- Keep full words when they fit. Use established abbreviations when necessary;
  split graphical move names at readable word boundaries where supported.
- Preserve control codes, placeholders and significant spaces. Some fragments
  are joined to Pokemon or trainer names at runtime.
- Keep comments and editorial notes in English. Do not add a second review
  spreadsheet, exported catalogue or JSON copy of the same translation.

### Translation column reference

The following tables cover every column in the editable CSV files. **Edit**
means a normal translation contribution; **Note** means editorial information
to update only when your correction warrants it; **Keep** means source or
technical metadata to leave unchanged. These labels are guidance, not CSV values.
Do not rename headers, add/delete records or renumber IDs for a wording change.
Blank metadata does not invite filling it with a guess.

#### Main catalogue (both parts)

| Column | Meaning | What to do |
| --- | --- | --- |
| `stable_key` | Permanent record identity, such as `MAIN:0x0301C4`. Use it in reports and cross-references. | Keep. |
| `record_type` | `MAIN`: a main translation record; `RESTORED`: a Chinese text restored after omission or pointer merging in the old English base. | Keep. |
| `entry_index` | Reference index of the entry in the catalogue inventory; not a screen position. | Keep. |
| `dialogue_id` | Link to the dialogue inventory, where applicable. | Keep. |
| `category` | Descriptive classification of the text's use. | Note: correct only with confirmed context. |
| `source_offset_or_pointer` | Hexadecimal source identity used by the builder; not the relocated address in the final ROM. | Keep. |
| `pointer_references` | Source pointer locations associated with the record. A pointer location is distinct from its text target. | Keep. |
| `selected_pointer_references` | Reviewed subset of references assigned to this record. | Keep; changing ownership requires technical review. |
| `layout` | Encoding/layout rule for the text box. See the explanation below. | Keep. |
| `speaker` | Speaker/context annotation when known; not a name automatically inserted into the game. | Note: correct only with evidence. |
| `chinese_record_indexes` | Links to record indexes in the pinned Chinese extraction. | Keep. |
| `chinese_offsets` | Corresponding source locations in the Chinese ROM. | Keep. |
| `chinese_text` | Chinese source meaning, possibly covering several source records. | Keep; report extraction/alignment errors separately. |
| `english_2015_storage` | How the old base stored the entry: ASCII, graphical codes, or absent/wrong pointer. | Keep. |
| `english_2015` | Historical English text or decoded representation, potentially incorrect. | Keep; it is a comparison, not the text to translate into. |
| `english_v2` | Current English text encoded into the game. | **Edit this for wording corrections.** Preserve significant spaces and controls. |
| `editorial_origin` | Provenance of the translation/review, such as direct Chinese translation with AI review. | Note: retain truthful provenance; do not relabel an edit as a completed review. |
| `alignment_method` | How the Chinese source was matched: pointer table, offset, overlap or restoration inventory, for example. | Keep; not a translation-quality rating. |
| `alignment_confidence` | Confidence in that source match, not proof of linguistic correctness. | Keep unless the source match is re-reviewed. |
| `source_resolution` | Reviewed decision used to resolve source identity or shared meanings. | Keep; coordinated source review is required to change it. |
| `review_status` | Recorded review state; `ai_source_reviewed` does not mean a complete human playthrough. | Note: change only to reflect an actual agreed review; never to bypass validation. |
| `source_capacity_bytes` | Original storage capacity in bytes, used by the builder's space checks. | Keep; not the visible line width or a manual length counter. |
| `compression` | Whether the wording was shortened to meet constraints. This is editorial shortening, not a binary compression switch. | Note: keep consistent with the wording. |
| `compression_justification` | Why shortening was necessary; required when `compression` is `yes`. | Note: explain the constraint and retained meaning. |
| `fidelity_comment` | Explanation of meaning, terminology or an intentional difference from the old English text. | Note: update in English when relevant. |
| `multi_source_mode` | Reviewed handling of multiple source meanings: safe sharing, pointer variants or restored text/reference splits. | Keep. |
| `pointer_variant_count` | Number of context-specific variants associated with the entry. | Keep; do not change to hide a missing variant. |
| `storage_overlap_group` | Identifier of a reviewed group whose source storage overlaps. | Keep. |
| `storage_overlap_role` | `owner` owns the storage; `suffix_alias` refers to a shared ending within it. | Keep; wording changes may need a coordinated review of the group. |

`dialogue_19_19` and `dialogue_intro_17_19` select dialogue line-width
rules; `pokedex_13x4` selects the 13-column, four-line description layout;
`fixed_grid_7x3` selects the seven-column, three-line item-description grid.
An empty layout or `raw` does **not** mean unlimited space: fixed slots,
runtime-inserted names and special battle routines still impose constraints.
The builder handles allocation; never increase a capacity or change a layout
just to make longer wording pass.

#### Context-specific pointer variants

| Column | Meaning | What to do |
| --- | --- | --- |
| `variant_key` | Unique variant identity, combining the parent key and pointer reference. | Keep. |
| `stable_key` | Parent MAIN record in the catalogue. | Keep. |
| `entry_index` | Parent entry's inventory index. | Keep. |
| `pointer_reference_hex` | Hexadecimal location of the pointer selecting this particular meaning. | Keep. |
| `chinese_record_index` | Specific Chinese extraction record for this variant. | Keep. |
| `chinese_offset_hex` | Location of that Chinese source text. | Keep. |
| `chinese_text` | Chinese meaning for this context. | Keep; use it to translate the variant. |
| `shared_english_2015_target` | Old English text address shared by otherwise distinct Chinese contexts. | Keep. |
| `english_2015` | Historical shared English wording, possibly wrong for this context. | Keep. |
| `english_v2` | English text for this pointer's context. | **Edit.** Keep the primary variant identical to its MAIN text; do not copy it over distinct secondary meanings. |
| `editorial_origin` | Translation/review provenance, as in the main catalogue. | Note: preserve accurate provenance. |
| `review_status` | Recorded review state, as in the main catalogue. | Note: do not change merely to satisfy a check. |
| `fidelity_comment` | Explanation of the contextual distinction and wording. | Note: update in English when relevant. |

#### Graphical move names

| Column | Meaning | What to do |
| --- | --- | --- |
| `move_index` | Move's index in this NES game's move table; not a row number to renumber or an assumed Game Boy ID. | Keep, including its formatting. |
| `full_name` | Complete readable move name for identification and reports. | **Edit** when correcting the name; this field alone does not redraw the label. |
| `line_1` | Actual top line of the graphical label. | **Edit**, using 1–8 encoded glyphs. |
| `line_2` | Actual bottom line of the graphical label. | **Edit**, using 1–8 encoded glyphs; the current loader requires a nonempty second line. |

For example, `Flame Wheel` is displayed with `Flame` / `Wheel`. Keep
the complete name in `full_name` even when the displayed lines need an
abbreviation. These limits apply to this graphical table, not all dialogue.
The file contains selected graphical overrides, not every attack in the game.
Do not add/remove move indexes without checking the graphics allocation and tests.

For a typical correction, edit `english_v2`, adjust its primary variant if
present, and update a relevant explanation rather than unrelated metadata.
Run the checks below. Some intentional battle or source changes also require
reviewing explicit test expectations; report that need rather than disabling
the test. Never “fix” a mismatch by changing pointers or source text.

### 3. Check your change

```sh
python build.py check
python -m unittest discover -s tools -p "test_*.py"
```

`check` validates all four translation files, including graphical labels.
Tests needing local ROMs or fixtures are skipped when those inputs are absent.
Fix reported encoding or layout errors; do not weaken the checks to accept an
overflow. Static checks do not establish that a sentence is natural or that
every interactive screen works correctly.

### 4. Submit a correction or bug report

Open a pull request against **en**, with focused edits and a short explanation
of the original Chinese meaning, your English wording and the checks performed.
Include the stable key when available. Say clearly if you could not test in-game.

For a display bug, include the release version, emulator, location, steps to
reproduce, actual/expected text and a screenshot if possible. Test long inserted
names, both yes/no choices, cursor movement and the following text box to catch
overflow or uncleared letters. Never attach ROMs to an issue or pull request.

## Build an edited ROM

Supply these two NES images privately. Default filenames are at the repository
root; exact hashes are also in [data/source-inputs.sha256](data/source-inputs.sha256).
Both expected images are 2,097,168 bytes.

| Default filename | Purpose | SHA-256 |
| --- | --- | --- |
| `Pokemon Yellow English 9-23-2015.nes` | Technical build base | `d5c308b5862ccbe4647d4255a11bb0f1cb6817c4b107feac112509d658a9943b` |
| `Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes` | Final IPS application base and original dojo graphics | `450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed` |

```sh
python build.py build --output-dir build/my-translation
```

Choose a new or empty directory under `build/`. The builder refuses to replace
populated output directories or overwrite source inputs. It produces
`Pokemon_Yellow_NJ046_EN.nes`, `Pokemon_Yellow_NJ046_EN.ips`, `build_report.json`
and `pointer_manifest.json`. These local outputs are ignored by Git.

To store ROMs elsewhere, pass `--english-2015-rom PATH`
and `--chinese-rom PATH`. Quote paths containing spaces. Use a new output name
for a second build, or remove only your previous generated output first.

The builder encodes and repacks the translation tables, renders graphical move
names, adds the credited title, restores the Chinese dojo graphics and applies
the corrected pitch table. It then checks pointers, space budgets, font and
glyph preservation, deterministic rebuilding and the IPS round trip.

To reproduce the unchanged published release byte for byte:

```sh
python build.py build --verify-release --output-dir build/reproduce-2.0.3
```

Omit `--verify-release` for intentional translation changes: their output hash
should differ. A local build does not update the published patch. New releases
must be reviewed and versioned separately.

## Verification and emulator checks

CI runs the ROM-free tests on Python 3.12 and 3.14 and verifies the release
patch checksum. Tests skipped for absent local inputs are not passes. To
include the exact-release integration test locally, set the environment
variable `NJ046_VERIFY_RELEASE=1` before running the unit tests; use it only
with unchanged release translation inputs.

The builder verifies all 1,912 expected pointers, restored text ownership,
graphical move labels, space budgets, the English font and battle controls,
glyph residue and IPS reconstruction. Generated reports identify the candidate
ROM by hash; they are evidence, not another source of editable text.

For on-screen verification, use an emulator supporting mapper 163. Check
battle openings and endings, long names and attacks, shopping, inventory,
move learning, both choices in prompts, cancellation and consecutive messages.
Look for clipped text, missing cursors and uncleared punctuation.

Advanced testers can use `tools/run-mesen-english-regression-suite.ps1` for
targeted Mesen checks: boot, mapper, introduction, characters, menus, three
assisted text-rendering cases and save integrity, in Dendy, NTSC and PAL modes.
It does not attempt to play through the game and requires no route recording.
Inspect its parameters and supply Mesen and a target map generated by
`tools/prepare_critical_restoration_runtime.py` from the candidate's pointer
manifest. ROMs and emulator evidence are not included in this repository.
The suite is separate from ROM-free CI; a normal build records runtime and
hardware validation as **NOT RUN**. The automated campaign-dependent checks
are not part of its coverage; all 85 restorations remain statically checked.

After building a candidate, prepare its three assisted rendering targets
(replace `build/my-translation` if you chose a different output directory):

```sh
python tools/prepare_critical_restoration_runtime.py --rom build/my-translation/Pokemon_Yellow_NJ046_EN.nes --pointer-manifest build/my-translation/pointer_manifest.json --output build/critical_restoration_runtime_targets.tsv
```

Regenerate this map after changing the candidate ROM. It is local test input,
not a translation table to commit.

## What the other files are for

| Location | Role |
| --- | --- |
| `translation/` | The four editable translation files. Start here. |
| `data/source/` | Pinned Chinese records and glyph-to-Unicode map, used to verify source context. Do not edit during routine translation work. |
| `data/validation/` | Reviewed source decisions, pointer ownership, shared storage, cameo names, neutral graphics and bank-space limits. These are safeguards, not another translation. |
| `tools/` | Build implementation, regression tests and optional emulator probes. Contributors normally use `build.py` instead. |
| `releases/en/2.0.3/` | Published IPS, version, application instructions and checksum. |
| `build/` | Ignored generated files and local test evidence; never translation inputs. |

The Chinese extraction is hash-pinned; its original HZK16 extraction tools are
not included. Replacing source records or technical ownership rules requires a
separate provenance review. Keep ROMs, saves, recordings and local reports out
of commits. Earlier project revisions remain available in Git history.

## Status and credits

The translation has had an AI-assisted source review. A complete human
playthrough and testing on a physical mapper-163 cartridge remain pending.
Build reports explicitly distinguish byte-level checks from emulator/hardware
testing. See [verification](#verification-and-emulator-checks) and the
[changelog](CHANGELOG.md).

The game title credits **LUIGA2009, ZLADE, CHPEXO**. Third-party material and
distribution scope are described in [NOTICE.md](NOTICE.md).
