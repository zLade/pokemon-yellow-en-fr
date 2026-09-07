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
    "stable_key",
    "category",
    "source_offset_or_pointer",
    "script_line",
    "layout",
    "speaker",
    "french_reference_text",
    "chinese_text",
    "english_2015",
    "alignment_confidence",
    "translation_history",
    "naturalized",
    "chinese_fidelity_corrected",
    "review_verdict",
    "review_comment",
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
            f"invalid OpenXML cell reference: {reference!r}"
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
            f"invalid OpenXML range: {reference!r}"
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
        result.error("CSV_READ", f"cannot read {path}: {exc}")
        return None

    if len(rows) != EXPECTED_ROW_COUNT:
        result.error(
            "CSV_ROWS",
            f"{path} contains {len(rows)} rows; "
            f"{EXPECTED_ROW_COUNT} expected (including header)",
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
            f"non-rectangular rows ({preview}{suffix}); "
            f"{EXPECTED_COLUMN_COUNT} columns expected",
        )
    if not rows or any(len(row) != EXPECTED_COLUMN_COUNT for row in rows):
        return None

    if tuple(rows[0]) != EXPECTED_HEADERS:
        result.error(
            "CSV_HEADERS",
            "CSV header does not match the 16 canonical columns; "
            f"received={rows[0]!r}",
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
                    f"row {position}: ID {actual!r}; {expected!r} expected",
                )
                break
        if len(ids) != len(expected_ids):
            result.error(
                "CSV_ID_SEQUENCE",
                f"{len(ids)} IDs present; {len(expected_ids)} expected",
            )

    duplicate_ids = sorted(
        value for value, count in Counter(ids).items() if value and count > 1
    )
    if duplicate_ids:
        result.error(
            "CSV_ID_DUPLICATE",
            "duplicate IDs: " + ", ".join(duplicate_ids[:8]),
        )

    stable_keys = [row[1] for row in rows[1:]]
    bad_keys = [value for value in stable_keys if not STABLE_KEY_RE.fullmatch(value)]
    if bad_keys:
        result.error(
            "CSV_STABLE_KEY",
            "empty or malformed stable key: " + _short(bad_keys[0]),
        )
    duplicate_keys = sorted(
        value
        for value, count in Counter(stable_keys).items()
        if value and count > 1
    )
    if duplicate_keys:
        result.error(
            "CSV_STABLE_KEY_DUPLICATE",
            "duplicate stable keys: " + ", ".join(duplicate_keys[:8]),
        )

    if not result.errors:
        result.check(
            f"Canonical CSV: {EXPECTED_ROW_COUNT} rows × "
            f"{EXPECTED_COLUMN_COUNT} columns, unique IDs and stable keys"
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
            f"required OpenXML part missing: {name}"
        ) from exc
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise WorkbookVerificationError(f"invalid XML in {name}: {exc}") from exc


def _relationship_target(base_part: str, target: str) -> str:
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        resolved = posixpath.normpath(
            posixpath.join(posixpath.dirname(base_part), target)
        )
    if resolved == ".." or resolved.startswith("../") or resolved.startswith("/"):
        raise WorkbookVerificationError(
            f"relationship target outside package: {target!r}"
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
                f"relationship without Id in {rels_part}"
            )
        if relationship_id in relationships:
            raise WorkbookVerificationError(
                f"duplicate relationship {relationship_id!r} in {rels_part}"
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
            f"{len(candidates)} shared string tables found"
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
            f"{len(candidates)} stylesheets found"
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
            f"differential styles: count={declared}, {len(dxfs)} elements",
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
                f"invalid sharedStrings index {raw!r}"
            ) from exc
        if index < 0 or index >= len(shared_strings):
            raise WorkbookVerificationError(
                f"sharedStrings index out of bounds: {index} / "
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
            f"exactly one worksheet dimension expected; {len(dimensions)} found",
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
            f"dimension {canonical}; {EXPECTED_GRID_RANGE} expected",
        )
    else:
        result.check(f"Exact worksheet dimension: {EXPECTED_GRID_RANGE}")


