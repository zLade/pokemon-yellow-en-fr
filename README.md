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
| [catalog.csv](translation/catalog.csv) | Main catalogue: compare `chinese_text` and edit `english_v2`. Contains 1,844 MAIN and 85 RESTORED records. |
| [pointer_variants.csv](translation/pointer_variants.csv) | Context-specific `english_v2` for Chinese messages merged by the old English translation. |
| [move_labels_two_line.csv](translation/move_labels_two_line.csv) | Graphical attack names: `full_name` is the name; `line_1` and `line_2` control its display. |

For most changes, edit only `english_v2` in `catalog.csv`. Search by Chinese
text, current English text or `stable_key`. `english_2015` is a comparison
with the older translation and can contain mistakes. Menus, names and
descriptions are included; not every record is spoken dialogue.

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

### 3. Check your change

```sh
python build.py check
python -m unittest discover -s tools -p "test_*.py"
```

`check` validates all three translation tables, including graphical labels.
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
| `translation/` | The three editable translation tables. Start here. |
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
