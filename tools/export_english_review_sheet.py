#!/usr/bin/env python3
"""Export the canonical English corpus as a human-review friendly CSV."""

from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LOCALE = ROOT / "locales" / "en-US"
DEFAULT_OUTPUT = LOCALE / "ENGLISH_REVIEW_SHEET.csv"

FIELDS = (
    "stable_key",
    "record_type",
    "dialogue_id",
    "category",
    "layout",
    "speaker",
    "source_offset_or_pointer",
    "chinese_text",
    "english_2015",
    "french_v2_gloss",
    "english_v2",
    "official_reference_class",
    "reference_disposition",
    "reference_url",
    "reference_revision",
    "changed_during_official_reference_pass",
    "english_before_reference_pass",
    "reference_reason",
    "compression",
    "compression_justification",
    "fidelity_comment",
    "alignment_confidence",
    "source_resolution",
    "ai_review_status",
    "human_review_status",
    "human_reviewer",
    "human_review_notes",
)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def index_unique(
    rows: list[dict[str, str]], field: str, label: str
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(field, "").strip()
        if not key or key in result:
            raise ValueError(f"{label}: missing or duplicate {field}: {key!r}")
        result[key] = row
    return result


def export_rows() -> list[dict[str, str]]:
    catalogue = read_rows(LOCALE / "catalog.csv")
    changes = index_unique(
        read_rows(LOCALE / "official_reference_consistency_changes.csv"),
        "stable_key",
        "official reference changes",
    )
    audits = index_unique(
        read_rows(LOCALE / "official_gen1_scene_audit.csv"),
        "stable_key",
        "official scene audit",
    )
    if len(catalogue) != 1929:
        raise ValueError(f"catalogue has {len(catalogue)} rows, expected 1929")
    if len(changes) != 170:
        raise ValueError(f"official change log has {len(changes)} rows, expected 170")
    if len(audits) != 183:
        raise ValueError(f"official scene audit has {len(audits)} rows, expected 183")

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for source in catalogue:
        key = source["stable_key"]
        if key in seen:
            raise ValueError(f"duplicate catalogue stable_key: {key}")
        seen.add(key)
        change = changes.get(key, {})
        audit = audits.get(key, {})
        result.append(
            {
                "stable_key": key,
                "record_type": source["record_type"],
                "dialogue_id": source["dialogue_id"],
                "category": source["category"],
                "layout": source["layout"],
                "speaker": source["speaker"],
                "source_offset_or_pointer": source[
                    "source_offset_or_pointer"
                ],
                "chinese_text": source["chinese_text"],
                "english_2015": source["english_2015"],
                "french_v2_gloss": source["french_v2_gloss"],
                "english_v2": source["english_v2"],
                "official_reference_class": audit.get(
                    "reference_class", "Not identified as a Gen I scene"
                ),
                "reference_disposition": audit.get("disposition", "n/a"),
                "reference_url": audit.get("source_url", ""),
                "reference_revision": audit.get("source_revision", ""),
                "changed_during_official_reference_pass": (
                    "Yes" if change else "No"
                ),
                "english_before_reference_pass": change.get(
                    "previous_english_v2", ""
                ),
                "reference_reason": change.get(
                    "reason", audit.get("review_note", "")
                ),
                "compression": source["compression"],
                "compression_justification": source[
                    "compression_justification"
                ],
                "fidelity_comment": source["fidelity_comment"],
                "alignment_confidence": source["alignment_confidence"],
                "source_resolution": source["source_resolution"],
                "ai_review_status": source["review_status"],
                "human_review_status": "To review",
                "human_reviewer": "",
                "human_review_notes": "",
            }
        )
    unknown_changes = sorted(set(changes) - seen)
    unknown_audits = sorted(set(audits) - seen)
    if unknown_changes or unknown_audits:
        raise ValueError(
            "official reference tables contain keys outside the catalogue: "
            f"changes={unknown_changes}, audits={unknown_audits}"
        )
    return result


def render_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = export_rows()
    rendered = render_csv(rows)
    if args.check:
        current = (
            args.output.read_text(encoding="utf-8")
            if args.output.exists()
            else ""
        )
        if current != rendered:
            print(f"English review CSV is stale: {args.output}")
            return 1
        print("English review CSV: PASS (1,929 rows; 170 changed references)")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="")
    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
