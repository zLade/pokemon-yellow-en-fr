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
- French columns inside `locales/en-US/catalog.csv`: secondary gloss and
  provenance fields for source comparison.

These files must not be translated in place: doing so would destroy their
byte-level hashes, provenance or non-regression value.

## English authority

The English build reads final text exclusively from the `english_v2` column of
`locales/en-US/catalog.csv`, with the `en-US` codec/layout profile and English
restoration rows. It does not compile `french_v2_gloss`, French restoration
payloads, the French font, or French title/menu graphics.

The maintained French documentation and distributable patches live only on
`fr`. All user-facing documentation tracked on `en` is English.
