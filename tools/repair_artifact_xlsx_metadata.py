#!/usr/bin/env python3
"""Restore worksheet metadata omitted by artifact_tool 2.8.6 export.

All cells, styles, validation, conditional formatting and the native table are
authored by ``build_dialogue_review_xlsx.mjs`` through artifact_tool.  Version
2.8.6 currently serializes neither ``dimension`` nor ``sheetViews`` even when
``freezePanes`` is set.  This narrow OpenXML post-pass restores only those two
standard worksheet metadata nodes and rejects any unexpected existing state.
"""

from __future__ import annotations

import argparse
import os
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
GRID_RANGE = "A1:P1056"
WORKSHEET_PART = "xl/worksheets/sheet1.xml"


def _tag(name: str) -> str:
    return f"{{{MAIN_NS}}}{name}"


def repaired_worksheet_xml(payload: bytes) -> bytes:
    root = ET.fromstring(payload)
    if root.tag != _tag("worksheet"):
        raise ValueError("la partie ciblée n'est pas une feuille OpenXML")
    dimensions = root.findall(_tag("dimension"))
    sheet_views = root.findall(_tag("sheetViews"))
    if dimensions or len(sheet_views) > 1:
        raise ValueError(
            "artifact_tool a déjà sérialisé dimension/sheetViews; "
            "le contournement doit être réévalué"
        )
    dimension = ET.Element(_tag("dimension"), {"ref": GRID_RANGE})
    views = sheet_views[0] if sheet_views else ET.Element(_tag("sheetViews"))
    existing_views = list(views)
    if existing_views:
        if (
            len(existing_views) != 1
            or existing_views[0].tag != _tag("sheetView")
            or list(existing_views[0])
        ):
            raise ValueError(
                "artifact_tool a déjà sérialisé des vues de feuille; "
                "le contournement doit être réévalué"
            )
        view = existing_views[0]
        view.set("workbookViewId", view.get("workbookViewId", "0"))
    else:
        view = ET.SubElement(
            views,
            _tag("sheetView"),
            {"workbookViewId": "0"},
        )
    ET.SubElement(
        view,
        _tag("pane"),
        {
            "xSplit": "2",
            "ySplit": "1",
            "topLeftCell": "C2",
            "activePane": "bottomRight",
            "state": "frozen",
        },
    )
    for pane, cell in (
        ("topRight", "C1"),
        ("bottomLeft", "A2"),
        ("bottomRight", "C2"),
    ):
        ET.SubElement(
            view,
            _tag("selection"),
            {"pane": pane, "activeCell": cell, "sqref": cell},
        )

    root.insert(0, dimension)
    if not sheet_views:
        root.insert(1, views)
    ET.register_namespace("x", MAIN_NS)
    return ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )


def repair_xlsx(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temporary_handle, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    os.close(temporary_handle)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(source, "r") as reader:
            names = reader.namelist()
            if names.count(WORKSHEET_PART) != 1:
                raise ValueError(
                    f"{WORKSHEET_PART}: une partie attendue, "
                    f"{names.count(WORKSHEET_PART)} trouvée(s)"
                )
            with zipfile.ZipFile(temporary, "w") as writer:
                for info in reader.infolist():
                    payload = reader.read(info.filename)
                    if info.filename == WORKSHEET_PART:
                        payload = repaired_worksheet_xml(payload)
                    writer.writestr(info, payload)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restaure dimension et volets figés de l'XLSX artifact_tool."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repair_xlsx(args.input, args.output)
    print(f"XLSX metadata PASS: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
