#!/usr/bin/env python3
"""Build an exhaustive, reviewable inventory of every live French text unit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


TOOL_DIR = Path(__file__).resolve().parent
ROM_DIR = TOOL_DIR.parent
sys.path.insert(0, str(ROM_DIR))

from rom_traduction_assistant import (  # noqa: E402
    DEFAULT_FRENCH_POINTER_VARIANTS,
    ITEM_LIST_ANTIDOTE_OFFSET,
    TRANSLATION_BASE_ROM,
    load_french_pointer_variants,
    verified_all_graphical_text_records,
    verified_dialogue_restoration_payloads,
)
from tools.audit_battle_french import BATTLE_TEXT_EXPECTATIONS  # noqa: E402
from tools.audit_quality_ambitious import (  # noqa: E402
    Row as QualityRow,
    audit_rows,
    read_rows as read_quality_rows,
)
from tools.chinese_dialogue_restorations import (  # noqa: E402
    RESTORED_DIALOGUES,
)
from tools.dialogue_layout import (  # noqa: E402
    DIALOGUE_LAYOUT,
    INTRO_DIALOGUE_LAYOUT,
    POKEDEX_LAYOUT,
    format_game_text,
)
from tools.move_label_graphics import (  # noqa: E402
    MOVE_NAME_POINTER_TABLE_OFFSET,
    french_text_encoder,
    load_move_label_csv,
)
from tools.validate_repacked import (  # noqa: E402
    DEFAULT_MOVE_LABEL_CATALOGUE,
    build_parser as build_validate_parser,
    compute_plan,
)
from tools.validate_french_dynamic_fragments import (  # noqa: E402
    BATTLE_ARTIFACT_FREE_CELLS,
    DEAD_UNREFERENCED_REFS,
    DYNAMIC_LAYOUT_CLASSIFIED_REFS,
    ITEM_LIST_NAME_EXPECTATIONS,
    LIVE_DYNAMIC_LAYOUT_REFS,
)


EXPECTED_SCRIPT_ENTRY_COUNT = 1846
EXPECTED_RESTORATION_COUNT = 85
EXPECTED_GRAPHICAL_MOVE_LABEL_COUNT = 94
EXPECTED_SECONDARY_VARIANT_COUNT = 3
EXPECTED_FIXED_LIVE_TEXT_COUNT = 3
EXPECTED_REVIEWED_UNIT_COUNT = (
    EXPECTED_SCRIPT_ENTRY_COUNT
    + EXPECTED_RESTORATION_COUNT
    + EXPECTED_GRAPHICAL_MOVE_LABEL_COUNT
    + EXPECTED_SECONDARY_VARIANT_COUNT
    + EXPECTED_FIXED_LIVE_TEXT_COUNT
)

# Three live targets are absent from the historical patch catalogue.  They are
# inventoried explicitly so the exhaustive report does not silently omit the
# two fixed item labels or the one-record battle connector.
FIXED_LIVE_TEXT_UNITS = (
    {
        "offset": ITEM_LIST_ANTIDOTE_OFFSET,
        "reference": 0x03165B,
        "source_en": "Antidote",
        "fr_text": "Antid.",
        "source_capacity": 8,
        "storage": "fixed_builder_patch",
        "category": "fixed_menu_item_name_or_system",
        "liveness_evidence": "live_item_table_pointer",
        "provenance": "uncatalogued fixed item-table target, shortened for the quantity field",
    },
    {
        "offset": 0x0317AD,
        "reference": 0x03167B,
        "source_en": "Pokédex",
        "fr_text": "Pokédex",
        "source_capacity": 7,
        "storage": "verified_fixed_in_place",
        "category": "fixed_menu_item_name_or_system",
        "liveness_evidence": "live_item_table_pointer",
        "provenance": "uncatalogued fixed item-table target, already within the seven-cell limit",
    },
    {
        "offset": 0x030439,
        "reference": 0x0300A3,
        "source_en": "...!",
        "fr_text": "...!",
        "source_capacity": 4,
        "storage": "verified_fixed_in_place",
        "category": "battle_or_system",
        "liveness_evidence": "live_battle_pointer",
        "provenance": "uncatalogued live battle connector after a move name",
    },
)

# Entries edited during this focused full-text review.  This list deliberately
# excludes pre-existing dirty-tree work and derived CSV/Markdown rewrites.
CERTAIN_TEXT_CORRECTION_OFFSETS = (
    0x0301F0,
    0x030203,
    0x030262,
    0x0302EE,
    0x0302FA,
    0x030304,
    0x03030E,
    0x03031A,
    0x030417,
    0x03043F,
    0x03045F,
    0x030485,
    0x03049A,
    0x0304A9,
    0x0304AB,
    0x0304CF,
    0x030519,
    0x03068E,
    0x0306FE,
    0x03072D,
    0x030744,
    0x03077A,
    0x0307B9,
    0x0307C4,
    0x0307CF,
    0x0308E9,
    0x0308F6,
    0x030902,
    0x030939,
    0x030AC9,
    0x030ADB,
    0x030F83,
    0x030F8E,
    0x03118F,
    0x0316EE,
    0x0316F7,
    0x031700,
    0x031710,
    0x031719,
    0x031722,
    0x03174F,
    0x031758,
    0x03176F,
    0x031779,
    0x031782,
    0x03178B,
    0x031794,
    0x03179D,
    0x0317C4,
    0x0317CF,
    0x0317DA,
    0x0317E3,
    0x0317EE,
    0x0317F8,
    0x03181D,
    0x031824,
    0x031AA4,
    0x031ACE,
    0x031FF1,
    0x0346A1,
    0x0349E5,
    0x0349F2,
    0x035F15,
    0x035F23,
    0x035F34,
    0x035F3D,
    0x035F57,
    0x035F65,
    0x035F75,
    0x035F85,
    0x035F98,
    0x035FAE,
    0x035FB6,
    0x03650D,
    0x03651B,
    0x03BDDA,
)

DEFAULT_CSV_OUTPUT = (
    ROM_DIR / "build/full-text-review-fr-20260816/french_live_text_inventory.csv"
)
DEFAULT_JSON_OUTPUT = (
    ROM_DIR / "build/full-text-review-fr-20260816/french_live_text_summary.json"
)
DEFAULT_MARKDOWN_OUTPUT = (
    ROM_DIR / "build/full-text-review-fr-20260816/RELECTURE_EXHAUSTIVE_FR.md"
)

CSV_COLUMNS = (
    "record_id",
    "kind",
    "category",
    "source_offset_hex",
    "pointer_references_hex",
    "layout",
    "source_en",
    "source_chinese",
    "fr_text",
    "fr_encoded_len",
    "planned_payload_len",
    "source_capacity",
    "pointer_count",
    "storage",
    "liveness_evidence",
    "provenance",
    "quality_status",
    "quality_flags",
    "review_status",
    "notes",
)


def _resolve(path: Path | str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROM_DIR / candidate


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attach_artifact_metadata(
    summary: dict[str, Any],
    artifacts: Iterable[tuple[str, Path | None]],
) -> list[str]:
    """Attach exact release-candidate paths, sizes and hashes to the report."""
    errors: list[str] = []
    records: dict[str, dict[str, Any]] = {}
    for name, path in artifacts:
        if path is None:
            continue
        resolved = _resolve(path)
        if not resolved.is_file():
            errors.append(f"artefact absent: {name} ({resolved})")
            continue
        records[name] = {
            "path": str(resolved),
            "size": resolved.stat().st_size,
            "sha256": _sha256(resolved),
        }
    if records:
        summary["artifacts"] = records
    return errors


def _script_source_rows(path: Path) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = {
            int(item["offset_hex"], 16): item
            for item in csv.DictReader(handle)
        }
    return rows


def _dialogue_review_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {
            item["cle_stable"]: item
            for item in csv.DictReader(handle)
        }


def _pointer_variant_provenance(path: Path) -> dict[int, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {
            int(item["pointer_reference_hex"], 16): item
            for item in csv.DictReader(handle)
        }


def _issues_by_offset(
    issues: Iterable[dict[str, str | int]],
) -> dict[int, list[dict[str, str | int]]]:
    result: dict[int, list[dict[str, str | int]]] = defaultdict(list)
    for issue in issues:
        result[int(str(issue["offset_hex"]), 16)].append(issue)
    return result


def _quality_fields(
    issues: list[dict[str, str | int]],
) -> tuple[str, str]:
    if not issues:
        return "no_automated_issue", ""
    maximum = max(int(issue["severity"]) for issue in issues)
    status = (
        "unresolved_high_signal"
        if maximum >= 3
        else "heuristic_review_flag"
    )
    flags = " | ".join(
        f"S{issue['severity']}:{issue['category']}:{issue['rule_id']}"
        for issue in issues
    )
    return status, flags


def _category(
    *,
    offset: int,
    layout: str,
    refs: list[int],
    graphical_starts: set[int],
) -> str:
    if layout == DIALOGUE_LAYOUT:
        return "dialogue_main"
    if layout == INTRO_DIALOGUE_LAYOUT:
        return "dialogue_intro"
    if layout == POKEDEX_LAYOUT:
        return "pokedex"
    if offset in BATTLE_TEXT_EXPECTATIONS:
        return "battle_or_system"
    if offset in graphical_starts:
        return "graphical_fixed_text"
    if any(
        MOVE_NAME_POINTER_TABLE_OFFSET
        <= ref
        < MOVE_NAME_POINTER_TABLE_OFFSET + 177 * 2
        for ref in refs
    ):
        return "move_name_source"
    return "fixed_menu_item_name_or_system"


def _quality_summary(
    issue_groups: Iterable[Iterable[dict[str, str | int]]],
) -> dict[str, int]:
    counts = Counter()
    for issues in issue_groups:
        for issue in issues:
            severity = int(issue["severity"])
            counts[
                "high" if severity >= 3 else "medium" if severity == 2 else "low"
            ] += 1
    return {
        "high": counts["high"],
        "medium": counts["medium"],
        "low": counts["low"],
    }


def build_full_review(
    *,
    csv_path: Path,
    input_rom_path: Path,
    move_labels_path: Path,
    pointer_variants_path: Path,
    dialogue_review_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    plan_args = build_validate_parser().parse_args(
        [
            "--csv",
            str(csv_path),
            "--input-rom",
            str(input_rom_path),
            "--move-labels-csv",
            str(move_labels_path),
            "--pointer-variants-csv",
            str(pointer_variants_path),
        ]
    )
    (
        original,
        row_info,
        row_pointer_refs,
        allocations,
        allocation_failures,
        _free_spans,
        unsafe,
    ) = compute_plan(plan_args)

    source_rows = _script_source_rows(csv_path)
    dialogue_rows = _dialogue_review_rows(dialogue_review_path)
    variant_provenance = _pointer_variant_provenance(pointer_variants_path)
    graphical_starts = {
        start for start, _, _, _ in verified_all_graphical_text_records(original)
    }

    script_quality_issues = audit_rows(read_quality_rows(csv_path))
    script_issues = _issues_by_offset(script_quality_issues)

    restoration_payloads = verified_dialogue_restoration_payloads(original)
    restoration_quality_rows = [
        QualityRow(
            offset=reference,
            line=0,
            max_len=len(restoration_payloads[reference]),
            source_en="",
            fr_text=text,
            layout=DIALOGUE_LAYOUT,
        )
        for reference, text in sorted(RESTORED_DIALOGUES.items())
    ]
    restoration_issues = _issues_by_offset(audit_rows(restoration_quality_rows))

    variants = load_french_pointer_variants(pointer_variants_path)
    secondary_variants = [
        (main_offset, variant)
        for main_offset, group in variants.items()
        for variant in group[1:]
    ]
    variant_quality_rows = [
        QualityRow(
            offset=variant.pointer_reference,
            line=0,
            max_len=len(format_game_text(variant.text)),
            source_en="",
            fr_text=variant.text,
        )
        for _, variant in secondary_variants
    ]
    variant_issues = _issues_by_offset(audit_rows(variant_quality_rows))

    move_specs = load_move_label_csv(
        move_labels_path,
        encoder=french_text_encoder,
    )
    move_quality_rows = [
        QualityRow(
            offset=0x100000 + spec.move_index,
            line=0,
            max_len=spec.required_payload_size,
            source_en="",
            fr_text=spec.full_name,
        )
        for spec in move_specs
    ]
    move_issues = _issues_by_offset(audit_rows(move_quality_rows))

    inventory: list[dict[str, Any]] = []
    for row, max_len, planned_payload in row_info:
        pointer_refs = sorted(
            ref
            for _, refs in row_pointer_refs[row.offset]
            for ref in refs
        )
        source = source_rows[row.offset]
        review = dialogue_rows.get(f"MAIN:0x{row.offset:06X}", {})
        issues = script_issues.get(row.offset, [])
        quality_status, quality_flags = _quality_fields(issues)
        storage = (
            "repacked_pointer_payload"
            if row.offset in allocations
            else "fixed_in_place"
        )
        inventory.append(
            {
                "record_id": f"SCRIPT:0x{row.offset:06X}",
                "kind": "script",
                "category": _category(
                    offset=row.offset,
                    layout=row.layout,
                    refs=pointer_refs,
                    graphical_starts=graphical_starts,
                ),
                "source_offset_hex": f"0x{row.offset:06X}",
                "pointer_references_hex": ";".join(
                    f"0x{ref:06X}" for ref in pointer_refs
                ),
                "layout": row.layout,
                "source_en": source["source_en"],
                "source_chinese": review.get("texte_chinois_source", ""),
                "fr_text": row.text,
                "fr_encoded_len": len(format_game_text(row.text, row.layout)),
                "planned_payload_len": len(planned_payload),
                "source_capacity": max_len,
                "pointer_count": len(pointer_refs),
                "storage": storage,
                "liveness_evidence": (
                    "live_pointer_reference"
                    if pointer_refs
                    else "canonical_fixed_text_inventory"
                ),
                "provenance": review.get(
                    "historique_traduction",
                    "english_2015_base_or_fixed_runtime_table",
                ),
                "quality_status": quality_status,
                "quality_flags": quality_flags,
                "review_status": "reviewed_current_source_of_truth",
                "notes": "",
            }
        )

    for item in FIXED_LIVE_TEXT_UNITS:
        offset = int(item["offset"])
        reference = int(item["reference"])
        text = str(item["fr_text"])
        payload = format_game_text(text)
        inventory.append(
            {
                "record_id": f"FIXED_LIVE:0x{offset:06X}",
                "kind": "fixed_live_text",
                "category": str(item["category"]),
                "source_offset_hex": f"0x{offset:06X}",
                "pointer_references_hex": f"0x{reference:06X}",
                "layout": "",
                "source_en": str(item["source_en"]),
                "source_chinese": "",
                "fr_text": text,
                "fr_encoded_len": len(payload),
                "planned_payload_len": len(payload),
                "source_capacity": int(item["source_capacity"]),
                "pointer_count": 1,
                "storage": str(item["storage"]),
                "liveness_evidence": str(item["liveness_evidence"]),
                "provenance": str(item["provenance"]),
                "quality_status": "no_automated_issue",
                "quality_flags": "",
                "review_status": "reviewed_current_source_of_truth",
                "notes": "",
            }
        )

    for reference, text in sorted(RESTORED_DIALOGUES.items()):
        review = dialogue_rows.get(f"RESTORE:0x{reference:06X}", {})
        issues = restoration_issues.get(reference, [])
        quality_status, quality_flags = _quality_fields(issues)
        payload = restoration_payloads[reference]
        inventory.append(
            {
                "record_id": f"RESTORE:0x{reference:06X}",
                "kind": "restoration",
                "category": "dialogue_restored_from_chinese",
                "source_offset_hex": "",
                "pointer_references_hex": f"0x{reference:06X}",
                "layout": DIALOGUE_LAYOUT,
                "source_en": review.get("traduction_anglaise_rom_anglaise", ""),
                "source_chinese": review.get("texte_chinois_source", ""),
                "fr_text": text,
                "fr_encoded_len": len(payload),
                "planned_payload_len": len(payload),
                "source_capacity": "",
                "pointer_count": 1,
                "storage": "synthetic_repacked_payload",
                "liveness_evidence": "verified_restored_pointer_slot",
                "provenance": review.get(
                    "historique_traduction",
                    "restored_from_canonical_chinese_inventory",
                ),
                "quality_status": quality_status,
                "quality_flags": quality_flags,
                "review_status": "reviewed_current_source_of_truth",
                "notes": "",
            }
        )

    for main_offset, variant in sorted(
        secondary_variants,
        key=lambda item: item[1].pointer_reference,
    ):
        reference = variant.pointer_reference
        provenance = variant_provenance[reference]
        issues = variant_issues.get(reference, [])
        quality_status, quality_flags = _quality_fields(issues)
        payload = format_game_text(variant.text)
        inventory.append(
            {
                "record_id": f"VARIANT:0x{reference:06X}",
                "kind": "pointer_variant",
                "category": "distinct_collapsed_pointer_semantics",
                "source_offset_hex": f"0x{main_offset:06X}",
                "pointer_references_hex": f"0x{reference:06X}",
                "layout": "",
                "source_en": "collapsed_into_shared_2015_english_payload",
                "source_chinese": provenance["chinese_text"],
                "fr_text": variant.text,
                "fr_encoded_len": len(payload),
                "planned_payload_len": len(payload),
                "source_capacity": "",
                "pointer_count": 1,
                "storage": "synthetic_repacked_payload",
                "liveness_evidence": "reviewed_distinct_pointer_slot",
                "provenance": provenance["fidelity_comment"],
                "quality_status": quality_status,
                "quality_flags": quality_flags,
                "review_status": provenance["review_status"],
                "notes": "",
            }
        )

    for spec in move_specs:
        issue_offset = 0x100000 + spec.move_index
        issues = move_issues.get(issue_offset, [])
        quality_status, quality_flags = _quality_fields(issues)
        inventory.append(
            {
                "record_id": f"MOVE:{spec.move_index:03d}",
                "kind": "move_graphic",
                "category": "two_line_move_label",
                "source_offset_hex": "",
                "pointer_references_hex": (
                    f"0x{MOVE_NAME_POINTER_TABLE_OFFSET + spec.move_index * 2:06X}"
                ),
                "layout": "two_line_graphical_cell",
                "source_en": "",
                "source_chinese": "",
                "fr_text": f"{spec.full_name} | {spec.line_1} / {spec.line_2}",
                "fr_encoded_len": len(format_game_text(spec.full_name)),
                "planned_payload_len": spec.required_payload_size,
                "source_capacity": "",
                "pointer_count": 1,
                "storage": "graphical_move_overlay",
                "liveness_evidence": "move_name_pointer_table",
                "provenance": "reviewed_fr_move_catalogue",
                "quality_status": quality_status,
                "quality_flags": quality_flags,
                "review_status": "reviewed_current_source_of_truth",
                "notes": "",
            }
        )

    inventory.sort(key=lambda row: str(row["record_id"]))
    all_issue_groups = (
        list(script_issues.values())
        + list(restoration_issues.values())
        + list(variant_issues.values())
        + list(move_issues.values())
    )
    quality_counts = _quality_summary(all_issue_groups)
    category_counts = Counter(str(row["category"]) for row in inventory)
    kind_counts = Counter(str(row["kind"]) for row in inventory)
    errors: list[str] = []
    expected_counts = {
        "script": EXPECTED_SCRIPT_ENTRY_COUNT,
        "fixed_live_text": EXPECTED_FIXED_LIVE_TEXT_COUNT,
        "restoration": EXPECTED_RESTORATION_COUNT,
        "move_graphic": EXPECTED_GRAPHICAL_MOVE_LABEL_COUNT,
        "pointer_variant": EXPECTED_SECONDARY_VARIANT_COUNT,
    }
    for kind, expected in expected_counts.items():
        actual = kind_counts[kind]
        if actual != expected:
            errors.append(f"{kind}: {actual} unités au lieu de {expected}")
    if len(inventory) != EXPECTED_REVIEWED_UNIT_COUNT:
        errors.append(
            f"inventaire: {len(inventory)} unités au lieu de "
            f"{EXPECTED_REVIEWED_UNIT_COUNT}"
        )
    if len(source_rows) != EXPECTED_SCRIPT_ENTRY_COUNT:
        errors.append("CSV script incomplet ou dupliqué")
    missing_correction_offsets = sorted(
        set(CERTAIN_TEXT_CORRECTION_OFFSETS) - set(source_rows)
    )
    if missing_correction_offsets:
        errors.append(
            "corrections certaines absentes du CSV: "
            + ", ".join(
                f"0x{offset:06X}" for offset in missing_correction_offsets
            )
        )
    if len({row["record_id"] for row in inventory}) != len(inventory):
        errors.append("identifiants de revue dupliqués")
    errors.extend(allocation_failures)
    if unsafe:
        errors.append(
            "lignes d'allocation non sûres: "
            + ", ".join(f"0x{offset:06X}" for offset in sorted(unsafe))
        )
    if quality_counts["high"]:
        errors.append(
            f"{quality_counts['high']} anomalie(s) linguistique(s) forte(s)"
        )

    summary = {
        "schema": "pokemon-yellow-nes-french-live-text-review/v1",
        "status": "PASS" if not errors else "FAIL",
        "scope": (
            "all current script entries, uncatalogued fixed live targets, "
            "restored Chinese dialogues, secondary pointer variants and "
            "graphical move labels"
        ),
        "reviewed_units": len(inventory),
        "expected_reviewed_units": EXPECTED_REVIEWED_UNIT_COUNT,
        "counts_by_kind": dict(sorted(kind_counts.items())),
        "counts_by_category": dict(sorted(category_counts.items())),
        "quality_heuristics": quality_counts,
        "corrections_this_review": {
            "live_source_entries": len(CERTAIN_TEXT_CORRECTION_OFFSETS),
            "live_source_offsets": [
                f"0x{offset:06X}"
                for offset in CERTAIN_TEXT_CORRECTION_OFFSETS
            ],
            "secondary_pointer_variants_created": 3,
            "pointer_join_targets_repaired_by_routine": 35,
            "fixed_runtime_records_patched_by_builder": 1,
            "status_already_control_flow_patches": 1,
            "battle_clear_width_patches": 1,
            "battle_newline_control_records": 4,
            "dynamic_pointer_entries_classified": len(
                DYNAMIC_LAYOUT_CLASSIFIED_REFS
            ),
            "live_dynamic_compositions_width_gated": len(
                LIVE_DYNAMIC_LAYOUT_REFS
            ),
            "dead_dynamic_pointer_entries": len(
                DEAD_UNREFERENCED_REFS
            ),
            "item_table_entries_width_gated": len(
                ITEM_LIST_NAME_EXPECTATIONS
            ),
            "dialogue_derivatives_resynchronized": 1,
            "counting_note": (
                "categories overlap and must not be added as unique texts"
            ),
        },
        "allocated_payloads_total": len(allocations),
        "allocated_script_payloads": sum(
            1
            for row, _, _ in row_info
            if row.offset in allocations
        ),
        "fixed_script_entries": sum(
            1
            for row, _, _ in row_info
            if row.offset not in allocations
        ),
        "script_rows_with_live_pointer_refs": sum(
            1
            for row, _, _ in row_info
            if any(refs for _, refs in row_pointer_refs[row.offset])
        ),
        "inputs": {
            "translation_csv": str(csv_path),
            "translation_csv_sha256": _sha256(csv_path),
            "canonical_english_rom": str(input_rom_path),
            "canonical_english_rom_sha256": hashlib.sha256(original).hexdigest(),
            "move_labels_csv": str(move_labels_path),
            "move_labels_csv_sha256": _sha256(move_labels_path),
            "pointer_variants_csv": str(pointer_variants_path),
            "pointer_variants_csv_sha256": _sha256(pointer_variants_path),
            "dialogue_review_csv": str(dialogue_review_path),
            "dialogue_review_csv_sha256": _sha256(dialogue_review_path),
        },
        "manual_decisions": [
            "Le sociolecte de 0x03C114 est une adaptation dialectale délibérée, conservée après relecture de provenance.",
            "Les statuts sont rendus sur la seconde ligne par leur callsite; « est empoisonné ! » et « est intoxiqué ! » restent donc complets et naturels.",
            f"La fenêtre de combat affiche {BATTLE_ARTIFACT_FREE_CELLS} cellules; la source n'en effaçait que 24, mais le builder étend le nettoyage aux colonnes 4 à 28 sans toucher la bordure. Toutes les compositions FR restent bornées à ces 25 cases.",
            "Un contrôle 0x0A gardé dans le moteur déplace uniquement quatre fragments relus vers la seconde ligne et refuse tout troisième rang.",
            "Les deux branches de statut déjà présent convergent vers le message autonome « Statut inchangé ! » puis sautent le second événement; les messages normaux restent inchangés.",
            "Les 40 noms du tableau Objets occupent au plus sept cases, laissant la huitième vide avant la quantité; EauFr. conserve l'identité Eau Fraîche issue du chinois.",
            "Les descriptions de Ball utilisent la grille historique 7x3; les quatre longueurs 14/20/21/18 et la troisième ligne ont été confirmées par une sonde contrôlée du renderer.",
            "EXP gagn. ! est une abréviation grammaticale et lisible imposée par le record fixe de douze cases; gagn. signifie gagnés.",
        ],
        "limitations": [
            "Inventaire et reconstruction statiques exhaustifs; la preuve visuelle cible le renderer, les transitions de combat et les descriptions Ball, pas un replay manuel de chaque scène.",
            "Les alertes moyennes/faibles sont heuristiques et incluent des noms propres ou termes Pokémon légitimes.",
            "Les pointeurs 0x0300A9, 0x0300AD, 0x0300DB et 0x0300DD sont conservés mais classés morts après audit exhaustif des callsites $891C; ils ne sont pas présentés comme messages exécutés.",
        ],
        "errors": errors,
    }
    return inventory, summary, errors


def write_outputs(
    inventory: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    csv_output: Path,
    json_output: Path,
    markdown_output: Path,
) -> None:
    for path in (csv_output, json_output, markdown_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    with csv_output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(inventory)
    json_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    kind_lines = "\n".join(
        f"- `{kind}` : {count}"
        for kind, count in summary["counts_by_kind"].items()
    )
    decision_lines = "\n".join(
        f"- {item}" for item in summary["manual_decisions"]
    )
    limitation_lines = "\n".join(
        f"- {item}" for item in summary["limitations"]
    )
    error_lines = (
        "\n".join(f"- {item}" for item in summary["errors"])
        if summary["errors"]
        else "- Aucune erreur bloquante."
    )
    quality = summary["quality_heuristics"]
    corrections = summary["corrections_this_review"]
    artifact_lines = ""
    if summary.get("artifacts"):
        artifact_lines = (
            "## Artefacts gelés\n\n"
            + "\n".join(
                f"- `{name}` : `{record['sha256']}` "
                f"({record['size']} octets) — `{record['path']}`"
                for name, record in summary["artifacts"].items()
            )
            + "\n\n"
        )
    markdown_output.write_text(
        "# Relecture exhaustive des textes français vivants\n\n"
        f"Résultat : **{summary['status']}**. "
        f"L'inventaire couvre **{summary['reviewed_units']}** unités "
        "de texte actuellement compilées ou injectées.\n\n"
        "## Couverture\n\n"
        f"{kind_lines}\n\n"
        "Le détail ligne par ligne se trouve dans "
        f"`{csv_output.name}`; les compteurs et empreintes sont dans "
        f"`{json_output.name}`.\n\n"
        "## Audit linguistique automatisé\n\n"
        f"- Signal fort : {quality['high']}\n"
        f"- Signal moyen : {quality['medium']}\n"
        f"- Signal faible : {quality['low']}\n\n"
        "Les signaux moyens et faibles restent visibles dans le CSV pour "
        "relecture; ils ne sont pas assimilés automatiquement à des fautes.\n\n"
        "## Corrections certaines de cette passe\n\n"
        f"- Entrées source vivantes corrigées : {corrections['live_source_entries']}\n"
        f"- Variantes secondaires créées : {corrections['secondary_pointer_variants_created']}\n"
        f"- Cibles de jointure réparées par la routine : {corrections['pointer_join_targets_repaired_by_routine']}\n"
        f"- Record fixe Antidote corrigé par le builder : {corrections['fixed_runtime_records_patched_by_builder']}\n"
        f"- Contrôle de flux statut déjà présent corrigé : {corrections['status_already_control_flow_patches']}\n"
        f"- Largeur d'effacement combat corrigée : {corrections['battle_clear_width_patches']}\n"
        f"- Fragments autorisés à utiliser le contrôle de ligne : {corrections['battle_newline_control_records']}\n"
        f"- Pointeurs dynamiques classés : {corrections['dynamic_pointer_entries_classified']}\n"
        f"- Compositions vivantes bornées : {corrections['live_dynamic_compositions_width_gated']}\n"
        f"- Pointeurs dynamiques morts attestés : {corrections['dead_dynamic_pointer_entries']}\n"
        f"- Noms de la table Objets bornés : {corrections['item_table_entries_width_gated']}\n"
        f"- Dérivés de dialogue resynchronisés : {corrections['dialogue_derivatives_resynchronized']}\n\n"
        "Ces catégories se recoupent; elles ne constituent pas un total additif. "
        f"Les {corrections['live_source_entries']} offsets sont consignés "
        "dans le résumé JSON.\n\n"
        f"{artifact_lines}"
        "## Décisions éditoriales bornées\n\n"
        f"{decision_lines}\n\n"
        "## Limites de la preuve\n\n"
        f"{limitation_lines}\n\n"
        "## Erreurs bloquantes\n\n"
        f"{error_lines}\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=Path("traduction_base.csv"))
    parser.add_argument(
        "--input-rom",
        type=Path,
        default=Path(TRANSLATION_BASE_ROM),
    )
    parser.add_argument(
        "--move-labels-csv",
        type=Path,
        default=DEFAULT_MOVE_LABEL_CATALOGUE,
    )
    parser.add_argument(
        "--pointer-variants-csv",
        type=Path,
        default=DEFAULT_FRENCH_POINTER_VARIANTS,
    )
    parser.add_argument(
        "--dialogue-review-csv",
        type=Path,
        default=Path("LISTE_EXHAUSTIVE_DIALOGUES.csv"),
    )
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_OUTPUT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument(
        "--markdown-output",
        type=Path,
        default=DEFAULT_MARKDOWN_OUTPUT,
    )
    parser.add_argument("--ips-base-rom", type=Path)
    parser.add_argument("--text-rom", type=Path)
    parser.add_argument("--text-ips", type=Path)
    parser.add_argument("--final-rom", type=Path)
    parser.add_argument("--final-ips", type=Path)
    parser.add_argument("--certified-rom", type=Path)
    parser.add_argument("--certified-ips", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    csv_path = _resolve(args.csv)
    input_rom_path = _resolve(args.input_rom)
    move_labels_path = _resolve(args.move_labels_csv)
    pointer_variants_path = _resolve(args.pointer_variants_csv)
    dialogue_review_path = _resolve(args.dialogue_review_csv)
    csv_output = _resolve(args.csv_output)
    json_output = _resolve(args.json_output)
    markdown_output = _resolve(args.markdown_output)
    inventory, summary, errors = build_full_review(
        csv_path=csv_path,
        input_rom_path=input_rom_path,
        move_labels_path=move_labels_path,
        pointer_variants_path=pointer_variants_path,
        dialogue_review_path=dialogue_review_path,
    )
    artifact_errors = attach_artifact_metadata(
        summary,
        (
            ("ips_base_rom", args.ips_base_rom),
            ("text_rom", args.text_rom),
            ("text_ips", args.text_ips),
            ("final_rom", args.final_rom),
            ("final_ips", args.final_ips),
            ("certified_rom", args.certified_rom),
            ("certified_ips", args.certified_ips),
        ),
    )
    errors.extend(artifact_errors)
    if errors:
        summary["status"] = "FAIL"
    write_outputs(
        inventory,
        summary,
        csv_output=csv_output,
        json_output=json_output,
        markdown_output=markdown_output,
    )
    print("Relecture exhaustive FR")
    print(f"- Unités : {len(inventory)}")
    print(f"- Signal fort : {summary['quality_heuristics']['high']}")
    print(f"- Erreurs bloquantes : {len(errors)}")
    print(f"- Inventaire : {csv_output}")
    print(f"- Résumé : {json_output}")
    print(f"- Rapport : {markdown_output}")
    print(f"- Résultat : {summary['status']}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
