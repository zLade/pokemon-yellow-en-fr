#!/usr/bin/env python3
"""Extract the NJ046 Chinese text and align it with the English patch.

The original ROM stores one 16x16 GB2312 glyph per B0-BF xx code.  Two
successive code indexes share one 64-byte NES font block: the even code is
bitplane 0 and the odd code is bitplane 1.  This is the layout selected by
the 6502 routine at file offsets 0x019A53-0x019AF6.

HZK16 is used only as a bitmap-to-Unicode lookup table.  The generated CSVs
contain Unicode and do not depend on HZK16 at runtime.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    FINAL_ROM,
    PATCH_SCRIPT,
    TRANSLATION_BASE_ROM,
    TRANSLATION_BASE_SHA256,
    apply_verified_pointer_redirects,
    csv_safe,
    detect_pointer_table_entries,
    find_structured_glyph_records,
    known_source_target_offsets,
    offset_for_cpu_addr,
    pair_for_offset,
    parse_patch_entries,
    sha256,
    source_record_len,
    source_record_text,
    structured_glyph_record_map,
    verified_all_graphical_text_records,
    verified_field_dialogue_pointer_entries,
)
from tools.glyph_text_tools import (  # noqa: E402
    FONT_BASE_OFFSET,
    glyph_slot,
)


CHINESE_ROM_SHA256 = (
    "450d40c0d648f8651ac6b42f1c094921"
    "cb2202ed420194e65271e2f7b40c65ed"
)
HZK16_SHA256 = (
    "0a757c641b211419868af188f4a90b20"
    "10fcd7620373073a8bc7c1dd848eefdf"
)
SOURCE_RECORD_COUNT = 1974
SOURCE_GLYPH_CODE_COUNT = 20832
SOURCE_PAYLOAD_SIZE = 46874
SOURCE_RECORD_FINGERPRINT = (
    "1d88a2886e601f34c80652324d909bec"
    "18d730af584448d9395a1742f989f0c1"
)
GLYPH_CODE_COUNT = 1352
# These two indexes address the protected final 64 bytes of PRG pair 8, so
# their bitmap was overwritten by common code/vectors and cannot match HZK16.
# Their intended values are nevertheless unambiguous from repeated contexts:
# 培育方法 / 赢的方法 and 沙瓦郎 / 瓦斯弹 / 双弹瓦斯.
CONTEXTUAL_GLYPH_MAP = {
    1022: "法",
    1023: "瓦",
}

GRAPHIC_CODE_RE = re.compile(r"<B[0-9A-F]{3}>")

# Complete source-side dialogue pointer bands.  The English patch deliberately
# leaves holes inside these bands (usually 0x3030), which is precisely how
# several multi-line Team Rocket and post-game exchanges disappeared.
CHINESE_DIALOGUE_POINTER_RANGES: tuple[tuple[int, int], ...] = (
    (0x033137, 0x0331ED),
    (0x038249, 0x038443),
    (0x03AE60, 0x03B056),
    (0x03CE8C, 0x03D086),
)

# Conservative, manually reviewed set of severe semantic divergences.  It
# intentionally excludes merely abbreviated or stylistically adapted lines.
REVIEWED_LARGE_DIALOGUE_DIVERGENCES: dict[int, tuple[str, str]] = {
    937: ("semantic_replacement", "L'arrivée difficile devient un défi."),
    949: ("semantic_replacement", "L'annonce d'un mariage disparaît."),
    950: ("semantic_replacement", "La demande en mariage disparaît."),
    969: ("major_omission", "Le retour chez la mère de Sacha disparaît."),
    973: ("story_rewrite", "Mewtwo est remplacé par une nouvelle quête Rocket."),
    981: ("story_rewrite", "La réouverture de la Ligue disparaît."),
    1003: ("story_rewrite", "Kamiyu/Nanjing Tech disparaît."),
    1004: ("semantic_replacement", "La confirmation de Miaouss est remplacée."),
    1009: ("wrong_character_and_story", "Kamiyu devient Eusine."),
    1011: ("story_rewrite", "Le voyage et le Pokédex deviennent un don."),
    1017: ("semantic_replacement", "L'aveu de défaite devient un adieu."),
    1018: ("semantic_replacement", "Le compliment devient une consigne."),
    1019: ("semantic_replacement", "La menace d'appeler la police disparaît."),
    1062: ("swapped_dialogue", "Échangé avec le dialogue scientifique suivant."),
    1063: ("swapped_dialogue", "Échangé avec le dialogue d'élevage précédent."),
    1066: ("broken_pointer_or_fragment", "Remplacé par un fragment puis un panneau."),
    1077: ("wrong_ability", "Coupe est remplacé par Flash."),
    1109: ("major_omission", "Le meurtre de la mère d'Osselait disparaît."),
    1119: ("story_rewrite", "Kamiyu/Nanjing Tech est remplacé par Sylphe."),
    1236: ("story_rewrite", "Le vieillard endormi devient blessé au dos."),
    1240: ("sequence_shift", "La remise du colis devient son identification."),
    1241: ("major_omission", "La demande du Prof. Chen disparaît."),
    1242: ("semantic_replacement", "Régis ne parle plus de son Pokémon."),
    1245: ("sequence_shift", "Le rêve de Chen est attribué à Régis."),
    1269: ("sequence_shift", "Le Badge Roche devient l'usage de Flash."),
    1270: ("sequence_shift", "L'explication du badge devient la CT35."),
    1271: ("sequence_shift", "La réception de la CT devient sa description."),
    1305: ("semantic_replacement", "L'invitation Rocket devient un ordre fossile."),
    1316: ("sequence_shift", "La question de Sacha devient la devise de James."),
    1317: ("sequence_shift", "Le début de la devise devient la fin de Miaouss."),
    1345: ("wrong_order", "Le troisième dresseur devient le quatrième."),
    1346: ("wrong_pointer", "La réplique devient l'obtention de Salamèche."),
    1347: ("wrong_order", "Le quatrième dresseur devient le troisième."),
    1348: ("wrong_pointer", "Le suivi de Sacha devient un autre dialogue."),
    1350: ("wrong_pointer", "La victoire sur les cinq devient le départ vers Léo."),
    1384: ("major_omission", "La collection et les 150 espèces disparaissent."),
    1406: ("world_lore_removed", "L'origine du continent de Hoenn disparaît."),
    1410: ("semantic_replacement", "Le confort à Hoenn devient une insulte."),
    1411: ("world_lore_removed", "La légende de Johto disparaît."),
    1441: ("broken_sequence", "Le massage de Sacha devient le fragment raw."),
    1442: ("sequence_shift", "Le don de Coupe devient seulement le massage."),
    1453: ("sequence_shift", "La CT24 devient tout le discours du Badge Foudre."),
    1483: ("branch_inversion", "Le refus devient l'acceptation."),
    1484: ("branch_inversion", "L'acceptation devient l'obtention."),
    1485: ("branch_inversion", "L'obtention devient le refus."),
    1579: ("developer_cameo_removed", "Le graphiste est remplacé."),
    1580: ("developer_cameo_removed", "Le scénariste est remplacé."),
    1581: ("developer_cameo_removed", "Le programmeur est remplacé."),
    1582: ("developer_cameo_removed", "Le message du boss est remplacé."),
    1640: ("major_omission", "L'identité et le but du chef Rocket disparaissent."),
    1859: ("sequence_shift", "Le Badge Marais devient la CT40."),
    1860: ("sequence_shift", "La CT40 devient sa description."),
    1963: ("semantic_replacement", "La vengeance des Rockets licenciés disparaît."),
    1964: ("sequence_shift", "La question de Sacha devient une défaite."),
    1973: ("semantic_replacement", "L'agacement de Morgane devient une leçon psy."),
    1974: ("semantic_replacement", "Le reproche devient une consigne de soin."),
}


@dataclass(frozen=True)
class ChineseRecord:
    index: int
    start: int
    end: int
    pair: int
    glyph_count: int
    text: str
    unresolved_codes: tuple[int, ...]


@dataclass(frozen=True)
class EnglishRow:
    index: int
    offset: int
    line: int
    layout: str
    source_length: int
    source_text: str
    french_text: str


def read_checked(path: Path, expected_hash: str, label: str) -> bytes:
    data = path.read_bytes()
    actual = sha256(data)
    if actual != expected_hash:
        raise ValueError(
            f"{label} non canonique: {actual} au lieu de {expected_hash}"
        )
    return data


def hzk_character(index: int) -> str:
    high = 0xA1 + index // 94
    low = 0xA1 + index % 94
    try:
        return bytes((high, low)).decode("gb2312")
    except UnicodeDecodeError:
        return f"<GB{high:02X}{low:02X}>"


def source_glyph_bitmap(rom: bytes, code: int) -> bytes:
    """Return the 32-byte row-major 1bpp bitmap selected by one text code."""
    block = code // 2
    bitplane = code & 1
    start = FONT_BASE_OFFSET + block * 64
    raw = rom[start:start + 64]
    if len(raw) != 64:
        raise ValueError(f"bloc de glyphe {code} hors ROM")

    plane_offset = bitplane * 8
    bitmap = bytearray()
    for row in range(16):
        half = row // 8
        y = row % 8
        half_data = raw[half * 32:(half + 1) * 32]
        bitmap.extend(
            (
                half_data[plane_offset + y],
                half_data[16 + plane_offset + y],
            )
        )
    return bytes(bitmap)


def build_glyph_map(
    chinese: bytes,
    hzk16: bytes,
) -> dict[int, str]:
    if len(hzk16) % 32:
        raise ValueError("taille HZK16 non multiple de 32")
    bitmap_to_index = {
        hzk16[offset:offset + 32]: offset // 32
        for offset in range(0, len(hzk16), 32)
    }
    result: dict[int, str] = {}
    unresolved: set[int] = set()
    for code in range(GLYPH_CODE_COUNT):
        index = bitmap_to_index.get(source_glyph_bitmap(chinese, code))
        if index is None:
            unresolved.add(code)
            result[code] = f"<GLYPH_{code:04d}>"
        else:
            result[code] = hzk_character(index)
    if unresolved != set(CONTEXTUAL_GLYPH_MAP):
        raise ValueError(
            "glyphes sans correspondance HZK16 inattendus: "
            f"{sorted(unresolved)}"
        )
    result.update(CONTEXTUAL_GLYPH_MAP)
    return result


def decode_source_record(
    data: bytes,
    start: int,
    end: int,
    glyph_map: dict[int, str],
) -> tuple[str, tuple[int, ...]]:
    parts: list[str] = []
    unresolved: set[int] = set()
    cursor = start
    while cursor < end:
        value = data[cursor]
        if 0xB0 <= value <= 0xBF:
            if cursor + 1 >= end:
                raise ValueError(f"code glyphique tronqué à 0x{cursor:06X}")
            code = glyph_slot(value, data[cursor + 1])
            text = glyph_map.get(code, f"<GLYPH_{code:04d}>")
            if text.startswith("<GLYPH_"):
                unresolved.add(code)
            parts.append(text)
            cursor += 2
        elif value == 0x0A:
            parts.append("\n")
            cursor += 1
        elif 0x20 <= value <= 0x7E:
            parts.append(chr(value))
            cursor += 1
        else:
            parts.append(f"<{value:02X}>")
            cursor += 1
    return "".join(parts), tuple(sorted(unresolved))


def source_records(
    chinese: bytes,
    glyph_map: dict[int, str],
) -> list[ChineseRecord]:
    raw_records = find_structured_glyph_records(chinese)
    fingerprint = hashlib.sha256(
        "\n".join(
            f"{start:06X}-{end:06X}"
            for start, end, _, _ in raw_records
        ).encode("ascii")
    ).hexdigest()
    summary = (
        len(raw_records),
        sum(item[3] for item in raw_records),
        sum(end - start for start, end, _, _ in raw_records),
        fingerprint,
    )
    expected = (
        SOURCE_RECORD_COUNT,
        SOURCE_GLYPH_CODE_COUNT,
        SOURCE_PAYLOAD_SIZE,
        SOURCE_RECORD_FINGERPRINT,
    )
    if summary != expected:
        raise ValueError(
            "inventaire chinois non canonique: "
            f"{summary!r} au lieu de {expected!r}"
        )

    result: list[ChineseRecord] = []
    for index, (start, end, pair, glyph_count) in enumerate(
        raw_records,
        start=1,
    ):
        text, unresolved = decode_source_record(
            chinese,
            start,
            end,
            glyph_map,
        )
        result.append(
            ChineseRecord(
                index,
                start,
                end,
                pair,
                glyph_count,
                text,
                unresolved,
            )
        )
    return result


def english_rows(english: bytes, script: Path) -> list[EnglishRow]:
    glyph_map = structured_glyph_record_map(
        verified_all_graphical_text_records(english)
    )
    rows: list[EnglishRow] = []
    for index, entry in enumerate(parse_patch_entries(script), start=1):
        source_length = source_record_len(
            english,
            entry.offset,
            glyph_map,
        )
        source_text = source_record_text(
            english,
            entry.offset,
            source_length,
            glyph_map,
        )
        rows.append(
            EnglishRow(
                index,
                entry.offset,
                entry.line,
                entry.layout,
                source_length,
                csv_safe(source_text),
                entry.text,
            )
        )
    return rows


def pointer_index(
    data: bytes,
    ranges: Iterable[tuple[int, int]],
) -> dict[int, int]:
    known = known_source_target_offsets(data, ranges)
    entries = detect_pointer_table_entries(
        data,
        min_run=10,
        known_offsets=known,
        min_known_ratio=0.1,
        min_known_count=1,
    )
    by_reference: dict[int, int] = {}
    for target, references in entries.items():
        for reference in references:
            previous = by_reference.setdefault(reference, target)
            if previous != target:
                raise ValueError(
                    f"pointeur 0x{reference:06X} à deux cibles"
                )
    return by_reference


def chinese_owner(
    records: list[ChineseRecord],
    target: int,
) -> ChineseRecord | None:
    owners = [
        record
        for record in records
        if record.start <= target <= record.end
    ]
    if len(owners) > 1:
        raise ValueError(f"cible chinoise 0x{target:06X} ambiguë")
    return owners[0] if owners else None


def english_owner(
    rows: list[EnglishRow],
    target: int,
) -> EnglishRow | None:
    owners = [
        row
        for row in rows
        if (
            row.source_length > 0
            and row.offset <= target < row.offset + row.source_length
        )
    ]
    if not owners:
        return None
    exact = [row for row in owners if row.offset == target]
    return min(
        exact or owners,
        key=lambda row: (row.source_length, -row.offset),
    )


def fallback_source_records(
    row: EnglishRow,
    records: list[ChineseRecord],
) -> tuple[list[ChineseRecord], str]:
    exact = [record for record in records if record.start == row.offset]
    if exact:
        return exact, "exact_offset"
    containing = [
        record
        for record in records
        if record.start <= row.offset <= record.end
    ]
    if containing:
        return containing, "containing_offset"
    if row.source_length:
        end = row.offset + row.source_length
        overlaps = [
            record
            for record in records
            if record.start < end and record.end + 1 > row.offset
        ]
        if len(overlaps) == 1:
            return overlaps, "single_physical_overlap"
    return [], "unaligned"


def normalized_english(source: str) -> str:
    if GRAPHIC_CODE_RE.search(source):
        return source
    text = re.sub(r"^(?:<0A>)?", "", source)
    text = re.sub(r"^0+", "", text)
    text = re.sub(r"0+$", "", text)
    return re.sub(r"\s+", " ", text).strip()


def write_glyph_map(
    path: Path,
    glyph_map: dict[int, str],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "code_index",
                "high_hex",
                "low_hex",
                "unicode",
                "resolution_method",
            ),
        )
        writer.writeheader()
        for code, character in sorted(glyph_map.items()):
            high = 0xB0 + code // 94
            low = 0xA1 + code % 94
            writer.writerow(
                {
                    "code_index": code,
                    "high_hex": f"0x{high:02X}",
                    "low_hex": f"0x{low:02X}",
                    "unicode": character,
                    "resolution_method": (
                        "contextual_reconstruction"
                        if code in CONTEXTUAL_GLYPH_MAP
                        else "exact_hzk16_bitmap"
                    ),
                }
            )


def write_source_records(
    path: Path,
    records: list[ChineseRecord],
    pointers: dict[int, int],
) -> None:
    references_by_target: dict[int, list[int]] = {}
    for reference, target in pointers.items():
        references_by_target.setdefault(target, []).append(reference)

    with path.open("w", newline="", encoding="utf-8") as handle:
        fields = (
            "record_index",
            "start_hex",
            "end_hex_exclusive",
            "pair",
            "payload_bytes",
            "glyph_codes",
            "unresolved_codes",
            "chinese_text",
            "pointer_targets",
            "pointer_references",
        )
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            targets = sorted(
                target
                for target in references_by_target
                if record.start <= target <= record.end
            )
            references = sorted(
                reference
                for target in targets
                for reference in references_by_target[target]
            )
            writer.writerow(
                {
                    "record_index": record.index,
                    "start_hex": f"0x{record.start:06X}",
                    "end_hex_exclusive": f"0x{record.end:06X}",
                    "pair": record.pair,
                    "payload_bytes": record.end - record.start,
                    "glyph_codes": record.glyph_count,
                    "unresolved_codes": " ".join(
                        str(code) for code in record.unresolved_codes
                    ),
                    "chinese_text": record.text,
                    "pointer_targets": " ".join(
                        f"0x{target:06X}" for target in targets
                    ),
                    "pointer_references": " ".join(
                        f"0x{reference:06X}" for reference in references
                    ),
                }
            )


def write_alignment(
    path: Path,
    rows: list[EnglishRow],
    records: list[ChineseRecord],
    chinese_pointers: dict[int, int],
    english_pointers: dict[int, int],
) -> dict[str, int]:
    matched_references = sorted(
        set(chinese_pointers) & set(english_pointers)
    )
    records_by_row: dict[int, set[int]] = {}
    refs_by_row: dict[int, list[int]] = {}
    for reference in matched_references:
        source = chinese_owner(
            records,
            chinese_pointers[reference],
        )
        target = english_owner(
            rows,
            english_pointers[reference],
        )
        if source is None or target is None:
            continue
        records_by_row.setdefault(target.index, set()).add(source.index)
        refs_by_row.setdefault(target.index, []).append(reference)

    fields = (
        "entry_index",
        "english_offset_hex",
        "script_line",
        "layout",
        "source_length",
        "alignment_method",
        "alignment_confidence",
        "pointer_references",
        "chinese_record_indexes",
        "chinese_offsets",
        "chinese_text",
        "english_storage",
        "english_text",
        "fidelity_status",
        "review_note",
    )
    aligned = 0
    graphical = 0
    unresolved_source = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            record_indexes = sorted(records_by_row.get(row.index, set()))
            method = "pointer_table"
            confidence = "high"
            references = sorted(refs_by_row.get(row.index, []))
            if not record_indexes:
                fallback, method = fallback_source_records(row, records)
                record_indexes = [record.index for record in fallback]
                confidence = (
                    "medium"
                    if method in {"exact_offset", "containing_offset"}
                    else "low"
                )

            sources = [
                records[index - 1]
                for index in record_indexes
            ]
            if sources:
                aligned += 1
            if any(record.unresolved_codes for record in sources):
                unresolved_source += 1

            english_graphical = bool(
                GRAPHIC_CODE_RE.search(row.source_text)
            )
            if english_graphical:
                graphical += 1
            status = (
                "english_graphical_residual"
                if english_graphical
                else "pending_semantic_review"
                if sources
                else "unaligned_or_non_dialogue"
            )
            note = (
                "La ROM anglaise conserve des codes graphiques; "
                "ce texte n'est pas une chaîne anglaise lisible."
                if english_graphical
                else ""
            )
            writer.writerow(
                {
                    "entry_index": row.index,
                    "english_offset_hex": f"0x{row.offset:06X}",
                    "script_line": row.line,
                    "layout": row.layout,
                    "source_length": row.source_length,
                    "alignment_method": method,
                    "alignment_confidence": confidence,
                    "pointer_references": " ".join(
                        f"0x{reference:06X}"
                        for reference in references
                    ),
                    "chinese_record_indexes": " ".join(
                        str(index) for index in record_indexes
                    ),
                    "chinese_offsets": " ".join(
                        f"0x{record.start:06X}" for record in sources
                    ),
                    "chinese_text": "\n---\n".join(
                        record.text for record in sources
                    ),
                    "english_storage": (
                        "graphical_codes"
                        if english_graphical
                        else "ascii"
                    ),
                    "english_text": normalized_english(row.source_text),
                    "fidelity_status": status,
                    "review_note": note,
                }
            )
    return {
        "english_entries": len(rows),
        "aligned_entries": aligned,
        "matched_pointer_slots": len(matched_references),
        "english_graphical_residual_entries": graphical,
        "aligned_entries_with_unresolved_source_glyphs": unresolved_source,
    }


def write_pointer_alignment(
    path: Path,
    rows: list[EnglishRow],
    records: list[ChineseRecord],
    chinese_pointers: dict[int, int],
    english_pointers: dict[int, int],
) -> dict[str, int]:
    fields = (
        "pointer_reference_hex",
        "chinese_target_hex",
        "chinese_record_index",
        "chinese_text",
        "english_target_hex",
        "english_entry_index",
        "english_offset_hex",
        "english_storage",
        "english_text",
        "fidelity_status",
        "review_note",
    )
    matched = sorted(set(chinese_pointers) & set(english_pointers))
    resolved = 0
    graphical = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for reference in matched:
            source = chinese_owner(records, chinese_pointers[reference])
            target = english_owner(rows, english_pointers[reference])
            english_graphical = bool(
                target
                and GRAPHIC_CODE_RE.search(target.source_text)
            )
            if source is not None and target is not None:
                resolved += 1
            if english_graphical:
                graphical += 1
            writer.writerow(
                {
                    "pointer_reference_hex": f"0x{reference:06X}",
                    "chinese_target_hex": (
                        f"0x{chinese_pointers[reference]:06X}"
                    ),
                    "chinese_record_index": source.index if source else "",
                    "chinese_text": source.text if source else "",
                    "english_target_hex": (
                        f"0x{english_pointers[reference]:06X}"
                    ),
                    "english_entry_index": target.index if target else "",
                    "english_offset_hex": (
                        f"0x{target.offset:06X}" if target else ""
                    ),
                    "english_storage": (
                        "graphical_codes"
                        if english_graphical
                        else "ascii"
                        if target
                        else ""
                    ),
                    "english_text": (
                        normalized_english(target.source_text)
                        if target
                        else ""
                    ),
                    "fidelity_status": (
                        "english_graphical_residual"
                        if english_graphical
                        else "pending_semantic_review"
                        if source and target
                        else "unresolved_alignment"
                    ),
                    "review_note": (
                        "La cible anglaise conserve des codes graphiques."
                        if english_graphical
                        else ""
                    ),
                }
            )
    return {
        "pointer_alignment_rows": len(matched),
        "resolved_pointer_alignment_rows": resolved,
        "graphical_pointer_alignment_rows": graphical,
    }


def write_dialogue_subset(
    alignment_path: Path,
    output_path: Path,
) -> dict[str, int]:
    with alignment_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fields = tuple(rows[0]) if rows else ()
    dialogues = [
        row
        for row in rows
        if row["layout"].startswith("dialogue_")
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(dialogues)
    return {
        "dialogue_entries": len(dialogues),
        "aligned_dialogue_entries": sum(
            bool(row["chinese_record_indexes"]) for row in dialogues
        ),
        "graphical_residual_dialogue_entries": sum(
            row["english_storage"] == "graphical_codes"
            for row in dialogues
        ),
    }


def refs_by_target(entries: dict[int, list[int]]) -> dict[int, int]:
    """Invert a target-to-reference map, rejecting ambiguous pointer slots."""
    result: dict[int, int] = {}
    for target, references in entries.items():
        for reference in references:
            previous = result.setdefault(reference, target)
            if previous != target:
                raise ValueError(
                    f"pointeur 0x{reference:06X} à deux cibles terrain"
                )
    return result


def write_source_dialogue_inventory(
    path: Path,
    untranslated_path: Path,
    absent_french_path: Path,
    divergence_path: Path,
    chinese: bytes,
    english: bytes,
    records: list[ChineseRecord],
    rows: list[EnglishRow],
) -> dict[str, int]:
    """Write a source-centric audit of every live field dialogue.

    The English column follows the untouched 2015 English ROM.  The French
    column follows the reviewed pointer redirects applied by the French
    repacker, so it describes the effective French build rather than merely
    the translation row stored at the original English target.
    """
    chinese_by_reference = refs_by_target(
        verified_field_dialogue_pointer_entries(chinese)
    )
    english_entries = verified_field_dialogue_pointer_entries(english)
    english_by_reference = refs_by_target(english_entries)
    french_by_reference = refs_by_target(
        apply_verified_pointer_redirects(english, english_entries)
    )

    fields = (
        "pointer_reference_hex",
        "chinese_record_index",
        "chinese_offset_hex",
        "chinese_text",
        "english_offset_hex",
        "english_storage",
        "english_text",
        "english_translation_status",
        "french_source_offset_hex",
        "french_text",
        "present_in_french",
        "pointer_redirected_for_french",
    )
    inventory: list[dict[str, str]] = []
    seen_sources: set[int] = set()
    source_owner_failures = 0
    for reference in sorted(chinese_by_reference):
        source = chinese_owner(
            records,
            chinese_by_reference[reference],
        )
        if source is None:
            source_owner_failures += 1
            continue
        if source.index in seen_sources:
            continue
        seen_sources.add(source.index)

        english_target = english_by_reference[reference]
        french_target = french_by_reference[reference]
        english_row = english_owner(rows, english_target)
        french_row = english_owner(rows, french_target)
        english_graphical = bool(
            english_row
            and GRAPHIC_CODE_RE.search(english_row.source_text)
        )
        inventory.append(
            {
                "pointer_reference_hex": f"0x{reference:06X}",
                "chinese_record_index": str(source.index),
                "chinese_offset_hex": f"0x{source.start:06X}",
                "chinese_text": source.text,
                "english_offset_hex": (
                    f"0x{english_row.offset:06X}" if english_row else ""
                ),
                "english_storage": (
                    "graphical_codes"
                    if english_graphical
                    else "ascii"
                    if english_row
                    else ""
                ),
                "english_text": (
                    normalized_english(english_row.source_text)
                    if english_row
                    else ""
                ),
                "english_translation_status": (
                    "not_translated_in_english"
                    if english_graphical
                    else "english_ascii_present"
                    if english_row
                    else "english_entry_missing"
                ),
                "french_source_offset_hex": (
                    f"0x{french_row.offset:06X}" if french_row else ""
                ),
                "french_text": french_row.french_text if french_row else "",
                "present_in_french": "yes" if french_row else "no",
                "pointer_redirected_for_french": (
                    "yes" if english_target != french_target else "no"
                ),
            }
        )

    def write_rows(output_path: Path, selected: list[dict[str, str]]) -> None:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(selected)

    untranslated = [
        row
        for row in inventory
        if row["english_translation_status"] == "not_translated_in_english"
    ]
    absent_french = [
        row for row in inventory if row["present_in_french"] == "no"
    ]
    write_rows(path, inventory)
    write_rows(untranslated_path, untranslated)
    write_rows(absent_french_path, absent_french)
    divergence_fields = fields + ("review_category", "review_note")
    with divergence_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=divergence_fields)
        writer.writeheader()
        for row in inventory:
            record_index = int(row["chinese_record_index"])
            review = REVIEWED_LARGE_DIALOGUE_DIVERGENCES.get(record_index)
            if review is None:
                continue
            writer.writerow(
                {
                    **row,
                    "review_category": review[0],
                    "review_note": review[1],
                }
            )
    return {
        "source_field_dialogue_records": len(inventory),
        "source_field_dialogue_owner_failures": source_owner_failures,
        "source_dialogues_not_translated_in_english": len(untranslated),
        "source_field_dialogues_missing_french_owner": len(absent_french),
        "source_dialogues_present_in_french": sum(
            row["present_in_french"] == "yes" for row in inventory
        ),
        "source_dialogue_pointers_redirected_for_french": sum(
            row["pointer_redirected_for_french"] == "yes"
            for row in inventory
        ),
        "reviewed_large_dialogue_divergences": sum(
            int(row["chinese_record_index"])
            in REVIEWED_LARGE_DIALOGUE_DIVERGENCES
            for row in inventory
        ),
    }


def dialogue_reference(reference: int) -> bool:
    return any(
        first <= reference <= last
        for first, last in CHINESE_DIALOGUE_POINTER_RANGES
    )


def decoded_pointer_target(data: bytes, reference: int) -> int | None:
    address = int.from_bytes(data[reference:reference + 2], "little")
    return offset_for_cpu_addr(
        pair_for_offset(reference),
        address,
        len(data),
    )


def write_dialogues_absent_from_english_and_french(
    path: Path,
    compatibility_path: Path,
    records: list[ChineseRecord],
    chinese_pointers: dict[int, int],
    english: bytes,
    french: bytes,
) -> dict[str, int]:
    """List source dialogue slots invalidated by both downstream ROMs."""
    fields = (
        "pointer_reference_hex",
        "chinese_record_index",
        "chinese_offset_hex",
        "chinese_text",
        "english_pointer_bytes_hex",
        "english_pointer_status",
        "french_pointer_bytes_hex",
        "french_pointer_status",
        "absence_category",
    )
    rows: list[dict[str, str]] = []
    english_invalid = 0
    french_restored = 0
    for record in records:
        references = sorted(
            reference
            for reference, target in chinese_pointers.items()
            if (
                dialogue_reference(reference)
                and record.start <= target <= record.end
            )
        )
        for reference in references:
            if decoded_pointer_target(english, reference) is not None:
                continue
            english_invalid += 1
            french_target = decoded_pointer_target(french, reference)
            if french_target is not None:
                french_restored += 1
                continue
            rows.append(
                {
                    "pointer_reference_hex": f"0x{reference:06X}",
                    "chinese_record_index": str(record.index),
                    "chinese_offset_hex": f"0x{record.start:06X}",
                    "chinese_text": record.text,
                    "english_pointer_bytes_hex": (
                        english[reference:reference + 2].hex().upper()
                    ),
                    "english_pointer_status": "invalid",
                    "french_pointer_bytes_hex": (
                        french[reference:reference + 2].hex().upper()
                    ),
                    "french_pointer_status": "invalid",
                    "absence_category": (
                        "source_dialogue_pointer_removed_in_english_"
                        "and_not_restored_in_french"
                    ),
                }
            )

    def write_rows(output_path: Path) -> None:
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    write_rows(path)
    write_rows(compatibility_path)
    return {
        "source_dialogue_pointers_invalidated_in_english": english_invalid,
        "source_dialogue_pointers_restored_in_french": french_restored,
        "source_dialogues_absent_from_english_and_french": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extrait les textes chinois NJ046 et les aligne avec le patch "
            "anglais canonique."
        )
    )
    parser.add_argument("--chinese-rom", default=CHINESE_ROM)
    parser.add_argument("--english-rom", default=TRANSLATION_BASE_ROM)
    parser.add_argument("--french-rom", default=FINAL_ROM)
    parser.add_argument("--script", default=PATCH_SCRIPT)
    parser.add_argument("--hzk16", required=True)
    parser.add_argument(
        "--output-directory",
        default="build/chinese-english-fidelity",
    )
    args = parser.parse_args()

    chinese_path = Path(args.chinese_rom)
    english_path = Path(args.english_rom)
    french_path = Path(args.french_rom)
    script_path = Path(args.script)
    hzk_path = Path(args.hzk16)
    chinese_path = (
        chinese_path
        if chinese_path.is_absolute()
        else ROM_DIR / chinese_path
    )
    english_path = (
        english_path
        if english_path.is_absolute()
        else ROM_DIR / english_path
    )
    french_path = (
        french_path
        if french_path.is_absolute()
        else ROM_DIR / french_path
    )
    script_path = (
        script_path
        if script_path.is_absolute()
        else ROM_DIR / script_path
    )
    hzk_path = hzk_path if hzk_path.is_absolute() else ROM_DIR / hzk_path

    chinese = read_checked(
        chinese_path,
        CHINESE_ROM_SHA256,
        "ROM chinoise",
    )
    english = read_checked(
        english_path,
        TRANSLATION_BASE_SHA256,
        "ROM anglaise",
    )
    french = french_path.read_bytes()
    hzk16 = read_checked(hzk_path, HZK16_SHA256, "HZK16")

    output = Path(args.output_directory)
    if not output.is_absolute():
        output = ROM_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    glyph_map = build_glyph_map(chinese, hzk16)
    records = source_records(chinese, glyph_map)
    rows = english_rows(english, script_path)
    chinese_pointers = pointer_index(
        chinese,
        ((record.start, record.end - record.start) for record in records),
    )
    english_pointers = pointer_index(
        english,
        (
            (row.offset, row.source_length)
            for row in rows
            if row.source_length
        ),
    )

    write_glyph_map(output / "chinese_glyph_map.csv", glyph_map)
    write_source_records(
        output / "chinese_records.csv",
        records,
        chinese_pointers,
    )
    alignment_path = output / "chinese_english_alignment.csv"
    summary = write_alignment(
        alignment_path,
        rows,
        records,
        chinese_pointers,
        english_pointers,
    )
    summary.update(
        write_dialogue_subset(
            alignment_path,
            output / "chinese_dialogues.csv",
        )
    )
    summary.update(
        write_pointer_alignment(
            output / "pointer_alignment.csv",
            rows,
            records,
            chinese_pointers,
            english_pointers,
        )
    )
    summary.update(
        write_source_dialogue_inventory(
            output / "chinese_french_dialogue_inventory.csv",
            output / "dialogues_untranslated_in_english.csv",
            output / "field_dialogues_missing_french_owner.csv",
            output / "reviewed_large_dialogue_divergences.csv",
            chinese,
            english,
            records,
            rows,
        )
    )
    summary.update(
        write_dialogues_absent_from_english_and_french(
            output / "dialogues_absent_from_english_and_french.csv",
            output / "dialogues_absent_from_french.csv",
            records,
            chinese_pointers,
            english,
            french,
        )
    )
    summary.update(
        {
            "chinese_rom_sha256": sha256(chinese),
            "english_rom_sha256": sha256(english),
            "hzk16_sha256": sha256(hzk16),
            "chinese_records": len(records),
            "chinese_glyph_occurrences": sum(
                record.glyph_count for record in records
            ),
            "unique_chinese_codes": len(glyph_map),
            "exact_hzk16_chinese_codes": (
                len(glyph_map) - len(CONTEXTUAL_GLYPH_MAP)
            ),
            "contextually_reconstructed_chinese_codes": sorted(
                CONTEXTUAL_GLYPH_MAP
            ),
            "resolved_chinese_codes": len(glyph_map),
            "unresolved_chinese_codes": [],
            "chinese_pointer_slots": len(chinese_pointers),
            "english_pointer_slots": len(english_pointers),
        }
    )
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("Extraction chinois/anglais NJ046")
    print(f"- Records chinois : {summary['chinese_records']}")
    print(
        "- Occurrences glyphiques : "
        f"{summary['chinese_glyph_occurrences']}"
    )
    print(
        "- Codes Unicode résolus : "
        f"{summary['resolved_chinese_codes']}/"
        f"{summary['unique_chinese_codes']}"
    )
    print(
        "- Entrées anglaises alignées : "
        f"{summary['aligned_entries']}/"
        f"{summary['english_entries']}"
    )
    print(
        "- Résidus graphiques anglais : "
        f"{summary['english_graphical_residual_entries']}"
    )
    print(f"- Sortie : {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
