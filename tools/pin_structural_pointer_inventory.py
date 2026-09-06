#!/usr/bin/env python3
"""Pin the locale-neutral 1,912-reference pointer inventory.

The reviewed French manifest contains both structural ownership and localized
final payload data.  EN2 needs only the former.  This tool strips all French
targets/hashes, validates the fixed provenance partition, and writes a small
deterministic source artefact that can be audited without a ROM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = (
    ROOT
    / "build"
    / "private"
    / "baseline-fr-release"
    / "audits"
    / "pointer_manifest.json"
)
DEFAULT_OUTPUT = ROOT / "data" / "source" / "structural_pointer_inventory.json"

EXPECTED_RECORDS = 1912
EXPECTED_PROVENANCE = {
    "detected": 822,
    "field_verified": 967,
    "override_verified": 38,
    "restoration_verified": 85,
}
ALLOWED_FIELDS = (
    "kind",
    "reference",
    "source_row",
    "source_target",
    "pair",
    "provenance",
)


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def build_inventory(source: Path) -> dict[str, object]:
    document = json.loads(source.read_text(encoding="utf-8"))
    source_records = document.get("records")
    if not isinstance(source_records, list):
        raise ValueError("source manifest has no records list")
    records = [
        {field: row.get(field) for field in ALLOWED_FIELDS}
        for row in source_records
    ]
    if len(records) != EXPECTED_RECORDS:
        raise ValueError(f"{len(records)} pointer records instead of 1912")
    references = [row["reference"] for row in records]
    if len(set(references)) != EXPECTED_RECORDS:
        raise ValueError("pointer references are not unique")
    provenance = Counter(str(row["provenance"]) for row in records)
    if dict(provenance) != EXPECTED_PROVENANCE:
        raise ValueError(f"unexpected provenance partition: {provenance}")
    if any(
        row["kind"] == "restoration"
        and (row["source_row"] is not None or row["source_target"] is not None)
        for row in records
    ):
        raise ValueError("restoration unexpectedly owns a source row")
    if sum(row["kind"] == "restoration" for row in records) != 85:
        raise ValueError("restoration partition is not 85")
    commitment = hashlib.sha256(canonical_json(records)).hexdigest()
    return {
        "schema": "nj046-locale-neutral-pointer-inventory/v1",
        "derivation": (
            "stripped_from_reviewed_fr_v2_manifest_without_localized_"
            "targets_or_payloads"
        ),
        "source_manifest_inventory_sha256": document.get(
            "canonical_inventory", {}
        ).get("sha256"),
        "summary": {
            "records": len(records),
            "unique_references": len(set(references)),
            "restorations": 85,
            "by_provenance": dict(sorted(provenance.items())),
            "records_sha256": commitment,
        },
        "records": records,
    }


def render(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    document = build_inventory(args.source.resolve())
    expected = render(document)
    output = args.output.resolve()
    if args.check:
        if not output.is_file() or output.read_text(encoding="utf-8") != expected:
            print(f"Structural pointer inventory is stale: {output}")
            return 1
        print("Structural pointer inventory verified: 1912/1912")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(expected, encoding="utf-8")
    print(f"Wrote {output} (1912 references).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
