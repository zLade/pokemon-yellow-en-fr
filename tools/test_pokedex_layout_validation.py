#!/usr/bin/env python3
"""Regressions for the complete 151-entry Pokédex layout migration."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rom_traduction_assistant import parse_patch_entries
from tools.dialogue_inventory import (
    INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT,
    load_pokedex_inventory,
)
from tools.dialogue_layout import (
    POKEDEX_LAYOUT,
    POKEDEX_LINE_WIDTH,
    POKEDEX_MAX_LINES,
    wrap_pokedex_lines,
)
from tools.french_font import encode_game_text
from tools.pokedex_description_table import (
    POKEDEX_ACCESSIBLE_ANCHORS,
    POKEDEX_ACCESSIBLE_COUNT,
    POKEDEX_ACCESSIBLE_OFFSET_FINGERPRINT,
    POKEDEX_DESCRIPTION_TABLE_OFFSET,
    POKEDEX_EXTENDED_OFFSET_FINGERPRINT,
    POKEDEX_EXTENDED_POINTER_COUNT,
    load_pokedex_description_table,
    offset_fingerprint,
)
from tools.validate_pokedex_layout import validate


EXPECTED_EXTENDED_LAYOUT_OFFSETS = {
    0x032F2A,
    0x032F5E,
    0x032F9B,
    0x032FD0,
    0x0378C9,
    0x0378F6,
    0x03792A,
    0x03795F,
}
class PokedexLayoutValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.accessible, cls.extended = (
            load_pokedex_description_table()
        )

    def _fixture_script(
        self,
        *,
        missing_layout_ids: set[int] | None = None,
    ) -> Path:
        missing_layout_ids = missing_layout_ids or set()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "pokedex_layout_fixture.py"
        lines: list[str] = []
        for record in self.accessible:
            layout = (
                ""
                if record.table_index in missing_layout_ids
                else f', layout="{POKEDEX_LAYOUT}"'
            )
            lines.append(
                f'p(0x{record.description_offset:06X}, "Texte"{layout})'
            )
        for record in self.extended:
            layout = (
                f', layout="{POKEDEX_LAYOUT}"'
                if record.description_offset
                in EXPECTED_EXTENDED_LAYOUT_OFFSETS
                else ""
            )
            lines.append(
                f'p(0x{record.description_offset:06X}, "Texte"{layout})'
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def test_pointer_map_has_exact_151_accessible_offsets(self) -> None:
        self.assertEqual(
            len(self.accessible),
            POKEDEX_ACCESSIBLE_COUNT,
        )
        self.assertEqual(
            [record.table_index for record in self.accessible],
            list(range(1, POKEDEX_ACCESSIBLE_COUNT + 1)),
        )
        self.assertTrue(all(record.accessible for record in self.accessible))
        self.assertEqual(
            len(
                {
                    record.description_offset
                    for record in self.accessible
                }
            ),
            POKEDEX_ACCESSIBLE_COUNT,
        )
        self.assertEqual(
            offset_fingerprint(self.accessible),
            POKEDEX_ACCESSIBLE_OFFSET_FINGERPRINT,
        )
        self.assertEqual(
            self.accessible[0].pointer_file_offset,
            POKEDEX_DESCRIPTION_TABLE_OFFSET,
        )
        self.assertEqual(
            self.accessible[-1].pointer_file_offset,
            POKEDEX_DESCRIPTION_TABLE_OFFSET
            + 2 * (POKEDEX_ACCESSIBLE_COUNT - 1),
        )

    def test_required_species_anchors_match_table_0x03201e(self) -> None:
        expected = {
            1: 0x030898,
            2: 0x036950,
            3: 0x036978,
            4: 0x03217A,
            151: 0x03789A,
        }
        self.assertEqual(POKEDEX_ACCESSIBLE_ANCHORS, expected)
        for species_id, description_offset in expected.items():
            with self.subTest(species_id=species_id):
                self.assertEqual(
                    self.accessible[
                        species_id - 1
                    ].description_offset,
                    description_offset,
                )

    def test_eight_extended_pointers_are_separate(self) -> None:
        self.assertEqual(
            len(self.extended),
            POKEDEX_EXTENDED_POINTER_COUNT,
        )
        self.assertEqual(
            [record.table_index for record in self.extended],
            list(range(152, 160)),
        )
        self.assertTrue(
            all(not record.accessible for record in self.extended)
        )
        self.assertEqual(
            offset_fingerprint(self.extended),
            POKEDEX_EXTENDED_OFFSET_FINGERPRINT,
        )
        accessible_offsets = {
            record.description_offset for record in self.accessible
        }
        extended_offsets = {
            record.description_offset for record in self.extended
        }
        self.assertTrue(accessible_offsets.isdisjoint(extended_offsets))

    def test_validator_never_false_passes_an_incomplete_script(self) -> None:
        report, errors = validate()
        accessible_layouts = int(report["accessible_layout_rows"])
        missing_layouts = int(
            report["accessible_missing_layout_rows"]
        )
        self.assertEqual(
            missing_layouts,
            POKEDEX_ACCESSIBLE_COUNT - accessible_layouts,
        )
        if missing_layouts:
            self.assertEqual(report["result"], "FAIL")
            self.assertTrue(errors)
            self.assertEqual(
                len(report["accessible_missing_layout_offsets"]),
                missing_layouts,
            )
        else:
            self.assertEqual(errors, [])
            self.assertEqual(report["result"], "PASS")

    def test_complete_151_layout_fixture_passes_final_contract(self) -> None:
        report, errors = validate(self._fixture_script())
        self.assertEqual(errors, [])
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(
            report["accessible_layout_rows"],
            POKEDEX_ACCESSIBLE_COUNT,
        )
        self.assertEqual(report["accessible_missing_layout_rows"], 0)
        self.assertEqual(report["extended_layout_rows"], 8)
        self.assertEqual(report["word_split_boundaries"], 0)

    def test_one_missing_accessible_layout_is_a_hard_failure(self) -> None:
        report, errors = validate(
            self._fixture_script(missing_layout_ids={1})
        )
        self.assertEqual(report["result"], "FAIL")
        self.assertEqual(report["accessible_layout_rows"], 150)
        self.assertEqual(report["accessible_missing_layout_rows"], 1)
        self.assertEqual(
            report["accessible_missing_layout_offsets"],
            ["0x030898"],
        )
        self.assertEqual(len(errors), 1)
        self.assertIn("Pokédex #1", errors[0])

    def test_final_script_requires_all_151_accessible_layouts(self) -> None:
        report, errors = validate()
        self.assertEqual(errors, [])
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(
            report["accessible_layout_rows"],
            POKEDEX_ACCESSIBLE_COUNT,
        )
        self.assertEqual(report["accessible_missing_layout_rows"], 0)
        self.assertEqual(report["word_split_boundaries"], 0)

    def test_eight_extended_layouts_are_validated_separately(
        self,
    ) -> None:
        report, _ = validate()
        self.assertEqual(
            report["extended_pointer_rows"],
            POKEDEX_EXTENDED_POINTER_COUNT,
        )
        self.assertEqual(report["extended_layout_rows"], 8)
        self.assertEqual(
            {
                int(offset, 16)
                for offset in report["extended_layout_offsets"]
            },
            EXPECTED_EXTENDED_LAYOUT_OFFSETS,
        )

    def test_declared_table_descriptions_do_not_split_words(self) -> None:
        accessible_offsets = {
            record.description_offset for record in self.accessible
        }
        extended_offsets = {
            record.description_offset for record in self.extended
        }
        allowed_offsets = accessible_offsets | extended_offsets
        layout_entries = [
            entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
            if entry.layout == POKEDEX_LAYOUT
        ]
        self.assertTrue(layout_entries)
        self.assertTrue(
            {entry.offset for entry in layout_entries}
            <= allowed_offsets
        )
        for entry in layout_entries:
            with self.subTest(offset=f"0x{entry.offset:06X}"):
                lines = wrap_pokedex_lines(entry.text)
                self.assertGreaterEqual(len(lines), 1)
                self.assertLessEqual(len(lines), POKEDEX_MAX_LINES)
                self.assertTrue(
                    all(
                        len(line) == POKEDEX_LINE_WIDTH
                        for line in lines[:-1]
                    )
                )
                self.assertLessEqual(
                    len(lines[-1]),
                    POKEDEX_LINE_WIDTH,
                )
                self.assertEqual(
                    b" ".join(line.rstrip(b" ") for line in lines),
                    encode_game_text(entry.text),
                )

    def test_inventory_repairs_remain_a_checked_subset(self) -> None:
        repairs = 0
        entries = {
            entry.offset: entry
            for entry in parse_patch_entries(
                apply_dialogue_inventory=False,
            )
        }
        for offset, record in load_pokedex_inventory().items():
            self.assertIn(offset, entries)
            for repair in record["artificial_hyphenations"]:
                with self.subTest(
                    offset=f"0x{offset:06X}",
                    source_form=repair["source_form"],
                ):
                    self.assertNotIn(
                        repair["source_form"],
                        entries[offset].text,
                    )
                repairs += 1
        self.assertEqual(
            repairs,
            INVENTORY_POKEDEX_ARTIFICIAL_HYPHENATION_COUNT,
        )


if __name__ == "__main__":
    unittest.main()
