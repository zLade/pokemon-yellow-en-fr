#!/usr/bin/env python3
"""Synthetic OpenXML tests for the dialogue-review XLSX verifier."""

from __future__ import annotations

import csv
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from tools.verify_dialogue_review_xlsx import (
    EXPECTED_COLUMN_COUNT,
    EXPECTED_HEADERS,
    EXPECTED_ROW_COUNT,
    verify_dialogue_review_xlsx,
)


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)


def column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(ord("A") + remainder) + result
    return result


def synthetic_rows() -> list[list[str]]:
    rows = [list(EXPECTED_HEADERS)]
    confidence_values = ("high", "medium", "low", "direct source")
    for index in range(1, EXPECTED_ROW_COUNT):
        text = f"Dialogue français {index}"
        if index == 1:
            text = "Ligne 1\nLigne 2 — Pokémon"
        rows.append(
            [
                f"D{index:04d}",
                f"MAIN:0x{index:06X}",
                "In-game dialogue",
                f"0x{index:06X}",
                str(index),
                "dialogue_19",
                "NPC",
                text,
                f"中文对白{index}",
                f"English dialogue {index}",
                confidence_values[(index - 1) % len(confidence_values)],
                "translated from Chinese",
                "yes",
                "yes",
                "",
                "",
            ]
        )
    return rows


