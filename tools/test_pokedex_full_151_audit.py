from __future__ import annotations

import unittest

from tools.audit_pokedex_full_151 import (
    DEFAULT_CSV,
    DEFAULT_ROM,
    DEFAULT_SCRIPT,
    KANTO_COUNT,
    NAME_ANCHORS,
    POINTER_ANCHORS,
    PROPOSALS,
    SPECIES,
    _description_offsets,
    _name_records,
    build_report,
)
from tools.dialogue_layout import wrap_pokedex_lines


class PokedexFull151AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom = DEFAULT_ROM.read_bytes()

    def test_description_table_start_and_index_anchors(self) -> None:
        offsets = _description_offsets(self.rom, KANTO_COUNT)
        self.assertEqual(len(offsets), 151)
        for species_id, expected_offset in POINTER_ANCHORS.items():
            self.assertEqual(offsets[species_id - 1], expected_offset)

    def test_national_name_table_anchors_match_same_indices(self) -> None:
        names = _name_records(self.rom, KANTO_COUNT)
        self.assertEqual(len(names), 151)
        for species_id, (expected_name, expected_offset) in NAME_ANCHORS.items():
            self.assertEqual(
                names[species_id - 1],
                (expected_offset, expected_name),
            )

    def test_all_source_faithful_proposals_fit_13x4(self) -> None:
        self.assertEqual(len(SPECIES), 151)
        self.assertEqual(len(PROPOSALS), 151)
        for species_id, proposal in enumerate(PROPOSALS, 1):
            with self.subTest(species_id=species_id, species=SPECIES[species_id - 1]):
                lines = wrap_pokedex_lines(proposal)
                self.assertLessEqual(len(lines), 4)
                self.assertTrue(all(len(line) == 13 for line in lines[:-1]))
                self.assertLessEqual(len(lines[-1]), 13)

    def test_current_kanto_set_is_fully_migrated(self) -> None:
        report = build_report(DEFAULT_ROM, DEFAULT_SCRIPT, DEFAULT_CSV)
        self.assertEqual(report["result"], "PASS")
        summary = report["summary"]
        self.assertEqual(summary["accessible_already_pokedex_13x4"], 151)
        self.assertEqual(summary["remaining_layout_migrations"], 0)
        self.assertEqual(summary["remaining_content_corrections"], 0)
        self.assertEqual(summary["status_counts"]["complete"], 151)
        self.assertEqual(summary["status_counts"]["incomplete"], 0)


if __name__ == "__main__":
    unittest.main()
