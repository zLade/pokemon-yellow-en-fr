#!/usr/bin/env python3
"""Verify the final dialogue-review workbook without third-party libraries.

The verifier deliberately reads the XLSX package as ZIP/OpenXML instead of
loading it through a spreadsheet engine.  This makes it suitable for release
checks: formulas cannot be silently recalculated, cached errors remain visible,
and structural ranges are checked exactly.
"""

from __future__ import annotations

import argparse
import csv
import json
import posixpath
import re
import zipfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


ROM_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROM_DIR / "LISTE_EXHAUSTIVE_DIALOGUES.csv"
DEFAULT_XLSX = ROM_DIR / "build" / "LISTE_EXHAUSTIVE_DIALOGUES.xlsx"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
PACKAGE_REL_NS = (
    "http://schemas.openxmlformats.org/package/2006/relationships"
)
NS = {"m": MAIN_NS, "r": REL_NS, "pr": PACKAGE_REL_NS}

EXPECTED_SHEET_NAME = "Dialogues"
EXPECTED_ROW_COUNT = 1056
EXPECTED_COLUMN_COUNT = 16
EXPECTED_GRID_RANGE = "A1:P1056"
EXPECTED_FILTER_RANGE = EXPECTED_GRID_RANGE
EXPECTED_VALIDATION_RANGE = "O2:O1056"
EXPECTED_CONFIDENCE_RANGE = "K2:K1056"
EXPECTED_VERDICT_RANGE = "O2:O1056"
EXPECTED_HEADERS = (
    "id",
    "cle_stable",
    "categorie",
    "offset_ou_pointeur",
    "ligne_script",
    "layout",
    "intervenant",
    "texte_francais",
    "texte_chinois_source",
    "traduction_anglaise_rom_anglaise",
    "confiance_alignement",
    "historique_traduction",
    "naturalise",
    "corrige_d_apres_le_chinois",
    "votre_verdict",
    "votre_commentaire",
)

CELL_REFERENCE_RE = re.compile(r"^\$?([A-Za-z]{1,3})\$?([1-9][0-9]*)$")
STABLE_KEY_RE = re.compile(r"^(?:MAIN|RESTORED):0x[0-9A-F]{6}$")
EXCEL_ERROR_LITERALS = {
    "#NULL!",
    "#DIV/0!",
    "#VALUE!",
    "#REF!",
    "#NAME?",
    "#NUM!",
    "#N/A",
    "#GETTING_DATA",
    "#SPILL!",
    "#CALC!",
    "#FIELD!",
    "#BLOCKED!",
    "#UNKNOWN!",
    "#CONNECT!",
}


class WorkbookVerificationError(ValueError):
    """Raised for a malformed OpenXML package that cannot be inspected."""


