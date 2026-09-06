# English Fidelity 2.0 locale

`catalog.csv` is the canonical English corpus. It contains 1,844 `MAIN`
records and 85 `RESTORED` records. Chinese Unicode text and pointer context are
the semantic authority; the 2015 English text and French v2 text are comparison
columns only.

Companion files have distinct structural roles:

- `source_adjudications.csv` records the 63 manually resolved source mappings;
- `pointer_variants.csv` separates seven meanings that share three legacy payloads;
- `storage_overlaps.csv` documents three intentional storage relationships;
- `neutral_glyph_records.csv` classifies the 18 language-neutral pictograms;
- `review_batches/` preserves the AI-assisted editorial review inputs and
  decisions used to assemble the catalogue.
- `ENGLISH_REVIEW_SHEET.csv` is a generated CSV table for human review.
  Regenerate it with `python3 tools/export_english_review_sheet.py`.
- `FULL_TEXT_REVIEW_20260816.csv` is the exhaustive 1,936-row review witness:
  1,934 live ROM surfaces plus two pointer-proven `shadowed_nonlive` overlap
  rows. Its method, constraints, exact build evidence, and open runtime proof
  are documented in `docs/en/FULL_TEXT_REVIEW_20260816.md`.

`ai_source_reviewed` means that every source and English proposal received a
complete AI-assisted source review. It does not claim a human playthrough or
human editorial approval. Size-driven rewrites are marked in the `compression`
and `compression_justification` columns.

The locale is validated with:

```sh
python3 tools/validate_english_catalog.py
python3 tools/english_full_text_review.py --check
python3 -m unittest tools.test_english_full_text_review
```

The English builder must use `--profile en-US`, the canonical catalogue for
both ordinary and restored text, and `pointer_variants.csv`. It must never use
the French font or French title/menu graphics.
