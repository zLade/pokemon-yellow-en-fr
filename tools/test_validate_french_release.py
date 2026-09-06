#!/usr/bin/env python3

from __future__ import annotations

import unittest
from pathlib import Path

from rom_traduction_assistant import parse_ips
from tools.title_screen_tools import (
    ENGLISH_CREDIT_NT_COLUMN,
    ENGLISH_CREDIT_NT_ROW,
    TITLE_NT_FILE,
    TITLE_PT1_FILE,
    title_credit_tiles,
)

from tools.validate_french_release import (
    ARCHIVE_SHA256,
    LEGACY_V201_CREDIT_TILE_IDS,
    TARGET_SHA256,
    ROOT,
    _ips,
    patch_legacy_v201_title_credits,
    sha256,
    validate_mesen_title,
)


ACTIVE_V2010_IPS = (
    ROOT / "releases/fr/2.0.10/Pokemon_Jaune_FR_v2.0.10.ips"
)
ACTIVE_V2010_IPS_SHA256 = (
    "974c0edce8713baef11b2f89ea83e989"
    "457c86fc745b7addb860dbfa271d1532"
)
CANONICAL_YELLOW_SIZE = 2_097_168

class FrenchReleaseValidationTests(unittest.TestCase):
    def _ips_map(self, path: Path) -> dict[int, int]:
        records, truncate = parse_ips(path)
        self.assertIsNone(truncate)
        return {
            record.offset + index: value
            for record in records
            for index, value in enumerate(record.data)
        }

    def test_active_v2_0_10_ips_is_well_formed_and_pinned(self) -> None:
        payload = ACTIVE_V2010_IPS.read_bytes()
        self.assertEqual(sha256(payload), ACTIVE_V2010_IPS_SHA256)
        records, truncate = parse_ips(ACTIVE_V2010_IPS)
        self.assertIsNone(truncate)
        self.assertTrue(records)
        occupied: set[int] = set()
        for record in records:
            addresses = set(range(record.offset, record.offset + len(record.data)))
            self.assertTrue(occupied.isdisjoint(addresses))
            occupied.update(addresses)
        self.assertLess(max(occupied), CANONICAL_YELLOW_SIZE)

    def test_v2_0_1_ips_diff_is_confined_to_legacy_credit_storage(self) -> None:
        archive = self._ips_map(
            ROOT / "releases/fr/2.0.0/Pokemon_Jaune_FR_repacked_title.ips"
        )
        active = self._ips_map(
            ROOT / "releases/fr/2.0.1/Pokemon_Jaune_FR_v2.0.1.ips"
        )
        expected: dict[int, int] = {}
        for tile_id, tile in zip(
            LEGACY_V201_CREDIT_TILE_IDS,
            title_credit_tiles("LUIGA2009, ZLADE, CHPEXO"),
            strict=True,
        ):
            offset = TITLE_PT1_FILE + tile_id * 16
            expected.update(
                (offset + index, value) for index, value in enumerate(tile)
            )
        nt_offset = TITLE_NT_FILE + (
            ENGLISH_CREDIT_NT_ROW * 32 + ENGLISH_CREDIT_NT_COLUMN
        )
        expected.update(
            (nt_offset + index, value)
            for index, value in enumerate(LEGACY_V201_CREDIT_TILE_IDS)
        )
        differences = {
            offset
            for offset in set(archive) | set(active)
            if archive.get(offset) != active.get(offset)
        }
        self.assertTrue(differences)
        self.assertLessEqual(differences, set(expected))
        for offset in set(active) & set(expected):
            self.assertEqual(active[offset], expected[offset])

    @unittest.skipUnless((ROOT / "yellow.nes").is_file(), "yellow.nes absent")
    def test_v2_0_1_delta_is_exactly_the_credit_patch(self) -> None:
        yellow = (ROOT / "yellow.nes").read_bytes()
        archive = _ips(
            yellow,
            ROOT / "releases/fr/2.0.0/Pokemon_Jaune_FR_repacked_title.ips",
        )
        active = _ips(
            yellow,
            ROOT / "releases/fr/2.0.1/Pokemon_Jaune_FR_v2.0.1.ips",
        )
        self.assertEqual(sha256(archive), ARCHIVE_SHA256)
        self.assertEqual(sha256(active), TARGET_SHA256)
        expected = bytearray(archive)
        patch_legacy_v201_title_credits(expected)
        self.assertEqual(bytes(expected), active)

    @unittest.skipUnless(
        (ROOT / "build/french-title-credits-mesen/mesen_run_manifest.txt").is_file(),
        "preuve Mesen privée absente",
    )
    def test_stored_v2_0_1_mesen_title_evidence_is_bound_to_legacy_sha(self) -> None:
        errors = validate_mesen_title(ROOT / "build/french-title-credits-mesen")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