def _validate_freeze(root: ET.Element, result: VerificationResult) -> None:
    panes = root.findall("m:sheetViews/m:sheetView/m:pane", NS)
    if len(panes) != 1:
        result.error(
            "FREEZE_PANE_COUNT",
            f"one frozen pane expected; {len(panes)} found",
        )
        return
    pane = panes[0]
    state = pane.get("state", "")
    if state != "frozen":
        result.error(
            "FREEZE_STATE",
            f"state={state!r}; 'frozen' expected",
        )
    try:
        y_split = float(pane.get("ySplit", "0"))
        x_split = float(pane.get("xSplit", "0"))
    except ValueError:
        result.error(
            "FREEZE_SPLIT",
            f"invalid split xSplit={pane.get('xSplit')!r}, "
            f"ySplit={pane.get('ySplit')!r}",
        )
        return
    if y_split != 1:
        result.error(
            "FREEZE_ROW",
            f"ySplit={y_split:g}; only row 1 must be frozen",
        )
    if x_split not in {0, 2}:
        result.error(
            "FREEZE_COLUMNS",
            f"xSplit={x_split:g}; 0 or 2 (columns A:B) expected",
        )
    if x_split == 0:
        result.warning(
            "FREEZE_COLUMNS_RECOMMENDED",
            "columns A:B are not frozen (xSplit=2 recommended)",
        )
    expected_top_left = "C2" if x_split == 2 else "A2"
    top_left = pane.get("topLeftCell", "")
    if top_left != expected_top_left:
        result.error(
            "FREEZE_TOP_LEFT",
            f"topLeftCell={top_left!r}; {expected_top_left!r} expected",
        )
    if state == "frozen" and y_split == 1 and x_split in {0, 2} and top_left == expected_top_left:
        description = "row 1 and columns A:B" if x_split == 2 else "row 1"
        result.check(f"Correctly frozen panes: {description}")


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
        filters.append(("worksheet", element.get("ref", "")))

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
                f"missing table relationships: {rels_part}",
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
                        f"unknown table relationship: {relationship_id!r}",
                    )
                    continue
                relationship_type, target = relationship
                if target == "EXTERNAL" or not relationship_type.endswith("/table"):
                    result.error(
                        "TABLE_RELATIONSHIP",
                        f"relation {relationship_id!r} is external or is not a table relationship",
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
                        f"table {target}: {len(table_formulas)} unexpected "
                        "column/total formulas",
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
                        f"table {canonical_table}; {EXPECTED_GRID_RANGE} expected",
                    )
                auto_filter = table_root.find("m:autoFilter", NS)
                if auto_filter is None:
                    result.error(
                        "FILTER_MISSING",
                        f"table {target} has no autoFilter",
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
                            f"table {target}: {actual_columns} columns, "
                            f"count={declared_columns!r}; "
                            f"{EXPECTED_COLUMN_COUNT} expected",
                        )

    if len(filters) != 1:
        result.error(
            "FILTER_COUNT",
            f"exactly one effective filter expected; {len(filters)} found",
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
            f"filter from {source} on {canonical}; "
            f"{EXPECTED_FILTER_RANGE} expected",
        )
    else:
        result.check(f"Exact filter: {EXPECTED_FILTER_RANGE} ({source})")


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
                f"dataValidations count={declared}; {len(items)} rules",
            )
        validations.extend(items)
    if len(validations) != 1:
        result.error(
            "VALIDATION_COUNT",
            f"one list validation expected; {len(validations)} found",
        )
        return None

    validation = validations[0]
    if validation.get("type") != "list":
        result.error(
            "VALIDATION_TYPE",
            f"type={validation.get('type')!r}; 'list' expected",
        )
    try:
        references = _canonical_sqref(validation.get("sqref", ""))
    except WorkbookVerificationError as exc:
        result.error("VALIDATION_RANGE_INVALID", str(exc))
        references = []
    if references != [EXPECTED_VALIDATION_RANGE]:
        result.error(
            "VALIDATION_RANGE",
            f"ranges {references!r}; "
            f"[{EXPECTED_VALIDATION_RANGE!r}] expected",
        )
    allow_blank = validation.get("allowBlank", "0").lower() in {"1", "true"}
    if not allow_blank:
        result.error(
            "VALIDATION_ALLOW_BLANK",
            "allowBlank=1 expected because column O is initially empty",
        )
    hides_arrow = validation.get("showDropDown", "0").lower() in {"1", "true"}
    if hides_arrow:
        result.error(
            "VALIDATION_DROPDOWN",
            "showDropDown=1 hides the list arrow in Excel",
        )
    formula = validation.findtext("m:formula1", default="", namespaces=NS).strip()
    if not formula:
        result.error(
            "VALIDATION_FORMULA",
            "formula1 is empty; no verdicts would be offered",
        )
        return None
    options = _parse_inline_list(formula)
    if options is not None:
        if len(set(options)) < 2:
            result.error(
                "VALIDATION_OPTIONS",
                f"at least two distinct verdicts expected; received={options!r}",
            )
        elif references == [EXPECTED_VALIDATION_RANGE]:
            result.check(
                f"Exact list validation: {EXPECTED_VALIDATION_RANGE}, "
                f"{len(options)} verdicts"
            )
    elif references == [EXPECTED_VALIDATION_RANGE]:
        result.check(
            f"Exact list validation: {EXPECTED_VALIDATION_RANGE} "
            "(formula/range source)"
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
            result.error("CONDITIONAL_DXF", f"invalid dxfId: {dxf_id!r}")
        else:
            if index < 0 or index >= len(dxfs):
                result.error(
                    "CONDITIONAL_DXF",
                    f"dxfId={index} out of bounds (0..{len(dxfs) - 1})",
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
                f"ranges {references!r}; only "
                f"{EXPECTED_CONFIDENCE_RANGE} and "
                f"{EXPECTED_VERDICT_RANGE} are expected",
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
                    f"invalid priority {raw_priority!r} on {references[0]}",
                )
            else:
                if priority < 1:
                    result.error(
                        "CONDITIONAL_PRIORITY",
                        f"invalid priority {priority} on {references[0]}",
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
            "duplicate priorities: "
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
                f"{reference}: {len(useful)} conditional rules "
                "with useful styling; at least 2 expected",
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
                    f"{reference}: rules only distinguish "
                    f"{sorted(covered)!r}; at least two states from "
                    f"{expected_values!r} are expected",
                )
                continue
        result.check(
            f"Useful conditional formatting: {reference} "
            f"({len(useful)} styled rules)"
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
            result.error("ROW_REFERENCE", f"invalid row number: {raw_row!r}")
            continue
        if row_number in rows_seen:
            result.error("ROW_DUPLICATE", f"duplicate row {row_number}")
        rows_seen.add(row_number)
        if row_number < 1 or row_number > EXPECTED_ROW_COUNT:
            result.error(
                "ROW_OUTSIDE_GRID",
                f"physical row {row_number} outside 1:{EXPECTED_ROW_COUNT}",
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
                    f'{canonical} declared in XML row {row_number}'
                )
            key = (cell_row, cell_column)
            if key in values:
                result.error("CELL_DUPLICATE", f"duplicate cell {canonical}")
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
            f"{len(formula_cells)} cells with formulas: {preview}{suffix}",
        )
    if error_cells:
        preview = ", ".join(
            f"{reference}={value!r}" for reference, value in error_cells[:12]
        )
        suffix = "…" if len(error_cells) > 12 else ""
        result.error(
            "EXCEL_ERROR",
            f"{len(error_cells)} Excel errors: {preview}{suffix}",
        )
    if outside_cells:
        preview = ", ".join(outside_cells[:12])
        suffix = "…" if len(outside_cells) > 12 else ""
        result.error(
            "CELL_OUTSIDE_GRID",
            f"{len(outside_cells)} cells outside "
            f"{EXPECTED_GRID_RANGE} : {preview}{suffix}",
        )

    mismatches: list[str] = []
    mismatch_count = 0
    invalid_verdicts: list[str] = []
    for row_index, expected_row in enumerate(csv_rows, start=1):
        expected_id = expected_row[0] if row_index > 1 else "header"
        stable_key = expected_row[1] if row_index > 1 else "header"
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
                        f"O{row_index} (ID={expected_id}, key={stable_key})="
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
                f'{reference} (ID={expected_id}, key={stable_key}): expected {_short(expected)}, received {_short(actual)}'
            )
    if mismatch_count:
        suffix = ""
        if mismatch_count > len(mismatches):
            suffix = (
                f"; {mismatch_count - len(mismatches)} additional "
                "mismatches not shown"
            )
        result.error(
            "VALUE_MISMATCH",
            f"{mismatch_count} differing values: "
            + " | ".join(mismatches)
            + suffix,
        )
    if invalid_verdicts:
        result.error(
            "FEEDBACK_VERDICT",
            "verdicts outside the list: " + " | ".join(invalid_verdicts[:20]),
        )
    else:
        if not mismatch_count:
            exact_count = EXPECTED_COLUMN_COUNT + (
                (EXPECTED_ROW_COUNT - 1) * 14
            )
            result.check(
                f"Exact source values: {exact_count} cells in A:N "
                "and headers compared against CSV; feedback in O:P can be preserved"
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
            f"cannot open {xlsx_path} as XLSX: {exc}"
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
                "duplicate ZIP parts: " + ", ".join(duplicates[:8])
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
                "unsafe ZIP paths: " + ", ".join(sorted(dangerous)[:8])
            )
        encrypted = [info.filename for info in infos if info.flag_bits & 0x1]
        if encrypted:
            raise WorkbookVerificationError(
                "encrypted ZIP parts cannot be verified: "
                + ", ".join(encrypted[:8])
            )
        try:
            bad_crc = archive.testzip()
        except (OSError, zipfile.BadZipFile) as exc:
            raise WorkbookVerificationError(f"CRC/ZIP error: {exc}") from exc
        if bad_crc is not None:
            raise WorkbookVerificationError(f"invalid ZIP CRC: {bad_crc}")

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
                f"exactly one worksheet expected; {len(sheets)} found",
            )
        matching_sheets = [sheet for sheet in sheets if sheet.get("name") == sheet_name]
        if len(matching_sheets) != 1:
            names_found = [sheet.get("name", "") for sheet in sheets]
            result.error(
                "SHEET_NAME",
                f"worksheet {sheet_name!r} missing or duplicated; "
                f"worksheets={names_found!r}",
            )
            return
        sheet = matching_sheets[0]
        if sheet.get("state", "visible") != "visible":
            result.error("SHEET_HIDDEN", f"worksheet {sheet_name!r} is hidden")
        relationship_id = sheet.get(f"{{{REL_NS}}}id", "")
        relationship = workbook_relationships.get(relationship_id)
        if relationship is None:
            raise WorkbookVerificationError(
                f"unknown worksheet relationship: {relationship_id!r}"
            )
        relationship_type, worksheet_part = relationship
        if worksheet_part == "EXTERNAL" or not relationship_type.endswith("/worksheet"):
            raise WorkbookVerificationError(
                f"relation {relationship_id!r} is external or is not a worksheet relationship"
            )
        if worksheet_part not in names:
            raise WorkbookVerificationError(
                f"missing worksheet part: {worksheet_part}"
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
            result.check(f"Single visible worksheet: {sheet_name}")


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
        result.error("ARGUMENT", "max_value_errors must be greater than zero")
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
    status = "OK" if result.passed(strict=strict) else "FAILED"
    print(f'{status} — review workbook verification')
    print(f"XLSX : {xlsx_path}")
    print(f"CSV  : {csv_path}")
    for check in result.checks:
        print(f"  ✓ {check}")
    for warning in result.warnings:
        label = "ERROR (strict mode)" if strict else "WARNING"
        print(f"  ! {label} {warning}")
    for error in result.errors:
        print(f"  ✗ {error}")
    print(
        f'Summary: {len(result.errors)} error(s), {len(result.warnings)} warning(s)'
    )


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Verify the 1,055-dialogue review workbook against its canonical CSV.'
        )
    )
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--sheet-name", default=EXPECTED_SHEET_NAME)
    parser.add_argument(
        "--strict",
        action="store_true",
        help='treat recommendations (including frozen columns A:B) as errors',
    )
    parser.add_argument(
        "--max-value-errors",
        type=int,
        default=20,
        help="maximum number of detailed value mismatches (default: 20)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit a machine-readable JSON report for the build",
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
