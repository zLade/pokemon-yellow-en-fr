#!/usr/bin/env python3
"""Seed the canonical EN2 catalogue from the pinned fidelity inventories.

This is deliberately a *seed* generator.  It may copy readable 2015 English
into ``english_v2`` only as an explicitly unreviewed candidate.  Every seeded
row remains ``pending`` and the generator refuses to overwrite an existing
catalogue unless ``--force`` is supplied.

The source topology has several traps which are made explicit here:

* 58 medium/low alignments plus five known false-high alignments require a
  source-adjudication row (63 stable keys in total);
* eight English targets own more than one Chinese source record;
* two of those targets require pointer-specific English variants;
* one shifted move-table target requires a reviewed pointer-specific split;
* four are split by an already modelled restoration pointer;
* two safely share one payload; and
* three pairs of 2015 English source strings intentionally overlap because a
  shorter entry aliases the suffix of a longer entry.

No ROM is read and no translation is claimed to have been reviewed.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "data" / "source" / "chinese-english-fidelity"

DEFAULT_ALIGNMENT = SOURCE_DIR / "chinese_english_alignment.csv"
DEFAULT_RECORDS = SOURCE_DIR / "chinese_records.csv"
DEFAULT_POINTER_ALIGNMENT = SOURCE_DIR / "pointer_alignment.csv"
DEFAULT_REMOVED_DIALOGUES = SOURCE_DIR / "dialogues_removed_from_english.csv"
DEFAULT_TRANSLATION_BASE = ROOT / "traduction_base.csv"
DEFAULT_DIALOGUES = ROOT / "LISTE_EXHAUSTIVE_DIALOGUES.csv"
DEFAULT_OUTPUT_DIR = ROOT / "locales" / "en-US"

EXPECTED_MAIN_ROWS = 1844
EXPECTED_RESTORED_ROWS = 85
EXPECTED_CATALOG_ROWS = EXPECTED_MAIN_ROWS + EXPECTED_RESTORED_ROWS
EXPECTED_MAIN_DIALOGUES = 970
EXPECTED_DIALOGUES = 1055
EXPECTED_POKEDEX_ROWS = 159
EXPECTED_NON_DIALOGUE_MAIN_ROWS = 874
EXPECTED_NON_HIGH_ROWS = 58
EXPECTED_ADJUDICATION_ROWS = 63
EXPECTED_MULTI_SOURCE_ROWS = 8
EXPECTED_POINTER_VARIANT_ROWS = 7
EXPECTED_STORAGE_OVERLAPS = 3


# These five entries look high-confidence in the mechanical alignment, but a
# structural review proves that the apparent ownership is misleading.
FALSE_HIGH_KEYS = frozenset(
    {
        "MAIN:0x03499D",
        "MAIN:0x039D74",
        "MAIN:0x039DA8",
        "MAIN:0x039DE5",
        "MAIN:0x03F033",
    }
)

# Two shared 2015 targets conflate genuinely different messages and therefore
# need one future EN2 payload per pointer reference.
POINTER_VARIANT_KEYS = frozenset(
    {"MAIN:0x0302FA", "MAIN:0x031A15"}
)

# This move-table row is not mechanically multi-source because the 2015
# English pointers are shifted.  The reviewed Chinese table proves that Curse
# and Strength share the same English storage target and require two payloads.
RECOVERED_POINTER_VARIANT_RECORDS: Mapping[str, tuple[str, ...]] = {
    "MAIN:0x03162C": ("526", "527"),
}

# For these four multi-source targets, one pointer has already become an
# independent RESTORED row.  The MAIN row owns the one remaining reference.
RESTORATION_SPLIT_KEYS = frozenset(
    {
        "MAIN:0x03499D",
        "MAIN:0x039D74",
        "MAIN:0x039DA8",
        "MAIN:0x039DE5",
    }
)

# These targets intentionally share a payload: buy/sell use the same quantity
# prompt, and both fossil references contain the same Chinese wording.
SAFE_SHARED_KEYS = frozenset(
    {"MAIN:0x0308E9", "MAIN:0x031BBC"}
)

EXPECTED_MULTI_SOURCE_KEYS = (
    POINTER_VARIANT_KEYS | RESTORATION_SPLIT_KEYS | SAFE_SHARED_KEYS
)

EXPECTED_UNALIGNED_NON_DIALOGUE_KEYS = frozenset(
    {
        "MAIN:0x0310FB",
        "MAIN:0x031A0F",
        "MAIN:0x031E6A",
        "MAIN:0x035F75",
        "MAIN:0x03656D",
        "MAIN:0x0368F1",
    }
)

EXPECTED_UNALIGNED_DIALOGUE_KEYS = frozenset(
    {
        "MAIN:0x034927",
        "MAIN:0x034C03",
        "MAIN:0x037A51",
        "MAIN:0x037AB1",
        "MAIN:0x03804B",
        "MAIN:0x038445",
        "MAIN:0x03D088",
        "MAIN:0x03F27B",
        "MAIN:0x03F2EE",
    }
)

# Manually reviewed source ownership for the six non-dialogue entries which
# have no automatic alignment row.  The first three point directly at compact
# glyph payloads not represented as ChineseRecord objects.  The final three
# use pinned Unicode records; 0x0368F1 owns only the first proposition of its
# larger record.
MANUAL_DIRECT_SOURCES = {
    "MAIN:0x0310FB": {
        "pointer_reference": "0x030F99",
        "chinese_offset": "0x0310FB",
        "chinese_text": "火花",
    },
    "MAIN:0x031A0F": {
        "pointer_reference": "0x03196F",
        "chinese_offset": "0x031A0F",
        "chinese_text": "没有东西",
    },
    "MAIN:0x031E6A": {
        "pointer_reference": "0x031DF4",
        "chinese_offset": "0x031E6A",
        "chinese_text": "小茂",
    },
}

MANUAL_RECORD_SOURCES = {
    "MAIN:0x035F75": {
        "pointer_reference": "0x0300A1",
        "record_index": "59",
        "fragment": "",
    },
    "MAIN:0x03656D": {
        "pointer_reference": "0x034AF9",
        "record_index": "1063",
        "fragment": "",
    },
    "MAIN:0x0368F1": {
        "pointer_reference": "0x034B51",
        "record_index": "1107",
        "fragment": "最近幽灵塔里好象出现幽灵...",
    },
}

EXPECTED_MANUAL_SOURCE_KEYS = frozenset(
    set(MANUAL_DIRECT_SOURCES) | set(MANUAL_RECORD_SOURCES)
)

# (owner, suffix alias).  Bounds are derived and verified from source_length;
# only the reviewed relationships are declared here.
STORAGE_OVERLAP_PAIRS = (
    ("MAIN:0x034D08", "MAIN:0x034D3A"),
    ("MAIN:0x03A9EA", "MAIN:0x03A9F7"),
    ("MAIN:0x03ABAC", "MAIN:0x03ABCB"),
)


CATALOG_FIELDS = (
    "stable_key",
    "record_type",
    "entry_index",
    "dialogue_id",
    "category",
    "source_offset_or_pointer",
    "script_line",
    "pointer_references",
    "selected_pointer_references",
    "layout",
    "speaker",
    "chinese_record_indexes",
    "chinese_offsets",
    "chinese_text",
    "english_2015_storage",
    "english_2015",
    "french_v2_gloss",
    "english_v2",
    "editorial_origin",
    "alignment_method",
    "alignment_confidence",
    "source_resolution",
    "review_status",
    "encoded_length",
    "source_capacity_bytes",
    "compression",
    "compression_justification",
    "fidelity_comment",
    "secondary_french_provenance",
    "multi_source_mode",
    "pointer_variant_count",
    "storage_overlap_group",
    "storage_overlap_role",
)

ADJUDICATION_FIELDS = (
    "stable_key",
    "entry_index",
    "issue_kind",
    "alignment_method",
    "alignment_confidence",
    "candidate_pointer_references",
    "candidate_chinese_record_indexes",
    "candidate_chinese_offsets",
    "candidate_chinese_text",
    "selected_source_method",
    "selected_pointer_references",
    "selected_chinese_record_indexes",
    "selected_chinese_offsets",
    "selected_chinese_text",
    "resolution_status",
    "review_status",
    "note",
)

POINTER_VARIANT_FIELDS = (
    "variant_key",
    "stable_key",
    "entry_index",
    "pointer_reference_hex",
    "chinese_record_index",
    "chinese_offset_hex",
    "chinese_text",
    "shared_english_2015_target",
    "english_2015",
    "english_v2",
    "editorial_origin",
    "review_status",
    "fidelity_comment",
)

OVERLAP_FIELDS = (
    "overlap_group",
    "owner_key",
    "alias_key",
    "overlap_start_hex",
    "overlap_end_exclusive_hex",
    "overlap_bytes",
    "relationship",
    "structural_status",
    "note",
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _require_unique(
    rows: Sequence[Mapping[str, str]], field: str, label: str
) -> dict[str, Mapping[str, str]]:
    result: dict[str, Mapping[str, str]] = {}
    for row in rows:
        key = row[field]
        if not key:
            raise ValueError(f"{label}: empty {field}")
        if key in result:
            raise ValueError(f"{label}: duplicate {field}={key}")
        result[key] = row
    return result


def _main_key(offset_hex: str) -> str:
    return f"MAIN:0x{int(offset_hex, 16):06X}"


def _parts(value: str) -> list[str]:
    return value.split() if value else []


def _clean_chinese(value: str) -> str:
    return value.strip()


def _readable_english_seed(storage: str, text: str) -> str:
    """Return a byte-safe unreviewed seed, or empty for graphical residue."""
    if storage != "ascii" or not text:
        return ""
    if re.search(r"<[0-9A-F]+>", text):
        return ""
    try:
        text.encode("ascii")
    except UnicodeEncodeError:
        return ""
    return text


def _encoded_seed_length(text: str) -> str:
    return str(len(text.encode("ascii"))) if text else ""


def _record_matches_by_text(
    text: str,
    records: Sequence[Mapping[str, str]],
) -> list[Mapping[str, str]]:
    wanted = _clean_chinese(text)
    if not wanted:
        return []
    return [
        row
        for row in records
        if _clean_chinese(row["chinese_text"]) == wanted
    ]


def _multi_source_tuples(
    alignment: Mapping[str, str],
    records_by_index: Mapping[str, Mapping[str, str]],
) -> list[dict[str, str]]:
    references = _parts(alignment["pointer_references"])
    indexes = _parts(alignment["chinese_record_indexes"])
    offsets = _parts(alignment["chinese_offsets"])
    if not (len(references) == len(indexes) == len(offsets)):
        raise ValueError(
            f"{alignment['english_offset_hex']}: multi-source mapping: "
            "pointer/record/offset correspondence is not one-to-one"
        )
    result: list[dict[str, str]] = []
    for reference, index, offset in zip(references, indexes, offsets):
        record = records_by_index.get(index)
        if record is None:
            raise ValueError(f"Unknown Chinese record: {index}")
        if int(record["start_hex"], 16) != int(offset, 16):
            raise ValueError(
                f"record {index}: offset {record['start_hex']} != {offset}"
            )
        result.append(
            {
                "pointer_reference": reference,
                "record_index": index,
                "chinese_offset": offset,
                "chinese_text": _clean_chinese(record["chinese_text"]),
            }
        )
    return result


def _restored_source_map(
    removed_rows: Sequence[Mapping[str, str]],
    pointer_rows: Sequence[Mapping[str, str]],
    restored_keys: Iterable[str],
) -> dict[str, dict[str, str]]:
    removed_by_ref = _require_unique(
        removed_rows, "pointer_reference_hex", "removed dialogues"
    )
    pointer_by_ref = _require_unique(
        pointer_rows, "pointer_reference_hex", "pointer alignment"
    )
    result: dict[str, dict[str, str]] = {}
    for key in restored_keys:
        reference = key.removeprefix("RESTORED:")
        source = removed_by_ref.get(reference) or pointer_by_ref.get(reference)
        if source is None:
            raise ValueError(f"{key}: no structural Chinese source")
        result[key] = {
            "record_index": source["chinese_record_index"],
            "chinese_offset": source.get("chinese_offset_hex")
            or source.get("chinese_target_hex", ""),
            "chinese_text": _clean_chinese(source["chinese_text"]),
        }
    return result


def _manual_source_map(
    records_by_index: Mapping[str, Mapping[str, str]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for key, source in MANUAL_DIRECT_SOURCES.items():
        result[key] = {
            "pointer_reference": source["pointer_reference"],
            "record_index": "",
            "chinese_offset": source["chinese_offset"],
            "chinese_text": source["chinese_text"],
            "selected_source_method": "reviewed_manual_direct_pointer",
        }
    for key, source in MANUAL_RECORD_SOURCES.items():
        record = records_by_index.get(source["record_index"])
        if record is None:
            raise ValueError(
                f"{key}: missing manual Chinese record {source['record_index']}"
            )
        record_text = _clean_chinese(record["chinese_text"])
        fragment = source["fragment"]
        if fragment:
            if not record_text.startswith(fragment):
                raise ValueError(
                    f"{key}: manual fragment does not match record "
                    f"{source['record_index']}"
                )
            selected_text = fragment
            method = "reviewed_manual_record_fragment"
        else:
            selected_text = record_text
            method = "reviewed_manual_record"
        result[key] = {
            "pointer_reference": source["pointer_reference"],
            "record_index": source["record_index"],
            "chinese_offset": record["start_hex"],
            "chinese_text": selected_text,
            "selected_source_method": method,
        }
    if set(result) != EXPECTED_MANUAL_SOURCE_KEYS:
        raise ValueError('Incomplete manual source resolutions')
    return result


def _overlap_rows(
    alignments_by_key: Mapping[str, Mapping[str, str]],
) -> tuple[list[dict[str, str]], dict[str, tuple[str, str]]]:
    rows: list[dict[str, str]] = []
    annotations: dict[str, tuple[str, str]] = {}
    for number, (owner_key, alias_key) in enumerate(
        STORAGE_OVERLAP_PAIRS, start=1
    ):
        owner = alignments_by_key[owner_key]
        alias = alignments_by_key[alias_key]
        owner_start = int(owner["english_offset_hex"], 16)
        alias_start = int(alias["english_offset_hex"], 16)
        owner_end = owner_start + int(owner["source_length"])
        alias_end = alias_start + int(alias["source_length"])
        overlap_start = max(owner_start, alias_start)
        overlap_end = min(owner_end, alias_end)
        if overlap_start >= overlap_end:
            raise ValueError(f'Missing declared overlap: {owner_key}/{alias_key}')
        if overlap_start != alias_start or overlap_end != alias_end:
            raise ValueError(
                f'{owner_key}/{alias_key}: alias is not the expected suffix'
            )
        group = f"storage-overlap-{number:02d}"
        rows.append(
            {
                "overlap_group": group,
                "owner_key": owner_key,
                "alias_key": alias_key,
                "overlap_start_hex": f"0x{overlap_start:06X}",
                "overlap_end_exclusive_hex": f"0x{overlap_end:06X}",
                "overlap_bytes": str(overlap_end - overlap_start),
                "relationship": "alias_is_exact_suffix_of_owner",
                "structural_status": "declared_source_storage_fact",
                "note": (
                    "The short payload already aliased the suffix of the longer "
                    "payload in the 2015 English ROM; future edits must "
                    "relocate them or preserve compatible bytes."
                ),
            }
        )
        annotations[owner_key] = (group, "owner")
        annotations[alias_key] = (group, "suffix_alias")
    return rows, annotations


def _adjudication_issue(
    key: str,
    alignment: Mapping[str, str],
    has_dialogue_overlay: bool,
) -> str:
    if key in RESTORATION_SPLIT_KEYS:
        return "false_high_multi_source_restoration_split"
    if key in FALSE_HIGH_KEYS:
        return "false_high_source_ownership"
    method = alignment["alignment_method"]
    confidence = alignment["alignment_confidence"]
    if method == "unaligned":
        return (
            "unaligned_dialogue_resolved_by_inventory"
            if has_dialogue_overlay
            else "unaligned_non_dialogue"
        )
    return f"{confidence}_confidence_{method}"


def build_catalog_bundle(
    *,
    alignment_path: Path = DEFAULT_ALIGNMENT,
    records_path: Path = DEFAULT_RECORDS,
    pointer_alignment_path: Path = DEFAULT_POINTER_ALIGNMENT,
    removed_dialogues_path: Path = DEFAULT_REMOVED_DIALOGUES,
    translation_base_path: Path = DEFAULT_TRANSLATION_BASE,
    dialogues_path: Path = DEFAULT_DIALOGUES,
) -> dict[str, list[dict[str, str]]]:
    alignment_rows = _read_csv(alignment_path)
    record_rows = _read_csv(records_path)
    pointer_rows = _read_csv(pointer_alignment_path)
    removed_rows = _read_csv(removed_dialogues_path)
    base_rows = _read_csv(translation_base_path)
    dialogue_rows = _read_csv(dialogues_path)

    if len(alignment_rows) != EXPECTED_MAIN_ROWS:
        raise ValueError(
            f"{len(alignment_rows)} main alignments, "
            f"{EXPECTED_MAIN_ROWS} expected"
        )
    if len(base_rows) != EXPECTED_MAIN_ROWS:
        raise ValueError(
            f"{len(base_rows)} traduction_base entries, "
            f"{EXPECTED_MAIN_ROWS} expected"
        )
    if len(dialogue_rows) != EXPECTED_DIALOGUES:
        raise ValueError(
            f"{len(dialogue_rows)} dialogues, {EXPECTED_DIALOGUES} expected"
        )

    expected_indexes = [str(index) for index in range(1, EXPECTED_MAIN_ROWS + 1)]
    if [row["entry_index"] for row in alignment_rows] != expected_indexes:
        raise ValueError('Main entry_index values are not sequential')

    base_by_offset = _require_unique(base_rows, "offset_hex", "traduction_base")
    records_by_index = _require_unique(record_rows, "record_index", "Chinese records")
    dialogues_by_key = _require_unique(dialogue_rows, "stable_key", "dialogues")
    main_dialogues = {
        key: row
        for key, row in dialogues_by_key.items()
        if key.startswith("MAIN:")
    }
    restored_dialogues = {
        key: row
        for key, row in dialogues_by_key.items()
        if key.startswith("RESTORED:")
    }
    if len(main_dialogues) != EXPECTED_MAIN_DIALOGUES:
        raise ValueError(
            f"{len(main_dialogues)} MAIN dialogues, "
            f"{EXPECTED_MAIN_DIALOGUES} expected"
        )
    if len(restored_dialogues) != EXPECTED_RESTORED_ROWS:
        raise ValueError(
            f"{len(restored_dialogues)} RESTORED dialogues, "
            f"{EXPECTED_RESTORED_ROWS} expected"
        )

    alignments_by_key: dict[str, Mapping[str, str]] = {}
    for alignment in alignment_rows:
        key = _main_key(alignment["english_offset_hex"])
        if key in alignments_by_key:
            raise ValueError(f"Duplicate main offset: {key}")
        base = base_by_offset.get(alignment["english_offset_hex"])
        if base is None:
            raise ValueError(f'{key}: missing from traduction_base')
        if base["max_len"] != alignment["source_length"]:
            raise ValueError(f"{key}: inconsistent capacity")
        if base["layout"] != alignment["layout"]:
            raise ValueError(f"{key}: inconsistent layout")
        alignments_by_key[key] = alignment

    unknown_dialogues = set(main_dialogues) - set(alignments_by_key)
    if unknown_dialogues:
        raise ValueError(
            "MAIN dialogues without a main entry: "
            + ", ".join(sorted(unknown_dialogues))
        )

    multi_source = {
        key: alignment
        for key, alignment in alignments_by_key.items()
        if len(_parts(alignment["chinese_record_indexes"])) > 1
    }
    if len(multi_source) != EXPECTED_MULTI_SOURCE_ROWS:
        raise ValueError(
            f"{len(multi_source)} multi-source targets, "
            f"{EXPECTED_MULTI_SOURCE_ROWS} expected"
        )
    if set(multi_source) != EXPECTED_MULTI_SOURCE_KEYS:
        raise ValueError(
            "Multi-source classification changed: "
            f"{sorted(multi_source)}"
        )

    non_high_keys = {
        key
        for key, alignment in alignments_by_key.items()
        if alignment["alignment_confidence"] != "high"
    }
    if len(non_high_keys) != EXPECTED_NON_HIGH_ROWS:
        raise ValueError(
            f"{len(non_high_keys)} non-high alignments, "
            f"{EXPECTED_NON_HIGH_ROWS} expected"
        )
    unaligned_keys = {
        key
        for key, alignment in alignments_by_key.items()
        if alignment["alignment_method"] == "unaligned"
    }
    if (
        unaligned_keys & set(main_dialogues)
        != EXPECTED_UNALIGNED_DIALOGUE_KEYS
        or unaligned_keys - set(main_dialogues)
        != EXPECTED_UNALIGNED_NON_DIALOGUE_KEYS
    ):
        raise ValueError(
            f'The classification of the 15 missing alignments changed: {sorted(unaligned_keys)}'
        )
    adjudication_keys = non_high_keys | FALSE_HIGH_KEYS
    if len(adjudication_keys) != EXPECTED_ADJUDICATION_ROWS:
        raise ValueError(
            f"{len(adjudication_keys)} adjudications, "
            f"{EXPECTED_ADJUDICATION_ROWS} expected"
        )

    overlap_rows, overlap_annotations = _overlap_rows(alignments_by_key)
    restored_sources = _restored_source_map(
        removed_rows, pointer_rows, restored_dialogues
    )
    manual_sources = _manual_source_map(records_by_index)
    restored_references = {
        key.removeprefix("RESTORED:") for key in restored_dialogues
    }

    catalog: list[dict[str, str]] = []
    adjudications: list[dict[str, str]] = []
    pointer_variants: list[dict[str, str]] = []

    for alignment in alignment_rows:
        key = _main_key(alignment["english_offset_hex"])
        base = base_by_offset[alignment["english_offset_hex"]]
        dialogue = main_dialogues.get(key)
        source_records = _parts(alignment["chinese_record_indexes"])
        source_offsets = _parts(alignment["chinese_offsets"])
        source_references = _parts(alignment["pointer_references"])
        selected_records = list(source_records)
        selected_offsets = list(source_offsets)
        selected_references = list(source_references)
        multi_mode = ""
        pointer_variant_count = ""

        if key in multi_source:
            tuples = _multi_source_tuples(alignment, records_by_index)
            if key in POINTER_VARIANT_KEYS:
                multi_mode = "pointer_variant_split"
                pointer_variant_count = str(len(tuples))
                for item in tuples:
                    pointer_variants.append(
                        {
                            "variant_key": (
                                f"{key}@{item['pointer_reference']}"
                            ),
                            "stable_key": key,
                            "entry_index": alignment["entry_index"],
                            "pointer_reference_hex": item["pointer_reference"],
                            "chinese_record_index": item["record_index"],
                            "chinese_offset_hex": item["chinese_offset"],
                            "chinese_text": item["chinese_text"],
                            "shared_english_2015_target": alignment[
                                "english_offset_hex"
                            ],
                            "english_2015": alignment["english_text"],
                            "english_v2": "",
                            "editorial_origin": "untranslated_pointer_variant",
                            "review_status": "pending",
                            "fidelity_comment": (
                                "The 2015 English ROM shares storage for semantically distinct "
                                "Chinese messages; translate this "
                                "variant before compilation."
                            ),
                        }
                    )
            elif key in RESTORATION_SPLIT_KEYS:
                multi_mode = "restored_reference_split"
                remaining = [
                    item
                    for item in tuples
                    if item["pointer_reference"] not in restored_references
                ]
                restored = [
                    item
                    for item in tuples
                    if item["pointer_reference"] in restored_references
                ]
                if len(remaining) != 1 or len(restored) != 1:
                    raise ValueError(
                        f"{key}: MAIN/RESTORED split is not one-to-one"
                    )
                selected_records = [remaining[0]["record_index"]]
                selected_offsets = [remaining[0]["chinese_offset"]]
                selected_references = [remaining[0]["pointer_reference"]]
                if dialogue and _clean_chinese(
                    dialogue["chinese_text"]
                ) != remaining[0]["chinese_text"]:
                    raise ValueError(
                        f'{key}: dialogue overlay does not match the remaining MAIN source'
                    )
            elif key in SAFE_SHARED_KEYS:
                multi_mode = "safe_shared_payload"
            else:  # pragma: no cover - guarded by the classification gate
                raise ValueError(f"{key}: unclassified multi-source target")

        chinese_text = _clean_chinese(alignment["chinese_text"])
        source_resolution = alignment["alignment_method"]
        if dialogue:
            chinese_text = _clean_chinese(dialogue["chinese_text"])
            source_resolution = "dialogue_inventory_overlay"
            # The reviewed dialogue inventory is an overlay, not merely a
            # fallback for empty alignments.  A unique Unicode match must also
            # replace a misleading mechanical owner (notably 0x03F033).
            matches = _record_matches_by_text(chinese_text, record_rows)
            if len(matches) == 1:
                match = matches[0]
                selected_records = [match["record_index"]]
                selected_offsets = [match["start_hex"]]
                selected_references = _parts(match["pointer_references"])
        if key in RESTORATION_SPLIT_KEYS:
            source_resolution = "restoration_topology_and_dialogue_overlay"
        elif key in POINTER_VARIANT_KEYS:
            source_resolution = "pointer_variants_declared"
        elif key in SAFE_SHARED_KEYS:
            source_resolution = "safe_shared_source_declared"
        manual_source = manual_sources.get(key)
        if manual_source:
            selected_records = (
                [manual_source["record_index"]]
                if manual_source["record_index"]
                else []
            )
            selected_offsets = [manual_source["chinese_offset"]]
            selected_references = [manual_source["pointer_reference"]]
            chinese_text = manual_source["chinese_text"]
            source_resolution = "reviewed_manual/direct"

        english_seed = _readable_english_seed(
            alignment["english_storage"], alignment["english_text"]
        )
        # A single seed would falsely imply that one translation can serve all
        # pointer-specific variants.  Those reviewed texts live in
        # pointer_variants.csv.
        if key in POINTER_VARIANT_KEYS:
            english_seed = ""
        editorial_origin = (
            "english_2015_unreviewed_seed"
            if english_seed
            else "untranslated_pending"
        )
        overlap_group, overlap_role = overlap_annotations.get(key, ("", ""))

        if dialogue:
            category = dialogue["category"]
            dialogue_id = dialogue["id"]
            speaker = dialogue["speaker"]
            french_text = dialogue["french_reference_text"]
            french_provenance = dialogue["translation_history"]
            if dialogue["layout"] != alignment["layout"]:
                raise ValueError(f"{key}: inconsistent dialogue layout")
        else:
            category = (
                "Pokédex"
                if alignment["layout"] == "pokedex_13x4"
                else "Raw text"
                if alignment["layout"] == "raw"
                else "Ordinary text"
            )
            dialogue_id = ""
            speaker = ""
            french_text = base["fr_text"]
            french_provenance = "French v2 secondary gloss only"

        catalog_row = {
            "stable_key": key,
            "record_type": "MAIN",
            "entry_index": alignment["entry_index"],
            "dialogue_id": dialogue_id,
            "category": category,
            "source_offset_or_pointer": alignment["english_offset_hex"],
            "script_line": alignment["script_line"],
            "pointer_references": " ".join(source_references),
            "selected_pointer_references": " ".join(selected_references),
            "layout": alignment["layout"],
            "speaker": speaker,
            "chinese_record_indexes": " ".join(selected_records),
            "chinese_offsets": " ".join(selected_offsets),
            "chinese_text": chinese_text,
            "english_2015_storage": alignment["english_storage"],
            "english_2015": alignment["english_text"],
            "french_v2_gloss": french_text,
            "english_v2": english_seed,
            "editorial_origin": editorial_origin,
            "alignment_method": alignment["alignment_method"],
            "alignment_confidence": alignment["alignment_confidence"],
            "source_resolution": source_resolution,
            "review_status": "pending",
            "encoded_length": _encoded_seed_length(english_seed),
            "source_capacity_bytes": base["max_len"],
            "compression": "",
            "compression_justification": "",
            "fidelity_comment": alignment["review_note"],
            "secondary_french_provenance": french_provenance,
            "multi_source_mode": multi_mode,
            "pointer_variant_count": pointer_variant_count,
            "storage_overlap_group": overlap_group,
            "storage_overlap_role": overlap_role,
        }
        catalog.append(catalog_row)

        if key in adjudication_keys:
            if dialogue and chinese_text:
                selected_method = "dialogue_inventory_overlay"
                resolution_status = "source_text_resolved_pending_editorial_review"
            elif selected_records:
                selected_method = "mechanical_alignment_candidate"
                resolution_status = "pending_source_adjudication"
            else:
                selected_method = "unresolved"
                resolution_status = "pending_missing_source"
            if key in RESTORATION_SPLIT_KEYS:
                selected_method = "restoration_topology_and_dialogue_inventory"
                resolution_status = "source_text_resolved_pending_editorial_review"
            elif manual_source:
                selected_method = manual_source["selected_source_method"]
                resolution_status = "source_text_resolved_manual"
            adjudications.append(
                {
                    "stable_key": key,
                    "entry_index": alignment["entry_index"],
                    "issue_kind": _adjudication_issue(
                        key, alignment, dialogue is not None
                    ),
                    "alignment_method": alignment["alignment_method"],
                    "alignment_confidence": alignment["alignment_confidence"],
                    "candidate_pointer_references": alignment[
                        "pointer_references"
                    ],
                    "candidate_chinese_record_indexes": alignment[
                        "chinese_record_indexes"
                    ],
                    "candidate_chinese_offsets": alignment["chinese_offsets"],
                    "candidate_chinese_text": _clean_chinese(
                        alignment["chinese_text"]
                    ),
                    "selected_source_method": selected_method,
                    "selected_pointer_references": " ".join(
                        selected_references
                    ),
                    "selected_chinese_record_indexes": " ".join(
                        selected_records
                    ),
                    "selected_chinese_offsets": " ".join(selected_offsets),
                    "selected_chinese_text": chinese_text,
                    "resolution_status": resolution_status,
                    "review_status": "pending",
                    "note": (
                        "Source structure only; EN2 wording has not been "
                        "translated or reviewed."
                    ),
                }
            )

    for key, record_indexes in RECOVERED_POINTER_VARIANT_RECORDS.items():
        alignment = alignments_by_key[key]
        for record_index in record_indexes:
            record = records_by_index[record_index]
            references = _parts(record["pointer_references"])
            if len(references) != 1:
                raise ValueError(
                    f'{key}: recovered variant does not have a unique pointer'
                )
            pointer_reference = references[0]
            pointer_variants.append(
                {
                    "variant_key": f"{key}@{pointer_reference}",
                    "stable_key": key,
                    "entry_index": alignment["entry_index"],
                    "pointer_reference_hex": pointer_reference,
                    "chinese_record_index": record_index,
                    "chinese_offset_hex": record["pointer_targets"],
                    "chinese_text": _clean_chinese(record["chinese_text"]),
                    "shared_english_2015_target": alignment[
                        "english_offset_hex"
                    ],
                    "english_2015": alignment["english_text"],
                    "english_v2": "",
                    "editorial_origin": "untranslated_pointer_variant",
                    "review_status": "pending",
                    "fidelity_comment": (
                        "The 2015 English table shifts this move-name "
                        "pointer; translate this reviewed Chinese variant "
                        "before compilation."
                    ),
                }
            )

    for key, dialogue in sorted(
        restored_dialogues.items(),
        key=lambda item: int(item[1]["id"].removeprefix("D")),
    ):
        source = restored_sources[key]
        if _clean_chinese(dialogue["chinese_text"]) != source[
            "chinese_text"
        ]:
            raise ValueError(f'{key}: inconsistent restored Chinese text')
        catalog.append(
            {
                "stable_key": key,
                "record_type": "RESTORED",
                "entry_index": "",
                "dialogue_id": dialogue["id"],
                "category": dialogue["category"],
                "source_offset_or_pointer": dialogue["source_offset_or_pointer"],
                "script_line": "",
                "pointer_references": dialogue["source_offset_or_pointer"],
                "selected_pointer_references": dialogue[
                    "source_offset_or_pointer"
                ],
                "layout": dialogue["layout"],
                "speaker": dialogue["speaker"],
                "chinese_record_indexes": source["record_index"],
                "chinese_offsets": source["chinese_offset"],
                "chinese_text": source["chinese_text"],
                "english_2015_storage": "absent_or_wrong_pointer",
                "english_2015": dialogue[
                    "english_2015"
                ],
                "french_v2_gloss": dialogue["french_reference_text"],
                "english_v2": "",
                "editorial_origin": "untranslated_restoration_pending",
                "alignment_method": "restored_pointer_inventory",
                "alignment_confidence": dialogue["alignment_confidence"],
                "source_resolution": "restored_source_inventory",
                "review_status": "pending",
                "encoded_length": "",
                "source_capacity_bytes": "",
                "compression": "",
                "compression_justification": "",
                "fidelity_comment": (
                    "Independent EN2 payload required; never compile the "
                    "French restoration text."
                ),
                "secondary_french_provenance": dialogue[
                    "translation_history"
                ],
                "multi_source_mode": "restored_payload",
                "pointer_variant_count": "",
                "storage_overlap_group": "",
                "storage_overlap_role": "",
            }
        )

    bundle = {
        "catalog.csv": catalog,
        "source_adjudications.csv": adjudications,
        "pointer_variants.csv": pointer_variants,
        "storage_overlaps.csv": overlap_rows,
    }
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: Mapping[str, Sequence[Mapping[str, str]]]) -> None:
    catalog = bundle["catalog.csv"]
    adjudications = bundle["source_adjudications.csv"]
    variants = bundle["pointer_variants.csv"]
    overlaps = bundle["storage_overlaps.csv"]

    if len(catalog) != EXPECTED_CATALOG_ROWS:
        raise ValueError(
            f"catalogue: {len(catalog)} rows, {EXPECTED_CATALOG_ROWS} expected"
        )
    stable_keys = [row["stable_key"] for row in catalog]
    if len(set(stable_keys)) != len(stable_keys):
        raise ValueError("catalogue: duplicate stable keys")
    type_counts = Counter(row["record_type"] for row in catalog)
    if type_counts != Counter(
        {"MAIN": EXPECTED_MAIN_ROWS, "RESTORED": EXPECTED_RESTORED_ROWS}
    ):
        raise ValueError(f"catalogue: invalid types {type_counts}")
    dialogue_count = sum(bool(row["dialogue_id"]) for row in catalog)
    if dialogue_count != EXPECTED_DIALOGUES:
        raise ValueError(
            f"catalogue: {dialogue_count} dialogues, {EXPECTED_DIALOGUES} expected"
        )
    pokedex_count = sum(row["category"] == "Pokédex" for row in catalog)
    if pokedex_count != EXPECTED_POKEDEX_ROWS:
        raise ValueError(
            f"catalogue: {pokedex_count} Pokédex, "
            f"{EXPECTED_POKEDEX_ROWS} expected"
        )
    non_dialogue_main = sum(
        row["record_type"] == "MAIN" and not row["dialogue_id"]
        for row in catalog
    )
    if non_dialogue_main != EXPECTED_NON_DIALOGUE_MAIN_ROWS:
        raise ValueError(
            f"catalogue: {non_dialogue_main} non-dialogue MAIN entries, "
            f"{EXPECTED_NON_DIALOGUE_MAIN_ROWS} expected"
        )
    if any(row["review_status"] != "pending" for row in catalog):
        raise ValueError('The seed must not mark any row as reviewed')
    if any(not row["chinese_text"] for row in catalog):
        missing = [
            row["stable_key"] for row in catalog if not row["chinese_text"]
        ]
        raise ValueError(f"catalogue: empty Chinese source {missing}")
    manual_rows = {
        row["stable_key"]: row
        for row in catalog
        if row["source_resolution"] == "reviewed_manual/direct"
    }
    if set(manual_rows) != EXPECTED_MANUAL_SOURCE_KEYS:
        raise ValueError(
            "catalogue: missing or unexpected manual resolutions: "
            f"{sorted(manual_rows)}"
        )

    if len(adjudications) != EXPECTED_ADJUDICATION_ROWS:
        raise ValueError(
            f"adjudications: {len(adjudications)}, "
            f"{EXPECTED_ADJUDICATION_ROWS} expected"
        )
    adjudication_keys = {row["stable_key"] for row in adjudications}
    expected_adjudications = {
        row["stable_key"]
        for row in catalog
        if row["record_type"] == "MAIN"
        and row["alignment_confidence"] != "high"
    } | FALSE_HIGH_KEYS
    if adjudication_keys != expected_adjudications:
        raise ValueError('Inconsistent adjudication set')
    if any(row["review_status"] != "pending" for row in adjudications):
        raise ValueError('A seed adjudication cannot be marked reviewed')

    multi_modes = {
        row["stable_key"]: row["multi_source_mode"]
        for row in catalog
        if row["record_type"] == "MAIN" and row["multi_source_mode"]
    }
    expected_modes = {
        **{key: "pointer_variant_split" for key in POINTER_VARIANT_KEYS},
        **{
            key: "restored_reference_split"
            for key in RESTORATION_SPLIT_KEYS
        },
        **{key: "safe_shared_payload" for key in SAFE_SHARED_KEYS},
    }
    if multi_modes != expected_modes:
        raise ValueError(f"Incomplete multi-source processing: {multi_modes}")

    if len(variants) != EXPECTED_POINTER_VARIANT_ROWS:
        raise ValueError(
            f"variants: {len(variants)}, {EXPECTED_POINTER_VARIANT_ROWS} expected"
        )
    expected_variant_keys = POINTER_VARIANT_KEYS | set(
        RECOVERED_POINTER_VARIANT_RECORDS
    )
    if {row["stable_key"] for row in variants} != expected_variant_keys:
        raise ValueError("Invalid pointer variant keys")
    if any(row["review_status"] != "pending" for row in variants):
        raise ValueError('A seed variant cannot be marked reviewed')
    if any(row["english_v2"] for row in variants):
        raise ValueError('Distinct variants must not be prefilled')

    if len(overlaps) != EXPECTED_STORAGE_OVERLAPS:
        raise ValueError(
            f"overlaps: {len(overlaps)}, "
            f"{EXPECTED_STORAGE_OVERLAPS} expected"
        )
    actual_pairs = {
        (row["owner_key"], row["alias_key"]) for row in overlaps
    }
    if actual_pairs != set(STORAGE_OVERLAP_PAIRS):
        raise ValueError("Invalid overlap pairs")


def _render_csv(
    rows: Sequence[Mapping[str, str]], fields: Sequence[str]
) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fields,
        lineterminator="\n",
        extrasaction="raise",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


OUTPUT_FIELDS = {
    "catalog.csv": CATALOG_FIELDS,
    "source_adjudications.csv": ADJUDICATION_FIELDS,
    "pointer_variants.csv": POINTER_VARIANT_FIELDS,
    "storage_overlaps.csv": OVERLAP_FIELDS,
}


def write_bundle(
    output_dir: Path,
    bundle: Mapping[str, Sequence[Mapping[str, str]]],
    *,
    force: bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    existing = [output_dir / name for name in OUTPUT_FIELDS if (output_dir / name).exists()]
    if existing and not force:
        rendered = ", ".join(str(path) for path in existing)
        raise FileExistsError(
            "Refusing to overwrite existing editorial work: "
            f"{rendered}; use --force only to regenerate the seed"
        )
    for name, fields in OUTPUT_FIELDS.items():
        (output_dir / name).write_text(
            _render_csv(bundle[name], fields), encoding="utf-8", newline=""
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alignment", type=Path, default=DEFAULT_ALIGNMENT)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument(
        "--pointer-alignment", type=Path, default=DEFAULT_POINTER_ALIGNMENT
    )
    parser.add_argument(
        "--removed-dialogues", type=Path, default=DEFAULT_REMOVED_DIALOGUES
    )
    parser.add_argument(
        "--translation-base", type=Path, default=DEFAULT_TRANSLATION_BASE
    )
    parser.add_argument("--dialogues", type=Path, default=DEFAULT_DIALOGUES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--force",
        action="store_true",
        help='explicitly overwrite the existing seed (discards EN2 edits)',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bundle = build_catalog_bundle(
        alignment_path=args.alignment,
        records_path=args.records,
        pointer_alignment_path=args.pointer_alignment,
        removed_dialogues_path=args.removed_dialogues,
        translation_base_path=args.translation_base,
        dialogues_path=args.dialogues,
    )
    write_bundle(args.output_dir, bundle, force=args.force)
    print(f"Catalogue EN2 seed: {len(bundle['catalog.csv'])} rows")
    print(
        "- MAIN/RESTORED: "
        f"{EXPECTED_MAIN_ROWS}/{EXPECTED_RESTORED_ROWS}"
    )
    print(
        "- source adjudications / pointer variants / overlaps: "
        f"{len(bundle['source_adjudications.csv'])}/"
        f"{len(bundle['pointer_variants.csv'])}/"
        f"{len(bundle['storage_overlaps.csv'])}"
    )
    print(f"Output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