def write_csv(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        csv.writer(handle).writerows(rows)


def inline_cell(reference: str, value: str) -> str:
    preserve = ' xml:space="preserve"' if value != value.strip() else ""
    return (
        f'<c r="{reference}" t="inlineStr"><is><t{preserve}>'
        f"{escape(value)}</t></is></c>"
    )


def differential_styles_xml() -> str:
    colors = (
        "FFC6EFCE",
        "FFFFEB9C",
        "FFFFC7CE",
        "FFDDEBF7",
        "FFC6EFCE",
        "FFFFC7CE",
    )
    dxfs = "".join(
        "<dxf><fill><patternFill patternType=\"solid\">"
        f'<fgColor rgb="{color}"/>'
        "</patternFill></fill></dxf>"
        for color in colors
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<styleSheet xmlns="{MAIN_NS}">'
        '<fonts count="1"><font/></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill></fills>'
        '<borders count="1"><border/></borders>'
        '<cellStyleXfs count="1"><xf/></cellStyleXfs>'
        '<cellXfs count="1"><xf/></cellXfs>'
        f'<dxfs count="{len(colors)}">{dxfs}</dxfs>'
        "</styleSheet>"
    )


def conditional_block(
    reference: str,
    statuses: tuple[str, ...],
    *,
    first_priority: int,
    useful: bool = True,
) -> str:
    rules: list[str] = []
    for index, status in enumerate(statuses):
        dxf = f' dxfId="{first_priority + index - 1}"' if useful else ""
        formula = escape(
            f'NOT(ISERROR(SEARCH("{status}",'
            f'{reference.split(":", 1)[0]})))'
        )
        rules.append(
            f'<cfRule type="containsText"{dxf} '
            f'priority="{first_priority + index}" '
            f'operator="containsText" text="{escape(status)}">'
            f"<formula>{formula}</formula></cfRule>"
        )
    return (
        f'<conditionalFormatting sqref="{reference}">'
        f'{"".join(rules)}</conditionalFormatting>'
    )


def worksheet_xml(
    rows: list[list[str]],
    *,
    value_overrides: dict[str, str] | None = None,
    special_cells: dict[str, tuple[str, str]] | None = None,
    extra_cells: dict[str, str] | None = None,
    dimension_ref: str = "A1:P1056",
    filter_ref: str = "A1:P1056",
    table_filter: bool = False,
    pane_y: int = 1,
    pane_x: int = 2,
    validation_type: str = "list",
    validation_ref: str = "O2:O1056",
    validation_formula: str = '"Approved,Needs review,Needs rewriting"',
    include_confidence_cf: bool = True,
    include_verdict_cf: bool = True,
    useful_cf: bool = True,
) -> str:
    value_overrides = value_overrides or {}
    special_cells = special_cells or {}
    extra_cells = extra_cells or {}
    row_xml: list[str] = []
    for row_number, values in enumerate(rows, start=1):
        cells: list[str] = []
        for column_number, original_value in enumerate(values, start=1):
            reference = f"{column_name(column_number)}{row_number}"
            value = value_overrides.get(reference, original_value)
            if reference == "A1":
                cells.append('<c r="A1" t="s"><v>0</v></c>')
            elif reference in special_cells:
                cell_type, raw = special_cells[reference]
                if cell_type == "formula":
                    cells.append(
                        f'<c r="{reference}"><f>1+1</f><v>{escape(raw)}</v></c>'
                    )
                elif cell_type == "error":
                    cells.append(
                        f'<c r="{reference}" t="e"><v>{escape(raw)}</v></c>'
                    )
                else:
                    raise AssertionError(f"unknown special cell type: {cell_type}")
            else:
                cells.append(inline_cell(reference, value))
        if row_number == 1:
            for reference, value in extra_cells.items():
                cells.append(inline_cell(reference, value))
        row_xml.append(f'<row r="{row_number}">{"".join(cells)}</row>')

    x_split = f' xSplit="{pane_x}"' if pane_x else ""
    top_left = "C2" if pane_x == 2 else "A2"
    filter_xml = "" if table_filter else f'<autoFilter ref="{filter_ref}"/>'
    confidence_xml = (
        conditional_block(
            "K2:K1056",
            ("high", "medium", "low"),
            first_priority=1,
            useful=useful_cf,
        )
        if include_confidence_cf
        else ""
    )
    verdict_xml = (
        conditional_block(
            "O2:O1056",
            ("Approved", "Needs review", "Needs rewriting"),
            first_priority=4,
            useful=useful_cf,
        )
        if include_verdict_cf
        else ""
    )
    table_parts = (
        '<tableParts count="1"><tablePart r:id="rIdTable1"/></tableParts>'
        if table_filter
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        f'<dimension ref="{dimension_ref}"/>'
        '<sheetViews><sheetView workbookViewId="0">'
        f'<pane{x_split} ySplit="{pane_y}" topLeftCell="{top_left}" '
        'activePane="bottomRight" state="frozen"/>'
        "</sheetView></sheetViews>"
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        f"{filter_xml}{confidence_xml}{verdict_xml}"
        '<dataValidations count="1"><dataValidation '
        f'type="{validation_type}" allowBlank="1" sqref="{validation_ref}">'
        f"<formula1>{escape(validation_formula)}</formula1>"
        "</dataValidation></dataValidations>"
        f"{table_parts}</worksheet>"
    )


def write_xlsx(
    path: Path,
    rows: list[list[str]],
    **worksheet_options: object,
) -> None:
    table_formula = bool(worksheet_options.pop("table_formula", False))
    table_filter = bool(worksheet_options.get("table_filter", False))
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Default Extension="xml" '
            'ContentType="application/xml"/></Types>'
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
            '<sheets><sheet name="Dialogues" sheetId="1" '
            'r:id="rIdSheet1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships">'
            '<Relationship Id="rIdSheet1" Type="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '<Relationship Id="rIdStrings" Type="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships/sharedStrings" '
            'Target="sharedStrings.xml"/>'
            "</Relationships>"
        ),
        "xl/sharedStrings.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<sst xmlns="{MAIN_NS}" count="1" uniqueCount="1">'
            "<si><t>id</t></si></sst>"
        ),
        "xl/styles.xml": differential_styles_xml(),
        "xl/worksheets/sheet1.xml": worksheet_xml(rows, **worksheet_options),
    }
    if table_filter:
        parts["xl/worksheets/_rels/sheet1.xml.rels"] = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/'
            '2006/relationships"><Relationship Id="rIdTable1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
            'relationships/table" Target="../tables/table1.xml"/>'
            "</Relationships>"
        )
        table_columns_parts: list[str] = []
        for index, header in enumerate(EXPECTED_HEADERS, start=1):
            if table_formula and index == 8:
                table_columns_parts.append(
                    f'<tableColumn id="{index}" name="{escape(header)}">'
                    "<calculatedColumnFormula>1+1</calculatedColumnFormula>"
                    "</tableColumn>"
                )
            else:
                table_columns_parts.append(
                    f'<tableColumn id="{index}" name="{escape(header)}"/>'
                )
        table_columns = "".join(table_columns_parts)
        parts["xl/tables/table1.xml"] = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<table xmlns="{MAIN_NS}" id="1" name="DialoguesTable" '
            'displayName="DialoguesTable" ref="A1:P1056">'
            '<autoFilter ref="A1:P1056"/>'
            f'<tableColumns count="16">{table_columns}</tableColumns>'
            "</table>"
        )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload.encode("utf-8"))


class VerifyDialogueReviewXlsxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = synthetic_rows()
        if len(cls.rows) != EXPECTED_ROW_COUNT:
            raise AssertionError("synthetic fixture has the wrong row count")
        if not all(len(row) == EXPECTED_COLUMN_COUNT for row in cls.rows):
            raise AssertionError("synthetic fixture is not rectangular")

    def verify_fixture(
        self,
        *,
        csv_rows: list[list[str]] | None = None,
        **worksheet_options: object,
    ):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        csv_path = directory / "dialogues.csv"
        xlsx_path = directory / "dialogues.xlsx"
        rows = csv_rows if csv_rows is not None else self.rows
        write_csv(csv_path, rows)
        write_xlsx(xlsx_path, self.rows, **worksheet_options)
        return verify_dialogue_review_xlsx(xlsx_path, csv_path)

    def test_valid_workbook_passes_all_mandatory_checks(self) -> None:
        result = self.verify_fixture()
        self.assertTrue(result.passed(), result.errors)
        self.assertTrue(result.passed(strict=True), result.warnings)
        self.assertFalse(result.errors)
        self.assertFalse(result.warnings)
        self.assertTrue(any("14786 cells" in check for check in result.checks))

    def test_reviewer_feedback_is_preserved_but_verdict_stays_valid(self) -> None:
        result = self.verify_fixture(
            value_overrides={
                "O2": "Approved",
                "P2": "The tone of this line is perfect.",
            }
        )
        self.assertTrue(result.passed(strict=True), result.errors)

        invalid = self.verify_fixture(value_overrides={"O2": "Unknown"})
        self.assertTrue(
            any("[FEEDBACK_VERDICT]" in error for error in invalid.errors),
            invalid.errors,
        )

    def test_table_autofilter_is_accepted_as_the_single_effective_filter(self) -> None:
        result = self.verify_fixture(table_filter=True)
        self.assertTrue(result.passed(strict=True), result.errors + result.warnings)
        self.assertTrue(any("table xl/tables/table1.xml" in check for check in result.checks))

    def test_value_mismatch_names_cell_id_and_stable_key(self) -> None:
        result = self.verify_fixture(value_overrides={"H13": "texte altéré"})
        report = "\n".join(result.errors)
        self.assertIn("[VALUE_MISMATCH]", report)
        self.assertIn("H13", report)
        self.assertIn("ID=D0012", report)
        self.assertIn("key=MAIN:0x00000C", report)
        self.assertIn("texte altéré", report)

    def test_csv_rejects_nonsequential_ids_and_duplicate_stable_keys(self) -> None:
        rows = [row[:] for row in self.rows]
        rows[2][0] = "D9999"
        rows[2][1] = rows[1][1]
        result = self.verify_fixture(csv_rows=rows)
        report = "\n".join(result.errors)
        self.assertIn("[CSV_ID_SEQUENCE]", report)
        self.assertIn("[CSV_STABLE_KEY_DUPLICATE]", report)

    def test_wrong_dimension_and_filter_ranges_are_reported_exactly(self) -> None:
        result = self.verify_fixture(
            dimension_ref="A1:Q1056",
            filter_ref="A1:P1055",
        )
        report = "\n".join(result.errors)
        self.assertIn("[DIMENSION_RANGE]", report)
        self.assertIn("A1:Q1056", report)
        self.assertIn("[FILTER_RANGE]", report)
        self.assertIn("A1:P1055", report)

    def test_freeze_row_is_mandatory_and_columns_are_strict_recommendation(self) -> None:
        wrong_row = self.verify_fixture(pane_y=2)
        self.assertTrue(any("[FREEZE_ROW]" in error for error in wrong_row.errors))

        row_only = self.verify_fixture(pane_x=0)
        self.assertFalse(row_only.errors)
        self.assertTrue(
            any(
                "[FREEZE_COLUMNS_RECOMMENDED]" in warning
                for warning in row_only.warnings
            )
        )
        self.assertTrue(row_only.passed())
        self.assertFalse(row_only.passed(strict=True))

    def test_validation_must_be_a_list_on_the_exact_verdict_range(self) -> None:
        result = self.verify_fixture(
            validation_type="custom",
            validation_ref="O2:O1055",
            validation_formula='"Only"',
        )
        report = "\n".join(result.errors)
        self.assertIn("[VALIDATION_TYPE]", report)
        self.assertIn("[VALIDATION_RANGE]", report)
        self.assertIn("[VALIDATION_OPTIONS]", report)

    def test_both_conditional_format_ranges_need_useful_styled_rules(self) -> None:
        missing = self.verify_fixture(include_verdict_cf=False)
        self.assertTrue(
            any(
                "[CONDITIONAL_USEFUL_RULES]" in error and "O2:O1056" in error
                for error in missing.errors
            )
        )

        unstyled = self.verify_fixture(useful_cf=False)
        report = "\n".join(unstyled.errors)
        self.assertIn("K2:K1056", report)
        self.assertIn("O2:O1056", report)

    def test_cell_formulas_and_excel_errors_are_rejected(self) -> None:
        result = self.verify_fixture(
            special_cells={
                "H7": ("formula", "2"),
                "I8": ("error", "#REF!"),
            }
        )
        report = "\n".join(result.errors)
        self.assertIn("[UNEXPECTED_FORMULA]", report)
        self.assertIn("H7", report)
        self.assertIn("[EXCEL_ERROR]", report)
        self.assertIn("I8", report)

    def test_calculated_table_columns_are_rejected(self) -> None:
        result = self.verify_fixture(table_filter=True, table_formula=True)
        report = "\n".join(result.errors)
        self.assertIn("[UNEXPECTED_TABLE_FORMULA]", report)
        self.assertIn("xl/tables/table1.xml", report)

    def test_any_physical_cell_outside_the_exact_grid_is_rejected(self) -> None:
        result = self.verify_fixture(extra_cells={"Q1": "outside grid"})
        report = "\n".join(result.errors)
        self.assertIn("[CELL_OUTSIDE_GRID]", report)
        self.assertIn("Q1", report)


if __name__ == "__main__":
    unittest.main()