@dataclass
class VerificationResult:
    """Machine- and human-readable result of a workbook verification."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def error(self, code: str, message: str) -> None:
        self.errors.append(f"[{code}] {message}")

    def warning(self, code: str, message: str) -> None:
        self.warnings.append(f"[{code}] {message}")

    def check(self, message: str) -> None:
        self.checks.append(message)

    def passed(self, *, strict: bool = False) -> bool:
        return not self.errors and (not strict or not self.warnings)

    def as_dict(self, *, strict: bool = False) -> dict[str, object]:
        return {
            "ok": self.passed(strict=strict),
            "strict": strict,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
        }


def _xml_tag(local_name: str) -> str:
    return f"{{{MAIN_NS}}}{local_name}"


def _column_number(name: str) -> int:
    value = 0
    for character in name.upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _column_name(number: int) -> str:
    if number < 1:
        raise ValueError("column number must be positive")
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def _parse_cell_reference(reference: str) -> tuple[int, int]:
    match = CELL_REFERENCE_RE.fullmatch(reference)
    if match is None:
        raise WorkbookVerificationError(
            f"référence de cellule OpenXML invalide : {reference!r}"
        )
    return int(match.group(2)), _column_number(match.group(1))


def _canonical_cell_reference(reference: str) -> str:
    row, column = _parse_cell_reference(reference)
    return f"{_column_name(column)}{row}"


def _canonical_range(reference: str) -> str:
    parts = reference.split(":")
    if len(parts) == 1:
        cell = _canonical_cell_reference(parts[0])
        return cell
    if len(parts) != 2:
        raise WorkbookVerificationError(
            f"plage OpenXML invalide : {reference!r}"
        )
    return ":".join(_canonical_cell_reference(part) for part in parts)


def _canonical_sqref(reference: str) -> list[str]:
    return [_canonical_range(part) for part in reference.split() if part]


def _short(value: str, limit: int = 120) -> str:
    escaped = value.replace("\r", "\\r").replace("\n", "\\n")
    if len(escaped) <= limit:
        return repr(escaped)
    return repr(escaped[: limit - 1] + "…")


def _load_csv(path: Path, result: VerificationResult) -> list[list[str]] | None:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = [list(row) for row in csv.reader(handle, strict=True)]
    except (OSError, UnicodeError, csv.Error) as exc:
        result.error("CSV_READ", f"impossible de lire {path}: {exc}")
        return None

    if len(rows) != EXPECTED_ROW_COUNT:
        result.error(
            "CSV_ROWS",
            f"{path} contient {len(rows)} lignes; "
            f"{EXPECTED_ROW_COUNT} attendues (en-tête inclus)",
        )
    bad_widths = [
        index
        for index, row in enumerate(rows, start=1)
        if len(row) != EXPECTED_COLUMN_COUNT
    ]
    if bad_widths:
        preview = ", ".join(str(index) for index in bad_widths[:8])
        suffix = "…" if len(bad_widths) > 8 else ""
        result.error(
            "CSV_COLUMNS",
            f"lignes non rectangulaires ({preview}{suffix}); "
            f"{EXPECTED_COLUMN_COUNT} colonnes attendues",
        )
    if not rows or any(len(row) != EXPECTED_COLUMN_COUNT for row in rows):
        return None

    if tuple(rows[0]) != EXPECTED_HEADERS:
        result.error(
            "CSV_HEADERS",
            "l'en-tête CSV ne correspond pas aux 16 colonnes canoniques; "
            f"reçu={rows[0]!r}",
        )

    ids = [row[0] for row in rows[1:]]
    expected_ids = [f"D{index:04d}" for index in range(1, EXPECTED_ROW_COUNT)]
    if ids != expected_ids:
        for position, (actual, expected) in enumerate(
            zip(ids, expected_ids), start=2
        ):
            if actual != expected:
                result.error(
                    "CSV_ID_SEQUENCE",
                    f"ligne {position}: ID {actual!r}; {expected!r} attendu",
                )
                break
        if len(ids) != len(expected_ids):
            result.error(
                "CSV_ID_SEQUENCE",
                f"{len(ids)} IDs présents; {len(expected_ids)} attendus",
            )

    duplicate_ids = sorted(
        value for value, count in Counter(ids).items() if value and count > 1
    )
    if duplicate_ids:
        result.error(
            "CSV_ID_DUPLICATE",
            "IDs dupliqués : " + ", ".join(duplicate_ids[:8]),
        )

    stable_keys = [row[1] for row in rows[1:]]
    bad_keys = [value for value in stable_keys if not STABLE_KEY_RE.fullmatch(value)]
    if bad_keys:
        result.error(
            "CSV_STABLE_KEY",
            "clé stable vide ou mal formée : " + _short(bad_keys[0]),
        )
    duplicate_keys = sorted(
        value
        for value, count in Counter(stable_keys).items()
        if value and count > 1
    )
    if duplicate_keys:
        result.error(
            "CSV_STABLE_KEY_DUPLICATE",
            "clés stables dupliquées : " + ", ".join(duplicate_keys[:8]),
        )

    if not result.errors:
        result.check(
            f"CSV canonique : {EXPECTED_ROW_COUNT} lignes × "
            f"{EXPECTED_COLUMN_COUNT} colonnes, IDs et clés stables uniques"
        )
    return rows


def _parse_xml(
    archive: zipfile.ZipFile,
    name: str,
) -> ET.Element:
    try:
        payload = archive.read(name)
    except KeyError as exc:
        raise WorkbookVerificationError(
            f"partie OpenXML obligatoire absente : {name}"
        ) from exc
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise WorkbookVerificationError(f"XML invalide dans {name}: {exc}") from exc


def _relationship_target(base_part: str, target: str) -> str:
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(base_part), target)
        )
    if resolved == ".." or resolved.startswith("../") or resolved.startswith("/"):
        raise WorkbookVerificationError(
            f"cible de relation hors paquet : {target!r}"
        )
    return resolved


def _relationships(
    archive: zipfile.ZipFile,
    rels_part: str,
    base_part: str,
) -> dict[str, tuple[str, str]]:
    root = _parse_xml(archive, rels_part)
    relationships: dict[str, tuple[str, str]] = {}
    for relationship in root.findall("pr:Relationship", NS):
        relationship_id = relationship.get("Id", "")
        if not relationship_id:
            raise WorkbookVerificationError(
                f"relation sans Id dans {rels_part}"
            )
        if relationship_id in relationships:
            raise WorkbookVerificationError(
                f"relation dupliquée {relationship_id!r} dans {rels_part}"
            )
        if relationship.get("TargetMode", "Internal") == "External":
            relationships[relationship_id] = (
                relationship.get("Type", ""),
                "EXTERNAL",
            )
            continue
        relationships[relationship_id] = (
            relationship.get("Type", ""),
            _relationship_target(base_part, relationship.get("Target", "")),
        )
    return relationships


def _shared_strings(
    archive: zipfile.ZipFile,
    relationships: dict[str, tuple[str, str]],
) -> list[str]:
    candidates = [
        target
        for relationship_type, target in relationships.values()
        if relationship_type.endswith("/sharedStrings")
        and target != "EXTERNAL"
    ]
    if not candidates:
        return []
    if len(candidates) != 1:
        raise WorkbookVerificationError(
            f"{len(candidates)} tables de chaînes partagées trouvées"
        )
    root = _parse_xml(archive, candidates[0])
    return [
        "".join(text.text or "" for text in item.findall(".//m:t", NS))
        for item in root.findall("m:si", NS)
    ]


def _styles_and_dxfs(
    archive: zipfile.ZipFile,
    relationships: dict[str, tuple[str, str]],
    result: VerificationResult,
) -> list[ET.Element]:
    candidates = [
        target
        for relationship_type, target in relationships.values()
        if relationship_type.endswith("/styles") and target != "EXTERNAL"
    ]
    if not candidates:
        return []
    if len(candidates) != 1:
        raise WorkbookVerificationError(
            f"{len(candidates)} feuilles de styles trouvées"
        )
    root = _parse_xml(archive, candidates[0])
    container = root.find("m:dxfs", NS)
    if container is None:
        return []
    dxfs = list(container.findall("m:dxf", NS))
    declared = container.get("count")
    if declared is not None and declared != str(len(dxfs)):
        result.error(
            "DXF_COUNT",
            f"styles différentiels : count={declared}, {len(dxfs)} éléments",
        )
    return dxfs


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t", "n")
    if cell_type == "inlineStr":
        inline = cell.find("m:is", NS)
        if inline is None:
            return ""
        return "".join(text.text or "" for text in inline.findall(".//m:t", NS))
    raw = cell.findtext("m:v", default="", namespaces=NS)
    if cell_type == "s":
        try:
            index = int(raw)
        except ValueError as exc:
            raise WorkbookVerificationError(
                f"index sharedStrings invalide {raw!r}"
            ) from exc
        if index < 0 or index >= len(shared_strings):
            raise WorkbookVerificationError(
                f"index sharedStrings hors limites : {index} / "
                f"{len(shared_strings)}"
            )
        return shared_strings[index]
    if cell_type == "b":
        return "TRUE" if raw == "1" else "FALSE"
    return raw


def _validate_dimension(root: ET.Element, result: VerificationResult) -> None:
    dimensions = root.findall("m:dimension", NS)
    if len(dimensions) != 1:
        result.error(
            "DIMENSION_COUNT",
            f"une seule dimension de feuille attendue; {len(dimensions)} trouvée(s)",
        )
        return
    reference = dimensions[0].get("ref", "")
    try:
        canonical = _canonical_range(reference)
    except WorkbookVerificationError as exc:
        result.error("DIMENSION_INVALID", str(exc))
        return
    if canonical != EXPECTED_GRID_RANGE:
        result.error(
            "DIMENSION_RANGE",
            f"dimension {canonical}; {EXPECTED_GRID_RANGE} attendue",
        )
    else:
        result.check(f"Dimension de feuille exacte : {EXPECTED_GRID_RANGE}")


def _validate_freeze(root: ET.Element, result: VerificationResult) -> None:
    panes = root.findall("m:sheetViews/m:sheetView/m:pane", NS)
    if len(panes) != 1:
        result.error(
            "FREEZE_PANE_COUNT",
            f"un volet figé attendu; {len(panes)} trouvé(s)",
        )
        return
    pane = panes[0]
    state = pane.get("state", "")
    if state != "frozen":
        result.error(
            "FREEZE_STATE",
            f"state={state!r}; 'frozen' attendu",
        )
    try:
        y_split = float(pane.get("ySplit", "0"))
        x_split = float(pane.get("xSplit", "0"))
    except ValueError:
        result.error(
            "FREEZE_SPLIT",
            f"séparation invalide xSplit={pane.get('xSplit')!r}, "
            f"ySplit={pane.get('ySplit')!r}",
        )
        return
    if y_split != 1:
        result.error(
            "FREEZE_ROW",
            f"ySplit={y_split:g}; seule la ligne 1 doit être figée",
        )
    if x_split not in {0, 2}:
        result.error(
            "FREEZE_COLUMNS",
            f"xSplit={x_split:g}; 0 ou 2 (colonnes A:B) attendu",
        )
    if x_split == 0:
        result.warning(
            "FREEZE_COLUMNS_RECOMMENDED",
            "les colonnes A:B ne sont pas figées (xSplit=2 recommandé)",
        )
    expected_top_left = "C2" if x_split == 2 else "A2"
    top_left = pane.get("topLeftCell", "")
    if top_left != expected_top_left:
        result.error(
            "FREEZE_TOP_LEFT",
            f"topLeftCell={top_left!r}; {expected_top_left!r} attendu",
        )
    if state == "frozen" and y_split == 1 and x_split in {0, 2} and top_left == expected_top_left:
        description = "ligne 1 et colonnes A:B" if x_split == 2 else "ligne 1"
        result.check(f"Volets figés correctement : {description}")


def _worksheet_relationships_part(worksheet_part: str) -> str:
    return posixpath.join(
        posixpath.dirname(worksheet_part),
        "_rels",
        posixpath.basename(worksheet_part) + ".rels",
    )


def _validate_filter(
    archive: zipfile.ZipFile,
    root: ET.Element,
    worksheet_part: str,
    names: set[str],
    result: VerificationResult,
) -> None:
    filters: list[tuple[str, str]] = []
    for element in root.findall("m:autoFilter", NS):
        filters.append(("feuille", element.get("ref", "")))

    table_parts = root.find("m:tableParts", NS)
    table_elements = [] if table_parts is None else list(table_parts.findall("m:tablePart", NS))
    if table_parts is not None:
        declared = table_parts.get("count")
        if declared is not None and declared != str(len(table_elements)):
            result.error(
                "TABLE_PART_COUNT",
                f"tableParts count={declared}; {len(table_elements)} relation(s)",
            )
    if table_elements:
        rels_part = _worksheet_relationships_part(worksheet_part)
        if rels_part not in names:
            result.error(
                "TABLE_RELATIONSHIPS",
                f"relations de table absentes : {rels_part}",
            )
        else:
            table_relationships = _relationships(
                archive,
                rels_part,
                worksheet_part,
            )
            for table_part in table_elements:
                relationship_id = table_part.get(f"{{{REL_NS}}}id", "")
                relationship = table_relationships.get(relationship_id)
                if relationship is None:
                    result.error(
                        "TABLE_RELATIONSHIP",
                        f"relation de table inconnue : {relationship_id!r}",
                    )
                    continue
                relationship_type, target = relationship
                if target == "EXTERNAL" or not relationship_type.endswith("/table"):
                    result.error(
                        "TABLE_RELATIONSHIP",
                        f"relation {relationship_id!r} non interne ou non-table",
                    )
                    continue
                table_root = _parse_xml(archive, target)
                table_formulas = table_root.findall(
                    ".//m:calculatedColumnFormula",
                    NS,
                ) + table_root.findall(".//m:totalsRowFormula", NS)
                if table_formulas:
                    result.error(
                        "UNEXPECTED_TABLE_FORMULA",
                        f"table {target}: {len(table_formulas)} formule(s) "
                        "de colonne/total inattendue(s)",
                    )
                table_reference = table_root.get("ref", "")
                try:
                    canonical_table = _canonical_range(table_reference)
                except WorkbookVerificationError as exc:
                    result.error("TABLE_RANGE_INVALID", str(exc))
                    continue
                if canonical_table != EXPECTED_GRID_RANGE:
                    result.error(
                        "TABLE_RANGE",
                        f"table {canonical_table}; {EXPECTED_GRID_RANGE} attendue",
                    )
                auto_filter = table_root.find("m:autoFilter", NS)
                if auto_filter is None:
                    result.error(
                        "FILTER_MISSING",
                        f"la table {target} ne contient pas d'autoFilter",
                    )
                else:
                    filters.append((f"table {target}", auto_filter.get("ref", "")))
                columns = table_root.find("m:tableColumns", NS)
                if columns is not None:
                    actual_columns = len(columns.findall("m:tableColumn", NS))
                    declared_columns = columns.get("count")
                    if actual_columns != EXPECTED_COLUMN_COUNT or (
                        declared_columns is not None
                        and declared_columns != str(actual_columns)
                    ):
                        result.error(
                            "TABLE_COLUMNS",
                            f"table {target}: {actual_columns} colonnes, "
                            f"count={declared_columns!r}; "
                            f"{EXPECTED_COLUMN_COUNT} attendues",
                        )

    if len(filters) != 1:
        result.error(
            "FILTER_COUNT",
            f"un seul filtre effectif attendu; {len(filters)} trouvé(s)",
        )
        return
    source, reference = filters[0]
    try:
        canonical = _canonical_range(reference)
    except WorkbookVerificationError as exc:
        result.error("FILTER_RANGE_INVALID", str(exc))
        return
    if canonical != EXPECTED_FILTER_RANGE:
        result.error(
            "FILTER_RANGE",
            f"filtre de {source} sur {canonical}; "
            f"{EXPECTED_FILTER_RANGE} attendu",
        )
    else:
        result.check(f"Filtre exact : {EXPECTED_FILTER_RANGE} ({source})")


def _parse_inline_list(formula: str) -> list[str] | None:
    value = formula.strip()
    if value.startswith("="):
        value = value[1:].strip()
    if len(value) < 2 or not (value.startswith('"') and value.endswith('"')):
        return None
    payload = value[1:-1].replace('""', '"')
    separator = ";" if ";" in payload and "," not in payload else ","
    return [item.strip() for item in payload.split(separator) if item.strip()]


def _validate_data_validation(
    root: ET.Element,
    result: VerificationResult,
) -> list[str] | None:
    containers = root.findall("m:dataValidations", NS)
    validations: list[ET.Element] = []
    for container in containers:
        items = container.findall("m:dataValidation", NS)
        declared = container.get("count")
        if declared is not None and declared != str(len(items)):
            result.error(
                "VALIDATION_COUNT_DECLARED",
                f"dataValidations count={declared}; {len(items)} règle(s)",
            )
        validations.extend(items)
    if len(validations) != 1:
        result.error(
            "VALIDATION_COUNT",
            f"une validation de liste attendue; {len(validations)} trouvée(s)",
        )
        return None

    validation = validations[0]
    if validation.get("type") != "list":
        result.error(
            "VALIDATION_TYPE",
            f"type={validation.get('type')!r}; 'list' attendu",
        )
    try:
        references = _canonical_sqref(validation.get("sqref", ""))
    except WorkbookVerificationError as exc:
        result.error("VALIDATION_RANGE_INVALID", str(exc))
        references = []
    if references != [EXPECTED_VALIDATION_RANGE]:
        result.error(
            "VALIDATION_RANGE",
            f"plage(s) {references!r}; "
            f"[{EXPECTED_VALIDATION_RANGE!r}] attendue",
        )
    allow_blank = validation.get("allowBlank", "0").lower() in {"1", "true"}
    if not allow_blank:
        result.error(
            "VALIDATION_ALLOW_BLANK",
            "allowBlank=1 attendu car la colonne O est initialement vide",
        )
    hides_arrow = validation.get("showDropDown", "0").lower() in {"1", "true"}
    if hides_arrow:
        result.error(
            "VALIDATION_DROPDOWN",
            "showDropDown=1 masque la flèche de liste dans Excel",
        )
    formula = validation.findtext("m:formula1", default="", namespaces=NS).strip()
    if not formula:
        result.error(
            "VALIDATION_FORMULA",
            "formula1 est vide; aucun verdict ne serait proposé",
        )
        return None
    options = _parse_inline_list(formula)
    if options is not None:
        if len(set(options)) < 2:
            result.error(
                "VALIDATION_OPTIONS",
                f"au moins deux verdicts distincts attendus; reçu={options!r}",
            )
        elif references == [EXPECTED_VALIDATION_RANGE]:
            result.check(
                f"Validation de liste exacte : {EXPECTED_VALIDATION_RANGE}, "
                f"{len(options)} verdicts"
            )
    elif references == [EXPECTED_VALIDATION_RANGE]:
        result.check(
            f"Validation de liste exacte : {EXPECTED_VALIDATION_RANGE} "
            "(source par formule/plage)"
        )
    return options


def _dxf_is_meaningful(dxf: ET.Element) -> bool:
    meaningful_names = {"font", "fill", "border", "numFmt", "alignment"}
    return any(child.tag.rsplit("}", 1)[-1] in meaningful_names for child in dxf)


def _conditional_rule_is_useful(
    rule: ET.Element,
    dxfs: list[ET.Element],
    result: VerificationResult,
) -> bool:
    rule_type = rule.get("type", "")
    visual_types = {"colorScale", "dataBar", "iconSet"}
    if rule_type in visual_types:
        visual = rule.find(f"m:{rule_type}", NS)
        return visual is not None and bool(list(visual))

    styled = False
    dxf_id = rule.get("dxfId")
    if dxf_id is not None:
        try:
            index = int(dxf_id)
        except ValueError:
            result.error("CONDITIONAL_DXF", f"dxfId invalide : {dxf_id!r}")
        else:
            if index < 0 or index >= len(dxfs):
                result.error(
                    "CONDITIONAL_DXF",
                    f"dxfId={index} hors limites (0..{len(dxfs) - 1})",
                )
            else:
                styled = _dxf_is_meaningful(dxfs[index])
    inline_dxf = rule.find("m:dxf", NS)
    if inline_dxf is not None and _dxf_is_meaningful(inline_dxf):
        styled = True

    has_predicate = bool(rule.get("text")) or any(
        (formula.text or "").strip() for formula in rule.findall("m:formula", NS)
    )
    return styled and has_predicate


def _rule_condition_text(rule: ET.Element) -> str:
    pieces = [rule.get("text", "")]
    pieces.extend(formula.text or "" for formula in rule.findall("m:formula", NS))
    return " ".join(pieces).casefold()


def _validate_conditional_formatting(
    root: ET.Element,
    dxfs: list[ET.Element],
    csv_rows: list[list[str]],
    validation_options: list[str] | None,
    result: VerificationResult,
) -> None:
    rules_by_range: dict[str, list[ET.Element]] = {
        EXPECTED_CONFIDENCE_RANGE: [],
        EXPECTED_VERDICT_RANGE: [],
    }
    priorities: list[int] = []
    for block in root.findall("m:conditionalFormatting", NS):
        try:
            references = _canonical_sqref(block.get("sqref", ""))
        except WorkbookVerificationError as exc:
            result.error("CONDITIONAL_RANGE_INVALID", str(exc))
            continue
        if len(references) != 1 or references[0] not in rules_by_range:
            result.error(
                "CONDITIONAL_RANGE",
                f"plage(s) {references!r}; seules "
                f"{EXPECTED_CONFIDENCE_RANGE} et "
                f"{EXPECTED_VERDICT_RANGE} sont attendues",
            )
            continue
        rules = block.findall("m:cfRule", NS)
        rules_by_range[references[0]].extend(rules)
        for rule in rules:
            raw_priority = rule.get("priority")
            try:
                priority = int(raw_priority or "")
            except ValueError:
                result.error(
                    "CONDITIONAL_PRIORITY",
                    f"priorité invalide {raw_priority!r} sur {references[0]}",
                )
            else:
                if priority < 1:
                    result.error(
                        "CONDITIONAL_PRIORITY",
                        f"priorité {priority} invalide sur {references[0]}",
                    )
                priorities.append(priority)

    duplicate_priorities = sorted(
        priority
        for priority, count in Counter(priorities).items()
        if count > 1
    )
    if duplicate_priorities:
        result.error(
            "CONDITIONAL_PRIORITY_DUPLICATE",
            "priorités dupliquées : "
            + ", ".join(str(value) for value in duplicate_priorities),
        )

    confidence_values = sorted(
        {row[10].strip() for row in csv_rows[1:] if row[10].strip()},
        key=str.casefold,
    )
    for reference, rules in rules_by_range.items():
        useful = [
            rule
            for rule in rules
            if _conditional_rule_is_useful(rule, dxfs, result)
        ]
        if len(useful) < 2:
            result.error(
                "CONDITIONAL_USEFUL_RULES",
                f"{reference}: {len(useful)} règle(s) conditionnelle(s) "
                "stylée(s) et exploitable(s); au moins 2 attendues",
            )
            continue

        conditions = [_rule_condition_text(rule) for rule in useful]
        expected_values = (
            confidence_values
            if reference == EXPECTED_CONFIDENCE_RANGE
            else (validation_options or [])
        )
        if expected_values:
            covered = {
                value
                for value in expected_values
                if any(value.casefold() in condition for condition in conditions)
            }
            if len(covered) < min(2, len(set(expected_values))):
                result.error(
                    "CONDITIONAL_STATUS_COVERAGE",
                    f"{reference}: les règles ne distinguent que "
                    f"{sorted(covered)!r}; au moins deux états de "
                    f"{expected_values!r} sont attendus",
                )
                continue
        result.check(
            f"Formats conditionnels utiles : {reference} "
            f"({len(useful)} règles stylées)"
        )


def _validate_cells(
    root: ET.Element,
    shared_strings: list[str],
    csv_rows: list[list[str]],
    result: VerificationResult,
    *,
    max_value_errors: int,
    validation_options: list[str] | None,
) -> None:
    values: dict[tuple[int, int], str] = {}
    formula_cells: list[str] = []
    error_cells: list[tuple[str, str]] = []
    outside_cells: list[str] = []
    bad_row_cells: list[str] = []

    rows_seen: set[int] = set()
    for row_element in root.findall("m:sheetData/m:row", NS):
        raw_row = row_element.get("r", "")
        try:
            row_number = int(raw_row)
        except ValueError:
            result.error("ROW_REFERENCE", f"numéro de ligne invalide : {raw_row!r}")
            continue
        if row_number in rows_seen:
            result.error("ROW_DUPLICATE", f"ligne {row_number} dupliquée")
        rows_seen.add(row_number)
        if row_number < 1 or row_number > EXPECTED_ROW_COUNT:
            result.error(
                "ROW_OUTSIDE_GRID",
                f"ligne physique {row_number} hors de 1:{EXPECTED_ROW_COUNT}",
            )
        for cell in row_element.findall("m:c", NS):
            reference = cell.get("r", "")
            try:
                cell_row, cell_column = _parse_cell_reference(reference)
            except WorkbookVerificationError as exc:
                result.error("CELL_REFERENCE", str(exc))
                continue
            canonical = f"{_column_name(cell_column)}{cell_row}"
            if cell_row != row_number:
                bad_row_cells.append(
                    f"{canonical} déclaré dans la ligne XML {row_number}"
                )
            key = (cell_row, cell_column)
            if key in values:
                result.error("CELL_DUPLICATE", f"cellule {canonical} dupliquée")
                continue
            if cell.find("m:f", NS) is not None:
                formula_cells.append(canonical)
            try:
                value = _cell_value(cell, shared_strings)
            except WorkbookVerificationError as exc:
                result.error("CELL_VALUE", f"{canonical}: {exc}")
                value = ""
            values[key] = value
            if cell.get("t") == "e" or value.strip().upper() in EXCEL_ERROR_LITERALS:
                error_cells.append((canonical, value))
            if not (
                1 <= cell_row <= EXPECTED_ROW_COUNT
                and 1 <= cell_column <= EXPECTED_COLUMN_COUNT
            ):
                outside_cells.append(canonical)

    if bad_row_cells:
        result.error(
            "CELL_ROW_MISMATCH",
            "; ".join(bad_row_cells[:8]),
        )
    if formula_cells:
        preview = ", ".join(formula_cells[:12])
        suffix = "…" if len(formula_cells) > 12 else ""
        result.error(
            "UNEXPECTED_FORMULA",
            f"{len(formula_cells)} cellule(s) avec formule : {preview}{suffix}",
        )
    if error_cells:
        preview = ", ".join(
            f"{reference}={value!r}" for reference, value in error_cells[:12]
        )
        suffix = "…" if len(error_cells) > 12 else ""
        result.error(
            "EXCEL_ERROR",
            f"{len(error_cells)} erreur(s) Excel : {preview}{suffix}",
        )
    if outside_cells:
        preview = ", ".join(outside_cells[:12])
        suffix = "…" if len(outside_cells) > 12 else ""
        result.error(
            "CELL_OUTSIDE_GRID",
            f"{len(outside_cells)} cellule(s) hors de "
            f"{EXPECTED_GRID_RANGE} : {preview}{suffix}",
        )

    mismatches: list[str] = []
    mismatch_count = 0
    invalid_verdicts: list[str] = []
    for row_index, expected_row in enumerate(csv_rows, start=1):
        expected_id = expected_row[0] if row_index > 1 else "en-tête"
        stable_key = expected_row[1] if row_index > 1 else "en-tête"
        for column_index, expected in enumerate(expected_row, start=1):
            actual = values.get((row_index, column_index), "")
            if row_index > 1 and column_index in (15, 16):
                if (
                    column_index == 15
                    and actual
                    and validation_options is not None
                    and actual not in validation_options
                ):
                    invalid_verdicts.append(
                        f"O{row_index} (ID={expected_id}, clé={stable_key})="
                        f"{_short(actual)}"
                    )
                # O:P are reviewer-owned and deliberately survive a refresh.
                continue
            if actual == expected:
                continue
            mismatch_count += 1
            if len(mismatches) >= max_value_errors:
                continue
            reference = f"{_column_name(column_index)}{row_index}"
            mismatches.append(
                f"{reference} (ID={expected_id}, clé={stable_key}) : "
                f"attendu {_short(expected)}, reçu {_short(actual)}"
            )
    if mismatch_count:
        suffix = ""
        if mismatch_count > len(mismatches):
            suffix = (
                f"; {mismatch_count - len(mismatches)} autre(s) "
                "écart(s) non affiché(s)"
            )
        result.error(
            "VALUE_MISMATCH",
            f"{mismatch_count} valeur(s) différente(s) : "
            + " | ".join(mismatches)
            + suffix,
        )
    if invalid_verdicts:
        result.error(
            "FEEDBACK_VERDICT",
            "verdict(s) hors liste : " + " | ".join(invalid_verdicts[:20]),
        )
    else:
        if not mismatch_count:
            exact_count = EXPECTED_COLUMN_COUNT + (
                (EXPECTED_ROW_COUNT - 1) * 14
            )
            result.check(
                f"Valeurs source exactes : {exact_count} cellules A:N "
                "et en-têtes comparés au CSV; retours O:P préservables"
            )


def _verify_package(
    xlsx_path: Path,
    csv_rows: list[list[str]],
    result: VerificationResult,
    *,
    sheet_name: str,
    max_value_errors: int,
) -> None:
    try:
        archive = zipfile.ZipFile(xlsx_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise WorkbookVerificationError(
            f"impossible d'ouvrir {xlsx_path} comme XLSX : {exc}"
        ) from exc

    with archive:
        infos = archive.infolist()
        names_list = [info.filename for info in infos]
        names = set(names_list)
        duplicates = sorted(
            name for name, count in Counter(names_list).items() if count > 1
        )
        if duplicates:
            raise WorkbookVerificationError(
                "parties ZIP dupliquées : " + ", ".join(duplicates[:8])
            )
        dangerous = [
            name
            for name in names
            if name.startswith("/")
            or posixpath.normpath(name) == ".."
            or posixpath.normpath(name).startswith("../")
        ]
        if dangerous:
            raise WorkbookVerificationError(
                "chemins ZIP dangereux : " + ", ".join(sorted(dangerous)[:8])
            )
        encrypted = [info.filename for info in infos if info.flag_bits & 0x1]
        if encrypted:
            raise WorkbookVerificationError(
                "parties ZIP chiffrées non vérifiables : "
                + ", ".join(encrypted[:8])
            )
        try:
            bad_crc = archive.testzip()
        except (OSError, zipfile.BadZipFile) as exc:
            raise WorkbookVerificationError(f"erreur CRC/ZIP : {exc}") from exc
        if bad_crc is not None:
            raise WorkbookVerificationError(f"CRC ZIP invalide : {bad_crc}")

        workbook_part = "xl/workbook.xml"
        workbook_root = _parse_xml(archive, workbook_part)
        workbook_relationships = _relationships(
            archive,
            "xl/_rels/workbook.xml.rels",
            workbook_part,
        )
        sheets = workbook_root.findall("m:sheets/m:sheet", NS)
        if len(sheets) != 1:
            result.error(
                "SHEET_COUNT",
                f"une seule feuille attendue; {len(sheets)} trouvée(s)",
            )
        matching_sheets = [sheet for sheet in sheets if sheet.get("name") == sheet_name]
        if len(matching_sheets) != 1:
            names_found = [sheet.get("name", "") for sheet in sheets]
            result.error(
                "SHEET_NAME",
                f"feuille {sheet_name!r} introuvable ou dupliquée; "
                f"feuilles={names_found!r}",
            )
            return
        sheet = matching_sheets[0]
        if sheet.get("state", "visible") != "visible":
            result.error("SHEET_HIDDEN", f"la feuille {sheet_name!r} est masquée")
        relationship_id = sheet.get(f"{{{REL_NS}}}id", "")
        relationship = workbook_relationships.get(relationship_id)
        if relationship is None:
            raise WorkbookVerificationError(
                f"relation de feuille inconnue : {relationship_id!r}"
            )
        relationship_type, worksheet_part = relationship
        if worksheet_part == "EXTERNAL" or not relationship_type.endswith("/worksheet"):
            raise WorkbookVerificationError(
                f"relation {relationship_id!r} non interne ou non-worksheet"
            )
        if worksheet_part not in names:
            raise WorkbookVerificationError(
                f"partie de feuille absente : {worksheet_part}"
            )

        shared_strings = _shared_strings(archive, workbook_relationships)
        dxfs = _styles_and_dxfs(archive, workbook_relationships, result)
        worksheet_root = _parse_xml(archive, worksheet_part)

        _validate_dimension(worksheet_root, result)
        _validate_freeze(worksheet_root, result)
        _validate_filter(
            archive,
            worksheet_root,
            worksheet_part,
            names,
            result,
        )
        validation_options = _validate_data_validation(worksheet_root, result)
        _validate_conditional_formatting(
            worksheet_root,
            dxfs,
            csv_rows,
            validation_options,
            result,
        )
        _validate_cells(
            worksheet_root,
            shared_strings,
            csv_rows,
            result,
            max_value_errors=max_value_errors,
            validation_options=validation_options,
        )
        if len(sheets) == 1 and sheet.get("state", "visible") == "visible":
            result.check(f"Feuille unique et visible : {sheet_name}")


def verify_dialogue_review_xlsx(
    xlsx_path: Path,
    csv_path: Path,
    *,
    sheet_name: str = EXPECTED_SHEET_NAME,
    max_value_errors: int = 20,
) -> VerificationResult:
    """Return a complete audit report for the dialogue-review workbook."""

    result = VerificationResult()
    if max_value_errors < 1:
        result.error("ARGUMENT", "max_value_errors doit être supérieur à zéro")
        return result
    csv_rows = _load_csv(csv_path, result)
    if csv_rows is None or len(csv_rows) != EXPECTED_ROW_COUNT:
        return result
    try:
        _verify_package(
            xlsx_path,
            csv_rows,
            result,
            sheet_name=sheet_name,
            max_value_errors=max_value_errors,
        )
    except WorkbookVerificationError as exc:
        result.error("XLSX_PACKAGE", str(exc))
    return result


def _print_text_report(
    result: VerificationResult,
    *,
    xlsx_path: Path,
    csv_path: Path,
    strict: bool,
) -> None:
    status = "OK" if result.passed(strict=strict) else "ÉCHEC"
    print(f"{status} — vérification du classeur de relecture")
    print(f"XLSX : {xlsx_path}")
    print(f"CSV  : {csv_path}")
    for check in result.checks:
        print(f"  ✓ {check}")
    for warning in result.warnings:
        label = "ERREUR (mode strict)" if strict else "AVERTISSEMENT"
        print(f"  ! {label} {warning}")
    for error in result.errors:
        print(f"  ✗ {error}")
    print(
        f"Bilan : {len(result.errors)} erreur(s), "
        f"{len(result.warnings)} avertissement(s)"
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Vérifie le classeur XLSX de relecture des 1 055 dialogues "
            "contre son CSV canonique."
        )
    )
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--sheet-name", default=EXPECTED_SHEET_NAME)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="traite les recommandations (dont le gel A:B) comme des erreurs",
    )
    parser.add_argument(
        "--max-value-errors",
        type=int,
        default=20,
        help="nombre maximal d'écarts de valeurs détaillés (défaut : 20)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="émet un rapport JSON exploitable par le build",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    result = verify_dialogue_review_xlsx(
        args.xlsx,
        args.csv,
        sheet_name=args.sheet_name,
        max_value_errors=args.max_value_errors,
    )
    if args.json:
        print(json.dumps(result.as_dict(strict=args.strict), ensure_ascii=False, indent=2))
    else:
        _print_text_report(
            result,
            xlsx_path=args.xlsx,
            csv_path=args.csv,
            strict=args.strict,
        )
    return 0 if result.passed(strict=args.strict) else 1


if __name__ == "__main__":
    raise SystemExit(main())
