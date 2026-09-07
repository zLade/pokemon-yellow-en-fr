#!/usr/bin/env python3
"""Tests for the narrow artifact_tool OpenXML metadata workaround."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from tools.repair_artifact_xlsx_metadata import (
    GRID_RANGE,
    MAIN_NS,
    WORKSHEET_PART,
    repair_xlsx,
    repaired_worksheet_xml,
)


def tag(name: str) -> str:
    return f"{{{MAIN_NS}}}{name}"


class ArtifactMetadataRepairTests(unittest.TestCase):
    def minimal_worksheet(self) -> bytes:
        return (
            '<?xml version="1.0" encoding="utf-8"?>'
            f'<x:worksheet xmlns:x="{MAIN_NS}">'
            '<x:sheetFormatPr defaultRowHeight="15"/>'
            '<x:sheetData><x:row r="1"><x:c r="A1"/></x:row></x:sheetData>'
            '</x:worksheet>'
        ).encode("utf-8")

    def test_adds_exact_dimension_and_two_axis_freeze(self) -> None:
        root = ET.fromstring(repaired_worksheet_xml(self.minimal_worksheet()))
        children = list(root)
        self.assertEqual(children[0].tag, tag("dimension"))
        self.assertEqual(children[0].get("ref"), GRID_RANGE)
        self.assertEqual(children[1].tag, tag("sheetViews"))
        pane = root.find("./x:sheetViews/x:sheetView/x:pane", {"x": MAIN_NS})
        self.assertIsNotNone(pane)
        self.assertEqual(pane.get("xSplit"), "2")
        self.assertEqual(pane.get("ySplit"), "1")
        self.assertEqual(pane.get("topLeftCell"), "C2")
        self.assertEqual(pane.get("state"), "frozen")

    def test_refuses_to_overwrite_future_native_export_metadata(self) -> None:
        for node in (
            f'<x:dimension ref="{GRID_RANGE}"/>',
            '<x:sheetViews><x:sheetView workbookViewId="0">'
            '<x:pane ySplit="1" state="frozen"/>'
            '</x:sheetView></x:sheetViews>',
        ):
            payload = self.minimal_worksheet().replace(
                b"<x:sheetFormatPr",
                node.encode("utf-8") + b"<x:sheetFormatPr",
            )
            with self.subTest(node=node):
                with self.assertRaisesRegex(ValueError, "reassessed"):
                    repaired_worksheet_xml(payload)

    def test_populates_empty_sheet_views_emitted_by_artifact_tool(self) -> None:
        for source in (
            b"<x:sheetViews/>",
            (
                b'<x:sheetViews><x:sheetView showGridLines="0" '
                b'workbookViewId="0"/></x:sheetViews>'
            ),
        ):
            with self.subTest(source=source):
                payload = self.minimal_worksheet().replace(
                    b"<x:sheetFormatPr",
                    source + b"<x:sheetFormatPr",
                )
                root = ET.fromstring(repaired_worksheet_xml(payload))
                views = root.findall(tag("sheetViews"))
                self.assertEqual(len(views), 1)
                self.assertIsNotNone(
                    views[0].find(
                        "./x:sheetView/x:pane",
                        {"x": MAIN_NS},
                    )
                )

    def test_zip_pass_preserves_other_parts_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "source.xlsx"
            target = directory / "target.xlsx"
            sentinel = b"styles-sentinel"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(WORKSHEET_PART, self.minimal_worksheet())
                archive.writestr("xl/styles.xml", sentinel)

            repair_xlsx(source, target)

            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.read("xl/styles.xml"), sentinel)
                root = ET.fromstring(archive.read(WORKSHEET_PART))
                self.assertEqual(
                    root.find(tag("dimension")).get("ref"),
                    GRID_RANGE,
                )


if __name__ == "__main__":
    unittest.main()
