#!/usr/bin/env python3
"""Refresh French-dependent fidelity artifacts without re-extracting HZK16.

The Unicode Chinese source extraction is immutable and independently pinned:
``chinese_glyph_map.csv`` and ``chinese_records.csv`` must be the exact files
produced by the reviewed HZK16 run.  Everything that depends on ``script.py``
or on the current French ROM is rebuilt from those two files.

This is deliberately not presented as a new bitmap-to-Unicode extraction.
The generated summary records the provenance mode
``derived_refresh_without_hzk_reextraction`` and the hashes of every current
input.  Publishing is refused unless the 80 dialogue slots deleted by the
English ROM are all restored in the French ROM and all 85 reviewed restored
payloads are present at their live targets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any


TOOLS_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    CHINESE_ROM,
    FINAL_ROM,
    PATCH_SCRIPT,
    TRANSLATION_BASE_ROM,
    TRANSLATION_BASE_SHA256,
    offset_for_cpu_addr,
    pair_for_offset,
)

# ``pointer_index`` belongs to the fidelity extractor rather than the ROM
# assistant.  Keeping all imports below together makes the provenance of the
# derived algorithms explicit.
from tools.audit_chinese_english_fidelity import (  # noqa: E402
    CHINESE_ROM_SHA256,
    CHINESE_DIALOGUE_POINTER_RANGES,
    CONTEXTUAL_GLYPH_MAP,
    HZK16_SHA256,
    SOURCE_GLYPH_CODE_COUNT,
    SOURCE_RECORD_COUNT,
    ChineseRecord,
    decoded_pointer_target,
    english_rows,
    pointer_index,
    write_alignment,
    write_dialogue_subset,
    write_dialogues_absent_from_english_and_french,
    write_pointer_alignment,
    write_source_dialogue_inventory,
)
from tools.chinese_dialogue_restorations import RESTORED_DIALOGUES  # noqa: E402
from tools.export_creator_cameo_inventory import CAMEO_METADATA  # noqa: E402
from tools.export_dialogue_review_table import clean_source_text  # noqa: E402
from rom_traduction_assistant import (  # noqa: E402
    parse_patch_entries,
    read_bytes,
    sha256,
    verified_dialogue_restoration_payloads,
)


DEFAULT_SOURCE_EXTRACTION_DIRECTORY = (
    ROM_DIR / "data" / "source" / "chinese-english-fidelity"
)
DEFAULT_PUBLISHED_EXTRACTION_DIRECTORY = (
    ROM_DIR / "build" / "chinese-english-fidelity" / "extraction"
)
# Backwards-compatible name used by the existing test helpers.  It now points
# at the immutable, versioned Unicode source rather than an ignored build
# directory.
DEFAULT_EXTRACTION_DIRECTORY = DEFAULT_SOURCE_EXTRACTION_DIRECTORY
DEFAULT_REVIEW_CSV = ROM_DIR / "LISTE_EXHAUSTIVE_DIALOGUES.csv"

PROVENANCE_MODE = "derived_refresh_without_hzk_reextraction"
IMMUTABLE_GLYPH_MAP_SHA256 = (
    "5fa49b098eee1fab8ff854a899c3e3f3c"
    "b8111d5686dd2a131f52941acbcc1bd"
)
IMMUTABLE_RECORDS_SHA256 = (
    "89e7f91d2102533a47ac6c58ab5aab147"
    "1b13bebb66e20737796863e247f1cca"
)
EXPECTED_DIALOGUE_ROWS = 1055
EXPECTED_MAIN_DIALOGUES = 970
EXPECTED_RESTORATIONS = 85
EXPECTED_ENGLISH_REMOVED_POINTERS = 80
EXPECTED_CREATOR_CAMEOS = 17

EXPECTED_DERIVED_COUNTS = {
    "english_entries": 1844,
    "aligned_entries": 1829,
    "matched_pointer_slots": 1840,
    "english_graphical_residual_entries": 303,
    "aligned_entries_with_unresolved_source_glyphs": 0,
    "dialogue_entries": 970,
    "aligned_dialogue_entries": 961,
    "graphical_residual_dialogue_entries": 113,
    "pointer_alignment_rows": 1840,
    "resolved_pointer_alignment_rows": 1795,
    "graphical_pointer_alignment_rows": 295,
    "source_field_dialogue_records": 966,
    "source_field_dialogue_owner_failures": 6,
    "source_dialogues_not_translated_in_english": 110,
    "source_field_dialogues_missing_french_owner": 0,
    "source_dialogues_present_in_french": 966,
    "source_dialogue_pointers_redirected_for_french": 4,
    "reviewed_large_dialogue_divergences": 56,
    "source_dialogues_removed_from_english_inventory": (
        EXPECTED_ENGLISH_REMOVED_POINTERS
    ),
    "restored_chinese_dialogues_inventory": EXPECTED_RESTORATIONS,
    "creator_cameo_dialogues": EXPECTED_CREATOR_CAMEOS,
}

DERIVED_FILENAMES = (
    "chinese_english_alignment.csv",
    "chinese_dialogues.csv",
    "pointer_alignment.csv",
    "chinese_french_dialogue_inventory.csv",
    "dialogues_untranslated_in_english.csv",
    "field_dialogues_missing_french_owner.csv",
    "reviewed_large_dialogue_divergences.csv",
    "dialogues_removed_from_english.csv",
    "dialogues_absent_from_english_and_french.csv",
    "dialogues_absent_from_french.csv",
    "restored_chinese_dialogues.csv",
    "creator_cameo_dialogues.csv",
    "summary.json",
)
DERIVED_DATA_FILENAMES = tuple(
    filename for filename in DERIVED_FILENAMES if filename != "summary.json"
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_hash(path: Path, expected: str, label: str) -> str:
    actual = _file_sha256(path)
    if actual != expected:
        raise ValueError(
            f"{label} non canonique: {actual} au lieu de {expected}"
        )
    return actual


def load_immutable_records(path: Path) -> list[ChineseRecord]:
    _require_hash(
        path,
        IMMUTABLE_RECORDS_SHA256,
        "extraction Unicode chinoise (records)",
    )
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    records: list[ChineseRecord] = []
    for expected_index, row in enumerate(rows, start=1):
        index = int(row["record_index"])
        if index != expected_index:
            raise ValueError(
                "index chinois non séquentiel: "
                f"{index} au lieu de {expected_index}"
            )
        unresolved = tuple(
            int(value)
            for value in row["unresolved_codes"].split()
            if value
        )
        records.append(
            ChineseRecord(
                index=index,
                start=int(row["start_hex"], 16),
                end=int(row["end_hex_exclusive"], 16),
                pair=int(row["pair"]),
                glyph_count=int(row["glyph_codes"]),
                text=row["chinese_text"],
                unresolved_codes=unresolved,
            )
        )
    if len(records) != SOURCE_RECORD_COUNT:
        raise ValueError(
            f"{len(records)} records chinois, {SOURCE_RECORD_COUNT} attendus"
        )
    if sum(record.glyph_count for record in records) != SOURCE_GLYPH_CODE_COUNT:
        raise ValueError("compte de glyphes chinois immuable invalide")
    if any(record.unresolved_codes for record in records):
        raise ValueError("l'extraction Unicode immuable contient un glyphe non résolu")
    return records


def load_immutable_glyph_stats(path: Path) -> dict[str, int]:
    _require_hash(
        path,
        IMMUTABLE_GLYPH_MAP_SHA256,
        "extraction Unicode chinoise (glyph map)",
    )
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    indexes = [int(row["code_index"]) for row in rows]
    if indexes != list(range(len(rows))):
        raise ValueError("index de glyphes chinois non séquentiel")
    if any(not row["unicode"] for row in rows):
        raise ValueError("caractère Unicode chinois vide")
    contextual = sum(
        row["resolution_method"] == "contextual_reconstruction"
        for row in rows
    )
    exact = sum(
        row["resolution_method"] == "exact_hzk16_bitmap"
        for row in rows
    )
    if contextual != len(CONTEXTUAL_GLYPH_MAP) or exact + contextual != len(rows):
        raise ValueError("méthodes de résolution des glyphes chinois invalides")
    return {
        "unique_chinese_codes": len(rows),
        "exact_hzk16_chinese_codes": exact,
        "contextually_reconstructed_chinese_codes": contextual,
    }


def _review_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_DIALOGUE_ROWS:
        raise ValueError(
            f"table de relecture: {len(rows)} dialogues, "
            f"{EXPECTED_DIALOGUE_ROWS} attendus"
        )
    expected_ids = [f"D{index:04d}" for index in range(1, len(rows) + 1)]
    if [row.get("id") for row in rows] != expected_ids:
        raise ValueError("suite d'IDs de la table de relecture invalide")
    keys = [row.get("cle_stable", "") for row in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("clés stables de la table de relecture invalides")
    return rows


def validate_review_csv_against_sources(
    review_csv: Path,
    script_path: Path,
) -> list[dict[str, str]]:
    rows = _review_rows(review_csv)
    by_key = {row["cle_stable"]: row for row in rows}
    main_entries = [
        entry
        for entry in parse_patch_entries(
            script_path,
            apply_dialogue_inventory=False,
        )
        if entry.layout.startswith("dialogue_")
    ]
    if len(main_entries) != EXPECTED_MAIN_DIALOGUES:
        raise ValueError(
            f"script: {len(main_entries)} dialogues principaux, "
            f"{EXPECTED_MAIN_DIALOGUES} attendus"
        )
    for entry in main_entries:
        key = f"MAIN:0x{entry.offset:06X}"
        row = by_key.get(key)
        if row is None:
            raise ValueError(f"table de relecture: clé absente {key}")
        expected = clean_source_text(entry.text)
        if row.get("texte_francais") != expected:
            raise ValueError(f"table de relecture périmée pour {key}")
        if row.get("layout") != entry.layout:
            raise ValueError(f"layout de relecture périmé pour {key}")
        if row.get("ligne_script") != str(entry.line):
            raise ValueError(f"ligne de script périmée pour {key}")

    if len(RESTORED_DIALOGUES) != EXPECTED_RESTORATIONS:
        raise ValueError("inventaire des restaurations françaises invalide")
    for reference, text in RESTORED_DIALOGUES.items():
        key = f"RESTORED:0x{reference:06X}"
        row = by_key.get(key)
        if row is None:
            raise ValueError(f"table de relecture: clé absente {key}")
        if row.get("texte_francais") != clean_source_text(text):
            raise ValueError(f"table de relecture périmée pour {key}")
    return rows


def write_creator_cameo_inventory(
    path: Path,
    review_rows: list[dict[str, str]],
) -> int:
    """Write current cameo text using the already-validated review table.

    The metadata is a reviewed, stable-key manifest.  Taking dialogue text
    from ``review_rows`` keeps this derivative in the same atomic refresh as
    the other Chinese/French tables and prevents an editorial rewrite from
    leaving the cameo inventory behind.
    """
    by_key = {row["cle_stable"]: row for row in review_rows}
    missing = [
        metadata.stable_key
        for metadata in CAMEO_METADATA
        if metadata.stable_key not in by_key
    ]
    if missing:
        raise ValueError("clés de caméos absentes : " + ", ".join(missing))

    fields = (
        "id",
        "cle_stable",
        "scope",
        "createur_ou_cameo",
        "role_source",
        "texte_chinois_source",
        "texte_francais_actuel",
        "statut",
    )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for metadata in CAMEO_METADATA:
            dialogue = by_key[metadata.stable_key]
            writer.writerow(
                {
                    "id": dialogue["id"],
                    "cle_stable": metadata.stable_key,
                    "scope": metadata.scope,
                    "createur_ou_cameo": metadata.creator,
                    "role_source": metadata.source_role,
                    "texte_chinois_source": dialogue[
                        "texte_chinois_source"
                    ],
                    "texte_francais_actuel": dialogue["texte_francais"],
                    "statut": "restauré dans la version française",
                }
            )
    return len(CAMEO_METADATA)


def write_restored_dialogue_inventory(
    path: Path,
    review_rows: list[dict[str, str]],
) -> int:
    """Publish the 85 source-backed restorations in one current table."""
    restored = [
        row
        for row in review_rows
        if row["cle_stable"].startswith("RESTORED:")
    ]
    if len(restored) != EXPECTED_RESTORATIONS:
        raise ValueError(
            f"{len(restored)} dialogues restaurés dans la table de "
            f"relecture, {EXPECTED_RESTORATIONS} attendus"
        )
    fields = (
        "id",
        "cle_stable",
        "pointer_reference_hex",
        "texte_chinois_source",
        "traduction_anglaise_rom_anglaise",
        "texte_francais_actuel",
        "statut",
    )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in restored:
            writer.writerow(
                {
                    "id": row["id"],
                    "cle_stable": row["cle_stable"],
                    "pointer_reference_hex": row["offset_ou_pointeur"],
                    "texte_chinois_source": row["texte_chinois_source"],
                    "traduction_anglaise_rom_anglaise": row[
                        "traduction_anglaise_rom_anglaise"
                    ],
                    "texte_francais_actuel": row["texte_francais"],
                    "statut": "restauré et vérifié dans la ROM française",
                }
            )
    return len(restored)


def write_dialogues_removed_from_english(
    path: Path,
    records: list[ChineseRecord],
    chinese_pointers: dict[int, int],
    english: bytes,
) -> int:
    """Keep the 80 English removals independent from current French state."""
    fields = (
        "pointer_reference_hex",
        "chinese_record_index",
        "chinese_offset_hex",
        "chinese_text",
        "english_pointer_bytes_hex",
        "english_pointer_status",
        "source_status",
    )
    rows: list[dict[str, str]] = []
    for record in records:
        references = sorted(
            reference
            for reference, target in chinese_pointers.items()
            if (
                any(
                    first <= reference <= last
                    for first, last in CHINESE_DIALOGUE_POINTER_RANGES
                )
                and record.start <= target <= record.end
            )
        )
        for reference in references:
            if decoded_pointer_target(english, reference) is not None:
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
                    "source_status": "removed_from_english_rom",
                }
            )
    if len(rows) != EXPECTED_ENGLISH_REMOVED_POINTERS:
        raise ValueError(
            f"{len(rows)} dialogues supprimés de l'anglais, "
            f"{EXPECTED_ENGLISH_REMOVED_POINTERS} attendus"
        )
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def validate_live_restoration_payloads(
    english: bytes,
    french: bytes,
) -> int:
    expected_payloads = verified_dialogue_restoration_payloads(english)
    if len(expected_payloads) != EXPECTED_RESTORATIONS:
        raise ValueError(
            f"{len(expected_payloads)} restaurations encodées, "
            f"{EXPECTED_RESTORATIONS} attendues"
        )
    errors: list[str] = []
    for reference, payload in sorted(expected_payloads.items()):
        address = int.from_bytes(french[reference:reference + 2], "little")
        target = offset_for_cpu_addr(
            pair_for_offset(reference),
            address,
            len(french),
        )
        if target is None:
            errors.append(f"0x{reference:06X}: pointeur français invalide")
            continue
        actual = french[target:target + len(payload)]
        terminator = target + len(payload)
        if actual != payload:
            errors.append(f"0x{reference:06X}: charge utile française différente")
        elif terminator >= len(french) or french[terminator] != 0x0D:
            errors.append(f"0x{reference:06X}: terminateur français absent")
    if errors:
        raise ValueError(
            "restaurations françaises non publiables:\n  "
            + "\n  ".join(errors[:20])
        )
    return len(expected_payloads)


def _resolved_path(path: Path) -> Path:
    return path if path.is_absolute() else ROM_DIR / path


def build_refresh(
    *,
    source_extraction_directory: Path = DEFAULT_EXTRACTION_DIRECTORY,
    output_directory: Path = DEFAULT_EXTRACTION_DIRECTORY,
    chinese_rom: Path = ROM_DIR / CHINESE_ROM,
    english_rom: Path = ROM_DIR / TRANSLATION_BASE_ROM,
    french_rom: Path = ROM_DIR / FINAL_ROM,
    script_path: Path = ROM_DIR / PATCH_SCRIPT,
    review_csv: Path = DEFAULT_REVIEW_CSV,
) -> dict[str, Any]:
    source_extraction_directory = source_extraction_directory.resolve()
    output_directory = output_directory.resolve()
    chinese_rom = _resolved_path(chinese_rom).resolve()
    english_rom = _resolved_path(english_rom).resolve()
    french_rom = _resolved_path(french_rom).resolve()
    script_path = _resolved_path(script_path).resolve()
    review_csv = _resolved_path(review_csv).resolve()

    records_path = source_extraction_directory / "chinese_records.csv"
    glyph_map_path = source_extraction_directory / "chinese_glyph_map.csv"
    records = load_immutable_records(records_path)
    glyph_stats = load_immutable_glyph_stats(glyph_map_path)
    review_rows = validate_review_csv_against_sources(review_csv, script_path)

    chinese = chinese_rom.read_bytes()
    english = english_rom.read_bytes()
    french = french_rom.read_bytes()
    if sha256(chinese) != CHINESE_ROM_SHA256:
        raise ValueError("ROM chinoise non canonique")
    if sha256(english) != TRANSLATION_BASE_SHA256:
        raise ValueError("ROM anglaise non canonique")
    if len(french) != len(english):
        raise ValueError("taille de ROM française inattendue")
    restored_payloads_verified = validate_live_restoration_payloads(
        english,
        french,
    )

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

    output_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".fidelity-derived-refresh-",
        dir=output_directory.parent,
    ) as temporary_name:
        staging = Path(temporary_name)
        alignment_path = staging / "chinese_english_alignment.csv"
        summary: dict[str, Any] = write_alignment(
            alignment_path,
            rows,
            records,
            chinese_pointers,
            english_pointers,
        )
        summary.update(
            write_dialogue_subset(
                alignment_path,
                staging / "chinese_dialogues.csv",
            )
        )
        summary.update(
            write_pointer_alignment(
                staging / "pointer_alignment.csv",
                rows,
                records,
                chinese_pointers,
                english_pointers,
            )
        )
        summary.update(
            write_source_dialogue_inventory(
                staging / "chinese_french_dialogue_inventory.csv",
                staging / "dialogues_untranslated_in_english.csv",
                staging / "field_dialogues_missing_french_owner.csv",
                staging / "reviewed_large_dialogue_divergences.csv",
                chinese,
                english,
                records,
                rows,
            )
        )
        summary["source_dialogues_removed_from_english_inventory"] = (
            write_dialogues_removed_from_english(
                staging / "dialogues_removed_from_english.csv",
                records,
                chinese_pointers,
                english,
            )
        )
        summary.update(
            write_dialogues_absent_from_english_and_french(
                staging / "dialogues_absent_from_english_and_french.csv",
                staging / "dialogues_absent_from_french.csv",
                records,
                chinese_pointers,
                english,
                french,
            )
        )
        summary["restored_chinese_dialogues_inventory"] = (
            write_restored_dialogue_inventory(
                staging / "restored_chinese_dialogues.csv",
                review_rows,
            )
        )
        summary["creator_cameo_dialogues"] = write_creator_cameo_inventory(
            staging / "creator_cameo_dialogues.csv",
            review_rows,
        )

        count_errors = [
            f"{key}={summary.get(key)!r} (attendu {expected})"
            for key, expected in EXPECTED_DERIVED_COUNTS.items()
            if summary.get(key) != expected
        ]
        if count_errors:
            raise ValueError(
                "comptes structurels fidelity inattendus: "
                + "; ".join(count_errors)
            )

        removed = summary["source_dialogue_pointers_invalidated_in_english"]
        restored = summary["source_dialogue_pointers_restored_in_french"]
        absent = summary["source_dialogues_absent_from_english_and_french"]
        if (
            removed != EXPECTED_ENGLISH_REMOVED_POINTERS
            or restored != EXPECTED_ENGLISH_REMOVED_POINTERS
            or absent != 0
        ):
            raise ValueError(
                "état des pointeurs restaurés non publiable: "
                f"supprimés_en={removed}, restaurés_fr={restored}, "
                f"absents_en_et_fr={absent}"
            )

        contextual_codes = sorted(CONTEXTUAL_GLYPH_MAP)
        summary.update(
            {
                "chinese_rom_sha256": sha256(chinese),
                "english_rom_sha256": sha256(english),
                "french_rom_sha256": sha256(french),
                "script_sha256": _file_sha256(script_path),
                "review_csv_sha256": _file_sha256(review_csv),
                "hzk16_sha256": HZK16_SHA256,
                "chinese_records": len(records),
                "chinese_glyph_occurrences": sum(
                    record.glyph_count for record in records
                ),
                "unique_chinese_codes": glyph_stats["unique_chinese_codes"],
                "exact_hzk16_chinese_codes": glyph_stats[
                    "exact_hzk16_chinese_codes"
                ],
                "contextually_reconstructed_chinese_codes": contextual_codes,
                "resolved_chinese_codes": glyph_stats["unique_chinese_codes"],
                "unresolved_chinese_codes": [],
                "chinese_pointer_slots": len(chinese_pointers),
                "english_pointer_slots": len(english_pointers),
                "review_dialogue_rows": len(review_rows),
                "review_main_dialogues": EXPECTED_MAIN_DIALOGUES,
                "review_restored_dialogues": EXPECTED_RESTORATIONS,
                "restored_payloads_verified_in_french_rom": (
                    restored_payloads_verified
                ),
                "provenance_mode": PROVENANCE_MODE,
                "provenance": {
                    "mode": PROVENANCE_MODE,
                    "immutable_source_reextracted": False,
                    "hzk16_input_used_for_refresh": False,
                    "immutable_chinese_records_csv_sha256": (
                        IMMUTABLE_RECORDS_SHA256
                    ),
                    "immutable_chinese_glyph_map_csv_sha256": (
                        IMMUTABLE_GLYPH_MAP_SHA256
                    ),
                    "original_hzk16_sha256": HZK16_SHA256,
                    "claim": (
                        "French-dependent derivatives refreshed from the "
                        "pinned Unicode extraction; no HZK16 re-extraction."
                    ),
                },
            }
        )
        summary["derived_artifacts_sha256"] = {
            filename: _file_sha256(staging / filename)
            for filename in DERIVED_DATA_FILENAMES
        }
        (staging / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        for filename in DERIVED_FILENAMES:
            source = staging / filename
            if not source.is_file():
                raise ValueError(f"sortie dérivée absente: {filename}")
        for filename in DERIVED_FILENAMES:
            os.replace(staging / filename, output_directory / filename)
    return summary


def verify_published_refresh(
    *,
    source_extraction_directory: Path = DEFAULT_EXTRACTION_DIRECTORY,
    published_directory: Path = DEFAULT_EXTRACTION_DIRECTORY,
    chinese_rom: Path = ROM_DIR / CHINESE_ROM,
    english_rom: Path = ROM_DIR / TRANSLATION_BASE_ROM,
    french_rom: Path = ROM_DIR / FINAL_ROM,
    script_path: Path = ROM_DIR / PATCH_SCRIPT,
    review_csv: Path = DEFAULT_REVIEW_CSV,
) -> dict[str, Any]:
    """Rebuild to a temporary directory and byte-compare every derivative."""
    source_extraction_directory = source_extraction_directory.resolve()
    published_directory = published_directory.resolve()
    with tempfile.TemporaryDirectory(
        prefix=".fidelity-derived-check-",
        dir=published_directory.parent,
    ) as temporary_name:
        temporary = Path(temporary_name)
        summary = build_refresh(
            source_extraction_directory=source_extraction_directory,
            output_directory=temporary,
            chinese_rom=chinese_rom,
            english_rom=english_rom,
            french_rom=french_rom,
            script_path=script_path,
            review_csv=review_csv,
        )
        for filename in DERIVED_FILENAMES:
            published = published_directory / filename
            expected = temporary / filename
            if not published.is_file():
                raise ValueError(f"dérivé publié absent: {filename}")
            if published.read_bytes() != expected.read_bytes():
                raise ValueError(
                    f"dérivé publié périmé: {filename}; "
                    f"actuel={_file_sha256(published)}, "
                    f"attendu={_file_sha256(expected)}"
                )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Rafraîchit les dérivés chinois/anglais/français depuis "
            "l'extraction Unicode immuable, sans réexécuter HZK16."
        )
    )
    parser.add_argument(
        "--source-extraction-directory",
        type=Path,
        default=DEFAULT_SOURCE_EXTRACTION_DIRECTORY,
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=DEFAULT_PUBLISHED_EXTRACTION_DIRECTORY,
    )
    parser.add_argument("--chinese-rom", type=Path, default=ROM_DIR / CHINESE_ROM)
    parser.add_argument(
        "--english-rom",
        type=Path,
        default=ROM_DIR / TRANSLATION_BASE_ROM,
    )
    parser.add_argument("--french-rom", type=Path, default=ROM_DIR / FINAL_ROM)
    parser.add_argument("--script", type=Path, default=ROM_DIR / PATCH_SCRIPT)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Reconstruit dans un répertoire temporaire et refuse tout "
            "dérivé publié absent ou périmé."
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    keyword_arguments = {
        "source_extraction_directory": args.source_extraction_directory,
        "chinese_rom": args.chinese_rom,
        "english_rom": args.english_rom,
        "french_rom": args.french_rom,
        "script_path": args.script,
        "review_csv": args.review_csv,
    }
    if args.check:
        summary = verify_published_refresh(
            **keyword_arguments,
            published_directory=args.output_directory,
        )
        print("Contrôle des dérivés fidelity aval : PASS")
    else:
        summary = build_refresh(
            **keyword_arguments,
            output_directory=args.output_directory,
        )
        print("Rafraîchissement fidelity aval : PASS")
    print(f"- Provenance : {summary['provenance_mode']}")
    print(
        "- Pointeurs supprimés/restaurés/encore absents : "
        f"{summary['source_dialogue_pointers_invalidated_in_english']}/"
        f"{summary['source_dialogue_pointers_restored_in_french']}/"
        f"{summary['source_dialogues_absent_from_english_and_french']}"
    )
    print(f"- Sortie : {args.output_directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
