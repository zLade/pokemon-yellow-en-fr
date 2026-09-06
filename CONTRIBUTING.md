# Contributing to the English branch

The canonical English branch is `en`; the maintained French release lives on
`fr`.

## Rules

- Never commit a complete ROM, emulator state, save file or proprietary
  executable. Submit source changes, review data and IPS/BPS patches only.
- Treat the pinned Chinese NJ046 text as the semantic source of record.
- Use official English Red/Blue/Yellow wording only when the imitated scene and
  facts match. Preserve NJ046-specific names, places, cameos and plot details.
- Do not renumber `stable_key` values or silently replace source provenance.
- Record editorial changes in the catalogue and applicable audit table.
- Keep active English documentation in English. French material may remain
  only when it is a pinned technical input or non-regression fixture.

## Required checks

```sh
python3 tools/validate_branch_separation.py --language en
python3 tools/validate_english_catalog.py
(cd releases/en/2.0.2 && sha256sum -c SHA256SUMS)
python3 -m unittest -v \
  tools.test_validate_branch_separation \
  tools.test_validate_english_catalog \
  tools.test_english_codec \
  tools.test_english_layout \
  tools.test_locale_profiles \
  tools.test_restoration_topology \
  tools.test_english_review_workflow
```

ROM-dependent release and Mesen checks must be run locally using local input
ROMs whose hashes match `data/source-inputs.sha256`. Summarize those results in
the pull request without uploading the ROMs.
