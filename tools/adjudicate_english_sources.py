#!/usr/bin/env python3
"""Apply the reviewed Chinese-source decisions for the 63 EN2 exceptions.

This pass reviews *source ownership only*.  It deliberately leaves every
English catalogue payload and every catalogue ``review_status`` untouched.
The mechanically generated catalogue remains reproducible; this script is
the deterministic, auditable second pass that corrects misleading physical
overlaps, records direct compact payloads, and records dialogue-inventory
decisions.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_english_catalog import (  # noqa: E402
    ADJUDICATION_FIELDS,
    CATALOG_FIELDS,
    DEFAULT_RECORDS,
    EXPECTED_ADJUDICATION_ROWS,
    build_catalog_bundle,
)


DEFAULT_ADJUDICATIONS = ROOT / "locales" / "en-US" / "source_adjudications.csv"
DEFAULT_CATALOGUE = ROOT / "locales" / "en-US" / "catalog.csv"

RESOLUTION_STATUS = "source_text_resolved_ai_review"
SOURCE_REVIEW_STATUS = "ai_source_reviewed"
CATALOGUE_SOURCE_RESOLUTION = "reviewed_source_adjudication"

CATALOGUE_SOURCE_FIELDS = (
    "selected_pointer_references",
    "chinese_record_indexes",
    "chinese_offsets",
    "chinese_text",
    "source_resolution",
)

ADJUDICATION_REVIEW_FIELDS = (
    "selected_source_method",
    "selected_pointer_references",
    "selected_chinese_record_indexes",
    "selected_chinese_offsets",
    "selected_chinese_text",
    "resolution_status",
    "review_status",
    "note",
)


@dataclass(frozen=True)
class ExplicitSelection:
    method: str
    record_indexes: tuple[str, ...]
    offsets: tuple[str, ...]
    pointer_references: tuple[str, ...]
    chinese_text: str
    proof: str


# Compact payloads excluded from ChineseRecord extraction.  The three item/UI
# rows were decoded from the pinned glyph map at the exact storage offset; the
# other three manual sources and the move-name sentinel are direct table
# payloads whose pointer slots are explicit in the pinned topology.
DIRECT_SELECTIONS: Mapping[str, ExplicitSelection] = {
    "MAIN:0x0310FB": ExplicitSelection(
        "ai_review_direct_compact_payload",
        (),
        ("0x0310FB",),
        ("0x030F99",),
        "火花",
        "direct move-name payload and its table pointer",
    ),
    "MAIN:0x0316E9": ExplicitSelection(
        "ai_review_direct_compact_payload",
        (),
        ("0x0316E9",),
        ("0x031649",),
        "无",
        "direct item-sentinel payload immediately before the Poké Ball table",
    ),
    "MAIN:0x031A0F": ExplicitSelection(
        "ai_review_direct_compact_payload",
        (),
        ("0x031A0F",),
        ("0x03196F",),
        "没有东西",
        "direct empty-inventory payload and its table pointer",
    ),
    "MAIN:0x031E6A": ExplicitSelection(
        "ai_review_direct_compact_payload",
        (),
        ("0x031E6A",),
        ("0x031DF4",),
        "小茂",
        "direct rival-name payload and its table pointer",
    ),
    "MAIN:0x034927": ExplicitSelection(
        "ai_review_direct_glyph_payload",
        (),
        ("0x034927",),
        ("0x0348DD",),
        "得到无",
        "exact pinned-glyph decode and preceding item-message pointer",
    ),
    "MAIN:0x034C03": ExplicitSelection(
        "ai_review_direct_glyph_payload",
        (),
        ("0x034C03",),
        ("0x034AE9",),
        "欢迎!",
        "exact pinned-glyph decode and preceding service-message pointer",
    ),
    "MAIN:0x03804B": ExplicitSelection(
        "ai_review_direct_menu_payload",
        (),
        ("0x03804B",),
        ("0x03801B",),
        "精灵取出精灵存放",
        "direct PC-menu payload and its table pointer",
    ),
}


# The short ASCII strings are unpointed shadow writes.  Each is covered by a
# later complete write in script.py; the complete owner is pointer-aligned to
# the Chinese record below.  Selecting the physical record underneath the
# short English offset is wrong whenever the English table packed differently.
SHADOW_OWNER_RECORDS: Mapping[str, str] = {
    "MAIN:0x0311E7": "383",   # Whip -> owner Vine Whip
    "MAIN:0x0311FF": "386",   # Bomb -> owner Seed Bomb slot
    "MAIN:0x031286": "403",   # Club -> owner Bone Club
    "MAIN:0x0312BC": "409",   # Tomb -> owner Rock Tomb
    "MAIN:0x0312F2": "416",   # Horn -> owner Megahorn
    "MAIN:0x0312FC": "417",   # Glow -> owner Tail Glow
    "MAIN:0x03145D": "464",   # Mind -> owner Calm Mind
    "MAIN:0x0314F1": "484",   # Tail -> owner Iron Tail
    "MAIN:0x0315A6": "509",   # Kiss -> owner Lovely Kiss
    "MAIN:0x0315DC": "516",   # Whip -> owner Tail Whip
}


# These pointer slots were not emitted by the mechanical English alignment,
# but ChineseRecord preserves their source pointers.  The corresponding target
# bytes establish the actual table ownership; physical-offset candidates 523
# and 525 are respectively two and one slots too early.
RECOVERED_POINTER_RECORDS: Mapping[str, str] = {
    "MAIN:0x031624": "525",  # source slot 0x0310F3: 变身
    "MAIN:0x03162C": "526",  # source slot 0x0310F5: 诅咒
}


SPECIAL_SELECTIONS: Mapping[str, ExplicitSelection] = {
    "MAIN:0x0368F1": ExplicitSelection(
        "ai_review_record_prefix",
        ("1107",),
        ("0x03523F",),
        ("0x034B51",),
        "最近幽灵塔里好象出现幽灵...",
        "first proposition of pinned record 1107, as isolated by the source inventory",
    ),
    "MAIN:0x038445": ExplicitSelection(
        "ai_review_composite_dialogue_inventory",
        ("175", "176", "177"),
        ("0x03082B", "0x03087F", "0x0308BA"),
        ("0x03018D", "0x03018F", "0x030191"),
        (
            "你好!欢迎你光临宠物精灵的世界!大家都叫我大木博士,"
            "在这世界住着被称为宠物精灵的生物!"
            "这生物被视为宠物,或使用于对战等等.而我是研究这宠物精灵的!"
            "小智,一个将属于你的故事,梦想即将开始!"
        ),
        "dialogue inventory concatenation of the three consecutive intro records",
    ),
    "MAIN:0x039D60": ExplicitSelection(
        "ai_review_glyph_record_fragment",
        ("1345",),
        ("0x039D60",),
        ("0x038349",),
        "我不会给你太好过",
        "exact pinned-glyph suffix within pointer-owned record 1345",
    ),
    "MAIN:0x03BDDA": ExplicitSelection(
        "ai_review_unpointed_physical_record_context",
        ("1583",),
        ("0x03BDC6",),
        ("0x03AF42",),
        "蓓蓓:没有我不知道的事,就连电玩里的世界也一样!这只依布就送给你吧!",
        (
            "the unpointed short English residue lies inside pinned record 1583; "
            "the pointer-owned full record is retained as source context without "
            "claiming that the residue is a faithful translation"
        ),
    ),
    "MAIN:0x03DF0D": ExplicitSelection(
        "ai_review_glyph_exact_record",
        ("1827",),
        ("0x03DF0F",),
        ("0x03CF60",),
        (
            "社长:少年!谢谢你救了我,在我最需要帮助的时候救了我!"
            "这恩情我不会忘的...对了!这礼物可不能忘了!就给你这个好吗?"
        ),
        "exact pinned-glyph payload; record 1826 was only a physical-overlap false match",
    ),
}


class SourceAdjudicationError(ValueError):
    """The reviewed source topology is incomplete or inconsistent."""


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _unique(rows: Sequence[Mapping[str, str]], field: str) -> dict[str, Mapping[str, str]]:
    result: dict[str, Mapping[str, str]] = {}
    for row in rows:
        key = row[field]
        if not key or key in result:
            raise SourceAdjudicationError(f"invalid/duplicate {field}: {key!r}")
        result[key] = row
    return result


def _parts(value: str) -> tuple[str, ...]:
    return tuple(value.split()) if value else ()


def _record_selection(
    key: str,
    record_index: str,
    records: Mapping[str, Mapping[str, str]],
    *,
    method: str,
    proof: str,
) -> ExplicitSelection:
    record = records[record_index]
    return ExplicitSelection(
        method,
        (record_index,),
        (record["start_hex"],),
        _parts(record["pointer_references"]),
        record["chinese_text"].strip(),
        proof,
    )


def build_decisions() -> dict[str, ExplicitSelection]:
    """Derive and validate exactly one reviewed decision for every exception."""
    seed = build_catalog_bundle()
    seed_adjudications = _unique(seed["source_adjudications.csv"], "stable_key")
    _record_fields, record_rows = _read_csv(DEFAULT_RECORDS)
    records = _unique(record_rows, "record_index")

    decisions: dict[str, ExplicitSelection] = {}
    for key, row in seed_adjudications.items():
        if key in DIRECT_SELECTIONS:
            selection = DIRECT_SELECTIONS[key]
        elif key in SPECIAL_SELECTIONS:
            selection = SPECIAL_SELECTIONS[key]
        elif key in SHADOW_OWNER_RECORDS:
            selection = _record_selection(
                key,
                SHADOW_OWNER_RECORDS[key],
                records,
                method="ai_review_shadow_fragment_owner",
                proof="complete pointer-owned entry that covers the short shadow write",
            )
        elif key in RECOVERED_POINTER_RECORDS:
            selection = _record_selection(
                key,
                RECOVERED_POINTER_RECORDS[key],
                records,
                method="ai_review_recovered_pointer_owner",
                proof="reviewed move-table pointer ownership, not physical byte overlap",
            )
        else:
            indexes = _parts(row["selected_chinese_record_indexes"])
            offsets = _parts(row["selected_chinese_offsets"])
            text = row["selected_chinese_text"].strip()
            if not indexes:
                raise SourceAdjudicationError(f"{key}: unclassified record-less source")
            if len(indexes) != len(offsets):
                raise SourceAdjudicationError(f"{key}: record/offset arity mismatch")
            selected_records = [records[index] for index in indexes]
            if len(indexes) != 1:
                raise SourceAdjudicationError(f"{key}: unexpected multi-record seed")
            record_text = selected_records[0]["chinese_text"].strip()
            if text != record_text:
                raise SourceAdjudicationError(
                    f"{key}: selected text is not the exact pinned record"
                )
            references = tuple(
                reference
                for record in selected_records
                for reference in _parts(record["pointer_references"])
            )
            # Record 59 is an unpointed compact record whose reviewed slot was
            # already recovered by the seed generator.
            if not references:
                references = _parts(row["selected_pointer_references"])

            if row["selected_source_method"].startswith("restoration_topology"):
                method = "ai_review_restoration_split"
                proof = "restoration topology leaves exactly this MAIN pointer owner"
            elif row["selected_source_method"] == "dialogue_inventory_overlay":
                method = "ai_review_dialogue_inventory_record"
                proof = "exact Unicode match in the exhaustive dialogue inventory"
            elif row["selected_source_method"].startswith("reviewed_manual"):
                method = "ai_review_manual_record"
                proof = "manual unaligned resolution rechecked against the pinned record"
            elif row["alignment_method"] == "exact_offset":
                method = "ai_review_exact_record"
                proof = "exact storage offset and exact pinned Unicode record"
            else:
                method = "ai_review_structural_record"
                proof = "pointer/record topology and exact pinned Unicode record"
            selection = ExplicitSelection(
                method,
                indexes,
                offsets,
                references,
                text,
                proof,
            )

        for record_index in selection.record_indexes:
            if record_index not in records:
                raise SourceAdjudicationError(f"{key}: unknown record {record_index}")
        if not selection.method or not selection.offsets or not selection.chinese_text:
            raise SourceAdjudicationError(f"{key}: incomplete reviewed selection")

        selected_records = [records[index] for index in selection.record_indexes]
        record_texts = [record["chinese_text"].strip() for record in selected_records]
        if selection.method == "ai_review_composite_dialogue_inventory":
            if "".join(record_texts) != selection.chinese_text:
                raise SourceAdjudicationError(f"{key}: invalid composite source text")
        elif selection.method in {
            "ai_review_record_prefix",
            "ai_review_glyph_record_fragment",
        }:
            if len(record_texts) != 1 or selection.chinese_text not in record_texts[0]:
                raise SourceAdjudicationError(f"{key}: invalid record fragment")
        elif selected_records and selection.method != "ai_review_unpointed_physical_record_context":
            if len(record_texts) != 1 or record_texts[0] != selection.chinese_text:
                raise SourceAdjudicationError(f"{key}: record text mismatch")

        record_references = {
            reference
            for record in selected_records
            for reference in _parts(record["pointer_references"])
        }
        if record_references and not set(selection.pointer_references).issubset(
            record_references
        ):
            raise SourceAdjudicationError(f"{key}: pointer is not owned by selected record")
        decisions[key] = selection

    if len(decisions) != EXPECTED_ADJUDICATION_ROWS:
        raise SourceAdjudicationError(
            f"{len(decisions)} decisions; expected {EXPECTED_ADJUDICATION_ROWS}"
        )
    if set(decisions) != set(seed_adjudications):
        raise SourceAdjudicationError("reviewed decision key set differs from seed")
    return decisions


def _note(key: str, selection: ExplicitSelection) -> str:
    records = " ".join(selection.record_indexes) or "N/A (direct compact payload)"
    pointers = (
        " ".join(selection.pointer_references)
        or "N/A (sequential/unpointed script segment)"
    )
    offsets = " ".join(selection.offsets)
    return (
        f"AI Chinese-source review for {key}: selected record(s) {records}, "
        f"offset(s) {offsets}, pointer reference(s) {pointers}. "
        f"Proof: {selection.proof}. English wording was not translated or reviewed."
    )


def apply_reviews(
    adjudications: Sequence[Mapping[str, str]],
    catalogue: Sequence[Mapping[str, str]],
    decisions: Mapping[str, ExplicitSelection],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    adjudication_by_key = _unique(adjudications, "stable_key")
    if set(adjudication_by_key) != set(decisions):
        raise SourceAdjudicationError("adjudication file does not contain exactly 63 keys")

    reviewed_adjudications: list[dict[str, str]] = []
    for source in adjudications:
        row = dict(source)
        selection = decisions[row["stable_key"]]
        row.update(
            {
                "selected_source_method": selection.method,
                "selected_pointer_references": " ".join(selection.pointer_references),
                "selected_chinese_record_indexes": " ".join(selection.record_indexes),
                "selected_chinese_offsets": " ".join(selection.offsets),
                "selected_chinese_text": selection.chinese_text,
                "resolution_status": RESOLUTION_STATUS,
                "review_status": SOURCE_REVIEW_STATUS,
                "note": _note(row["stable_key"], selection),
            }
        )
        reviewed_adjudications.append(row)

    catalogue_keys = [row["stable_key"] for row in catalogue]
    if len(catalogue_keys) != len(set(catalogue_keys)):
        raise SourceAdjudicationError("duplicate catalogue stable_key")
    missing = sorted(set(decisions) - set(catalogue_keys))
    if missing:
        raise SourceAdjudicationError("catalogue missing: " + ", ".join(missing))

    reviewed_catalogue: list[dict[str, str]] = []
    for source in catalogue:
        row = dict(source)
        selection = decisions.get(row["stable_key"])
        if selection is not None:
            row.update(
                {
                    "selected_pointer_references": " ".join(
                        selection.pointer_references
                    ),
                    "chinese_record_indexes": " ".join(selection.record_indexes),
                    "chinese_offsets": " ".join(selection.offsets),
                    "chinese_text": selection.chinese_text,
                    "source_resolution": CATALOGUE_SOURCE_RESOLUTION,
                }
            )
        reviewed_catalogue.append(row)

    validate_reviewed_rows(reviewed_adjudications, reviewed_catalogue, decisions)
    return reviewed_adjudications, reviewed_catalogue


def validate_reviewed_rows(
    adjudications: Sequence[Mapping[str, str]],
    catalogue: Sequence[Mapping[str, str]],
    decisions: Mapping[str, ExplicitSelection],
) -> None:
    if len(adjudications) != EXPECTED_ADJUDICATION_ROWS:
        raise SourceAdjudicationError("reviewed adjudication cardinality changed")
    for row in adjudications:
        key = row["stable_key"]
        selection = decisions[key]
        expected = {
            "selected_source_method": selection.method,
            "selected_pointer_references": " ".join(selection.pointer_references),
            "selected_chinese_record_indexes": " ".join(selection.record_indexes),
            "selected_chinese_offsets": " ".join(selection.offsets),
            "selected_chinese_text": selection.chinese_text,
            "resolution_status": RESOLUTION_STATUS,
            "review_status": SOURCE_REVIEW_STATUS,
            "note": _note(key, selection),
        }
        for field, value in expected.items():
            if row.get(field) != value:
                raise SourceAdjudicationError(f"{key}: invalid {field}")
        if "pending" in " ".join(row.values()).casefold():
            raise SourceAdjudicationError(f"{key}: pending marker remains")

    catalog_by_key = _unique(catalogue, "stable_key")
    for key, selection in decisions.items():
        row = catalog_by_key[key]
        expected = {
            "selected_pointer_references": " ".join(selection.pointer_references),
            "chinese_record_indexes": " ".join(selection.record_indexes),
            "chinese_offsets": " ".join(selection.offsets),
            "chinese_text": selection.chinese_text,
            "source_resolution": CATALOGUE_SOURCE_RESOLUTION,
            "review_status": "pending",
        }
        for field, value in expected.items():
            if row.get(field) != value:
                raise SourceAdjudicationError(f"{key}: catalogue {field} changed/invalid")


def _write_csv_atomic(
    path: Path,
    fields: Sequence[str],
    rows: Sequence[Mapping[str, str]],
) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run(adjudications_path: Path, catalogue_path: Path, *, check: bool) -> None:
    adjudication_fields, adjudications = _read_csv(adjudications_path)
    catalogue_fields, catalogue = _read_csv(catalogue_path)
    if adjudication_fields != list(ADJUDICATION_FIELDS):
        raise SourceAdjudicationError("unexpected source-adjudication schema")
    if catalogue_fields != list(CATALOG_FIELDS):
        raise SourceAdjudicationError("unexpected catalogue schema")
    decisions = build_decisions()
    reviewed_adjudications, reviewed_catalogue = apply_reviews(
        adjudications, catalogue, decisions
    )
    if check:
        if reviewed_adjudications != adjudications or reviewed_catalogue != catalogue:
            raise SourceAdjudicationError("reviewed source files are stale")
        return
    _write_csv_atomic(adjudications_path, ADJUDICATION_FIELDS, reviewed_adjudications)
    _write_csv_atomic(catalogue_path, CATALOG_FIELDS, reviewed_catalogue)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudications", type=Path, default=DEFAULT_ADJUDICATIONS)
    parser.add_argument("--catalogue", type=Path, default=DEFAULT_CATALOGUE)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run(args.adjudications.resolve(), args.catalogue.resolve(), check=args.check)
    action = "verified" if args.check else "written"
    print(f"EN2 Chinese-source adjudications {action}: {EXPECTED_ADJUDICATION_ROWS}/63")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
