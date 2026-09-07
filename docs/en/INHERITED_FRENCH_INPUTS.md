# Inherited French technical inputs

The English branch is built from infrastructure developed for French 2.0.
Some French files remain tracked because they are reproducibility inputs, not
because French is an active locale on this branch.

## Deliberately retained

- `script.py` and `traduction_base.csv`: pinned structural baseline and French
  golden corpus used by the non-regression build;
- `LISTE_EXHAUSTIVE_DIALOGUES.csv`: reviewed 1,055-dialogue source ledger used
  to seed and refresh Chinese alignment derivatives;
- `tools/data/french_*.json`: exact French golden payloads required to prove
  that English-profile refactoring does not change the released French ROM;
- `tools/french_font.py`, French layout helpers and their tests: isolated
  implementation used only when the explicit `fr-FR` profile is selected;
- `french_v2_gloss` inside `locales/en-US/catalog.csv`: secondary French
  dialogue text for source comparison. Provenance annotations are English.

French dialogue payloads and golden byte expectations must remain unchanged.
Headers, editorial annotations, comments and tool messages use English on
this branch. CSV readers and generators share the English schema, and source
ledger IDs, offsets and payloads remain stable across metadata updates.

The original input filenames and stable technical identifiers are retained
for compatibility. French lexical examples, glyph samples and golden test
fixtures are reference data, not user-facing tool messages.

The following ROM-free tests check the English schema, annotations,
lossless spreadsheet export and pinned text/pointer fingerprints:

```sh
python3 -m unittest tools.test_english_repository_metadata tools.test_csv_to_review_xlsx
```

## English authority

The English build reads final text exclusively from the `english_v2` column of
`locales/en-US/catalog.csv`, with the `en-US` codec/layout profile and English
restoration rows. It does not compile `french_v2_gloss`, French restoration
payloads, the French font, or French title/menu graphics.

The maintained French documentation and distributable patches live only on
`fr`. All user-facing documentation tracked on `en` is English.
