#!/usr/bin/env python3
"""Export and merge auditable EN2 source-review batches.

The canonical catalogue remains the single build input.  Review agents work
in small JSON files so they never edit the large CSV concurrently.  Merging
is deterministic, refuses duplicate or unknown keys, validates every payload
with the strict English codec/layout, and never upgrades unresolved source
provenance to a release-ready status.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.locales.profiles import ENGLISH_TEXT_PROFILE  # noqa: E402


DEFAULT_CATALOGUE = ROOT / "locales" / "en-US" / "catalog.csv"
DEFAULT_BATCH_DIRECTORY = (
    ROOT / "locales" / "en-US" / "review_batches"
)

RELEASE_REVIEW_STATUS = "ai_source_reviewed"
BLOCKED_SOURCE_RESOLUTIONS = frozenset(
    {
        "",
        "unaligned",
        "pending",
        "pending_missing_source",
        "pending_source_adjudication",
        "unresolved",
    }
)

SOURCE_EXPORT_FIELDS = (
    "stable_key",
    "record_type",
    "entry_index",
    "dialogue_id",
    "category",
    "source_offset_or_pointer",
    "pointer_references",
    "selected_pointer_references",
    "layout",
    "speaker",
    "chinese_text",
    "english_2015",
    "french_v2_gloss",
    "alignment_method",
    "alignment_confidence",
    "source_resolution",
    "source_capacity_bytes",
    "multi_source_mode",
    "fidelity_comment",
)

REQUIRED_REVIEW_FIELDS = (
    "stable_key",
    "english_v2",
    "editorial_origin",
    "fidelity_comment",
)


class ReviewWorkflowError(ValueError):
    """A batch or catalogue violates the traceable review contract."""


def read_catalogue(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    if not header or "stable_key" not in header:
        raise ReviewWorkflowError(f"{path}: missing stable_key column")
    seen: set[str] = set()
    for line_number, row in enumerate(rows, start=2):
        key = row.get("stable_key", "")
        if not key:
            raise ReviewWorkflowError(
                f"{path}:{line_number}: empty stable_key"
            )
        if key in seen:
            raise ReviewWorkflowError(f"{path}: duplicate key {key}")
        seen.add(key)
    return header, rows


def _domain(row: Mapping[str, str]) -> str:
    layout = row.get("layout", "")
    if layout.startswith("dialogue_") or row.get("record_type") == "RESTORED":
        return "dialogue"
    if layout == "pokedex_13x4":
        return "pokedex"
    return "other"


def build_batches(
    rows: Sequence[Mapping[str, str]],
    *,
    batch_size: int,
    statuses: Iterable[str] = ("pending",),
    exclude_keys: Iterable[str] = (),
) -> list[dict[str, object]]:
    """Return deterministic review documents for selected catalogue rows."""
    if batch_size < 1:
        raise ReviewWorkflowError("batch_size must be positive")
    accepted = {status.casefold() for status in statuses}
    excluded = set(exclude_keys)
    selected = [
        row
        for row in rows
        if row.get("review_status", "").casefold() in accepted
        and row.get("multi_source_mode") != "pointer_variant_split"
        and row.get("stable_key") not in excluded
    ]
    batches: list[dict[str, object]] = []
    for domain in ("dialogue", "pokedex", "other"):
        domain_rows = [row for row in selected if _domain(row) == domain]
        for start in range(0, len(domain_rows), batch_size):
            batch_number = start // batch_size + 1
            batch_rows = domain_rows[start:start + batch_size]
            batches.append(
                {
                "schema": "nj046-en2-source-review-v1",
                "batch_id": f"{domain}-{batch_number:03d}",
                "domain": domain,
                "authority_order": [
                    "chinese_text_and_pointer_context",
                    "executable_rom_data_for_mechanics",
                    "french_v2_secondary_gloss",
                    "official_english_terms_when_semantically_matching",
                    "english_2015_only_after_positive_comparison",
                ],
                "review_status_to_emit": RELEASE_REVIEW_STATUS,
                "entries": [
                    {field: row.get(field, "") for field in SOURCE_EXPORT_FIELDS}
                    for row in batch_rows
                ],
                }
            )
    return batches


def export_batches(
    catalogue: Path,
    output_directory: Path,
    *,
    batch_size: int,
    exclude_keys: Iterable[str] = (),
) -> list[Path]:
    _header, rows = read_catalogue(catalogue)
    batches = build_batches(
        rows,
        batch_size=batch_size,
        exclude_keys=exclude_keys,
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    existing = sorted(output_directory.glob("*.input.json"))
    if existing:
        raise ReviewWorkflowError(
            f"{output_directory}: batch inputs already exist"
        )
    paths: list[Path] = []
    for document in batches:
        path = output_directory / f"{document['batch_id']}.input.json"
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def _read_review_document(path: Path) -> list[dict[str, object]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewWorkflowError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ReviewWorkflowError(f"{path}: root must be an object")
    if document.get("schema") != "nj046-en2-source-review-v1":
        raise ReviewWorkflowError(f"{path}: unsupported schema")
    entries = document.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ReviewWorkflowError(f"{path}: entries must be a non-empty list")
    normalized: list[dict[str, object]] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ReviewWorkflowError(f"{path}: entry {index} is not an object")
        missing = [
            field
            for field in REQUIRED_REVIEW_FIELDS
            if not isinstance(entry.get(field), str)
            or not str(entry.get(field)).strip()
        ]
        if missing:
            raise ReviewWorkflowError(
                f"{path}: entry {index} missing {', '.join(missing)}"
            )
        normalized.append(dict(entry))
    return normalized


def collect_reviews(paths: Sequence[Path]) -> dict[str, dict[str, object]]:
    reviews: dict[str, dict[str, object]] = {}
    for path in sorted(paths):
        for entry in _read_review_document(path):
            key = str(entry["stable_key"])
            if key in reviews:
                raise ReviewWorkflowError(f"duplicate reviewed key {key}")
            reviews[key] = entry
    return reviews


def merge_reviews(
    rows: Sequence[Mapping[str, str]],
    reviews: Mapping[str, Mapping[str, object]],
    *,
    allow_overwrite: bool = False,
) -> list[dict[str, str]]:
    """Merge complete reviewed payloads and validate their encoded layouts."""
    known = {row["stable_key"] for row in rows}
    unknown = sorted(set(reviews) - known)
    if unknown:
        raise ReviewWorkflowError(
            "unknown reviewed keys: " + ", ".join(unknown)
        )

    result: list[dict[str, str]] = []
    applied: set[str] = set()
    for source_row in rows:
        row = dict(source_row)
        key = row["stable_key"]
        review = reviews.get(key)
        if review is None:
            result.append(row)
            continue
        if row.get("review_status") != "pending" and not allow_overwrite:
            raise ReviewWorkflowError(
                f"{key}: already reviewed; use --allow-overwrite explicitly"
            )
        if not row.get("chinese_text", "").strip():
            raise ReviewWorkflowError(f"{key}: Chinese source is empty")
        source_resolution = row.get("source_resolution", "").casefold()
        if source_resolution in BLOCKED_SOURCE_RESOLUTIONS:
            raise ReviewWorkflowError(
                f"{key}: source resolution is still {source_resolution or 'empty'}"
            )

        text = str(review["english_v2"])
        try:
            payload = ENGLISH_TEXT_PROFILE.format_text(
                text,
                row.get("layout", ""),
            )
        except (TypeError, ValueError, UnicodeError) as exc:
            raise ReviewWorkflowError(f"{key}: invalid English payload: {exc}") from exc

        compression = review.get("compression", False)
        if not isinstance(compression, bool):
            raise ReviewWorkflowError(f"{key}: compression must be boolean")
        justification = str(review.get("compression_justification", ""))
        if compression and not justification.strip():
            raise ReviewWorkflowError(
                f"{key}: compressed wording needs a justification"
            )

        row["english_v2"] = text
        row["editorial_origin"] = str(review["editorial_origin"])
        row["review_status"] = RELEASE_REVIEW_STATUS
        row["encoded_length"] = str(len(payload))
        row["compression"] = "yes" if compression else "no"
        row["compression_justification"] = justification
        row["fidelity_comment"] = str(review["fidelity_comment"])
        applied.add(key)
        result.append(row)

    missing = sorted(set(reviews) - applied)
    if missing:
        raise AssertionError(f"internal merge omission: {missing}")
    return result


def write_catalogue_atomic(
    path: Path,
    header: Sequence[str],
    rows: Sequence[Mapping[str, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(header))
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def command_export(args: argparse.Namespace) -> int:
    excluded: set[str] = set()
    if args.exclude_keys_csv:
        _header, exclusion_rows = read_catalogue(args.exclude_keys_csv.resolve())
        excluded = {row["stable_key"] for row in exclusion_rows}
    paths = export_batches(
        args.catalogue.resolve(),
        args.output_directory.resolve(),
        batch_size=args.batch_size,
        exclude_keys=excluded,
    )
    print(f"Exported {len(paths)} review batch(es).")
    return 0


def command_merge(args: argparse.Namespace) -> int:
    catalogue = args.catalogue.resolve()
    header, rows = read_catalogue(catalogue)
    review_paths = sorted(args.review_directory.resolve().glob("*.review.json"))
    if not review_paths:
        raise ReviewWorkflowError("no *.review.json files found")
    reviews = collect_reviews(review_paths)
    merged = merge_reviews(
        rows,
        reviews,
        allow_overwrite=args.allow_overwrite,
    )
    output = args.output.resolve() if args.output else catalogue
    write_catalogue_atomic(output, header, merged)
    print(f"Merged {len(reviews)} reviewed payload(s) into {output}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export = subparsers.add_parser("export")
    export.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    export.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_BATCH_DIRECTORY,
    )
    export.add_argument("--batch-size", type=int, default=100)
    export.add_argument(
        "--exclude-keys-csv",
        type=Path,
        help="CSV with a stable_key column to exclude from this wave.",
    )
    export.set_defaults(func=command_export)

    merge = subparsers.add_parser("merge")
    merge.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    merge.add_argument(
        "--review-directory",
        type=Path,
        default=DEFAULT_BATCH_DIRECTORY,
    )
    merge.add_argument("--output", type=Path)
    merge.add_argument("--allow-overwrite", action="store_true")
    merge.set_defaults(func=command_merge)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
