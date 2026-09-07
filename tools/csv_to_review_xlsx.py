#!/usr/bin/env python3
"""Convert the dialogue review CSV to a dependency-free XLSX workbook."""

from __future__ import annotations

import argparse
import csv
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape


ROM_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROM_DIR / "LISTE_EXHAUSTIVE_DIALOGUES.csv"
DEFAULT_XLSX = ROM_DIR / "build" / "LISTE_EXHAUSTIVE_DIALOGUES.xlsx"
SHEET_NAME = "Dialogues"


def column_name(index: int) -> str:
    value = index + 1
    result = ""
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def inline_string_cell(
    row_index: int,
    column_index: int,
    value: str,
    *,
    style: int = 0,
) -> str:
    reference = f"{column_name(column_index)}{row_index}"
    preserve = ' xml:space="preserve"' if value != value.strip() else ""
    style_attribute = f' s="{style}"' if style else ""
    return (
        f'<c r="{reference}" t="inlineStr"{style_attribute}>'
        f"<is><t{preserve}>{escape(value)}</t></is></c>"
    )


def worksheet_xml(rows: list[list[str]]) -> str:
    widths = (
        10, 24, 20, 20, 12, 22, 18, 70,
        70, 70, 18, 30, 12, 24, 18, 60,
    )
    columns = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths, start=1)
    )
    row_xml: list[str] = []
    for row_index, values in enumerate(rows, start=1):
        style = 1 if row_index == 1 else 0
        cells = "".join(
            inline_string_cell(
                row_index,
                column_index,
                value,
                style=style,
            )
            for column_index, value in enumerate(values)
        )
        height = ' ht="30" customHeight="1"' if row_index == 1 else ""
        row_xml.append(f'<row r="{row_index}"{height}>{cells}</row>')

    last_column = column_name(len(rows[0]) - 1)
    last_row = len(rows)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/'
        'spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0">'
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" '
        'state="frozen"/>'
        '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/>'
        '</sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        f"<cols>{columns}</cols>"
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        f'<autoFilter ref="A1:{last_column}{last_row}"/>'
        '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" '
        'header="0.3" footer="0.3"/>'
        "</worksheet>"
    )


def build_xlsx(csv_path: Path, xlsx_path: Path) -> tuple[int, int]:
    with csv_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = [list(row) for row in csv.reader(handle)]
    if not rows or not rows[0]:
        raise ValueError("Empty CSV")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("Non-rectangular CSV")

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00",
        "Z",
    )
    parts = {
        "[Content_Types].xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxml'
            'formats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="'
            'application/vnd.openxmlformats-officedocument.spreadsheetml.'
            'worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            '<Override PartName="/docProps/core.xml" ContentType="application/'
            'vnd.openxmlformats-package.core-properties+xml"/>'
            '<Override PartName="/docProps/app.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.extended-properties+xml"/>'
            "</Types>"
        ),
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" '
            'Target="xl/workbook.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
            'package/2006/relationships/metadata/core-properties" '
            'Target="docProps/core.xml"/>'
            '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/extended-properties" '
            'Target="docProps/app.xml"/>'
            "</Relationships>"
        ),
        "xl/workbook.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.'
            'org/officeDocument/2006/relationships">'
            '<bookViews><workbookView/></bookViews>'
            f'<sheets><sheet name="{SHEET_NAME}" sheetId="1" '
            'r:id="rId1"/></sheets>'
            '<calcPr calcId="191029"/></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>"
        ),
        "xl/worksheets/sheet1.xml": worksheet_xml(rows),
        "xl/styles.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/'
            'spreadsheetml/2006/main">'
            '<fonts count="2">'
            '<font><sz val="10"/><name val="Arial"/></font>'
            '<font><b/><sz val="10"/><name val="Arial"/></font>'
            '</fonts>'
            '<fills count="3">'
            '<fill><patternFill patternType="none"/></fill>'
            '<fill><patternFill patternType="gray125"/></fill>'
            '<fill><patternFill patternType="solid">'
            '<fgColor rgb="FFE8EAED"/><bgColor indexed="64"/>'
            '</patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/>'
            '<diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" '
            'fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="2">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" '
            'xfId="0"><alignment vertical="top" wrapText="1"/></xf>'
            '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" '
            'xfId="0" applyFont="1" applyFill="1" applyAlignment="1">'
            '<alignment vertical="center" wrapText="1"/></xf>'
            '</cellXfs>'
            '<cellStyles count="1"><cellStyle name="Normal" xfId="0" '
            'builtinId="0"/></cellStyles>'
            "</styleSheet>"
        ),
        "docProps/core.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
            'package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:dcterms="http://purl.org/dc/terms/" '
            'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
            '<dc:title>Pokémon Yellow NES — Dialogue review</dc:title>'
            '<dc:creator>Codex</dc:creator>'
            f'<dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>'
            "</cp:coreProperties>"
        ),
        "docProps/app.xml": (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Properties xmlns="http://schemas.openxmlformats.org/'
            'officeDocument/2006/extended-properties" '
            'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/'
            '2006/docPropsVTypes">'
            '<Application>Codex</Application>'
            "</Properties>"
        ),
    }
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        xlsx_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for name, content in parts.items():
            archive.writestr(name, content.encode("utf-8"))
    return len(rows), width


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, columns = build_xlsx(args.csv, args.xlsx)
    print(f"Workbook: {args.xlsx}")
    print(f"Dimensions : {rows} rows x {columns} columns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
