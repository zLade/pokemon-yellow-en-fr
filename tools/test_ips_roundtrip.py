#!/usr/bin/env python3
"""Roundtrip and boundary regressions for the generic IPS helpers."""

from __future__ import annotations

import random
import sys
import tempfile
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROM_DIR))

from tools.rom_builder import (  # noqa: E402
    FINAL_IPS,
    FINAL_ROM,
    apply_ips,
    make_ips,
    parse_ips,
)


class IpsRoundtripTests(unittest.TestCase):
    def roundtrip(
        self,
        original: bytes,
        modified: bytes,
    ) -> tuple[bytes, list[object], int | None]:
        patch = make_ips(original, modified)
        with tempfile.TemporaryDirectory(prefix="pokemon-ips-test-") as temp:
            patch_path = Path(temp) / "test.ips"
            patch_path.write_bytes(patch)
            records, truncate = parse_ips(patch_path)
        self.assertEqual(apply_ips(original, records, truncate), modified)
        return patch, records, truncate

    def test_longer_target_including_zero_tail_roundtrips(self) -> None:
        patch, records, truncate = self.roundtrip(
            b"ABC",
            b"ABchange\x00\x00",
        )
        self.assertTrue(patch.startswith(b"PATCH"))
        self.assertEqual(truncate, 10)
        self.assertTrue(records)

    def test_shorter_and_empty_targets_roundtrip(self) -> None:
        for modified in (b"ABx", b"", b"short"):
            with self.subTest(modified=modified):
                _, _, truncate = self.roundtrip(
                    b"ABCDEF-long-source",
                    modified,
                )
                self.assertEqual(truncate, len(modified))

    def test_truncate_marker_can_extend_with_zeroes(self) -> None:
        self.assertEqual(
            apply_ips(b"AB", [], truncate=5),
            b"AB\x00\x00\x00",
        )

    def test_deterministic_randomized_roundtrips(self) -> None:
        randomizer = random.Random(0x163)
        for case in range(128):
            original_length = randomizer.randrange(0, 384)
            target_length = randomizer.randrange(0, 384)
            original = bytes(
                randomizer.randrange(256)
                for _ in range(original_length)
            )
            modified = bytearray(original[:target_length])
            if target_length > len(modified):
                modified.extend(
                    randomizer.randrange(256)
                    for _ in range(target_length - len(modified))
                )
            for _ in range(randomizer.randrange(0, 24)):
                if modified:
                    index = randomizer.randrange(len(modified))
                    modified[index] = randomizer.randrange(256)
            with self.subTest(case=case):
                self.roundtrip(original, bytes(modified))

    def test_records_are_split_at_the_65535_byte_limit(self) -> None:
        _, records, truncate = self.roundtrip(
            b"",
            b"X" * 0x10000,
        )
        self.assertEqual([len(record.data) for record in records], [0xFFFF, 1])
        self.assertEqual([record.offset for record in records], [0, 0xFFFF])
        self.assertEqual(truncate, 0x10000)

    def test_changed_record_at_eof_sentinel_offset_is_rebased(self) -> None:
        sentinel = int.from_bytes(b"EOF", "big")
        original = bytes(sentinel + 2)
        modified = bytearray(original)
        modified[sentinel] = 0xA5
        patch, records, truncate = self.roundtrip(original, bytes(modified))
        self.assertIsNone(truncate)
        self.assertNotIn(b"PATCHEOF\x00", patch)
        self.assertEqual(records[0].offset, sentinel - 1)
        self.assertEqual(records[0].data, b"\x00\xA5")

    def test_changed_target_size_must_fit_the_24_bit_footer(self) -> None:
        with self.assertRaisesRegex(ValueError, "limite 24 bits"):
            make_ips(b"", bytes(0x1000000))

    @unittest.skipUnless(
        (ROM_DIR / "yellow.nes").is_file()
        and (ROM_DIR / FINAL_ROM).is_file()
        and (ROM_DIR / FINAL_IPS).is_file(),
        "artefacts IPS courants absents",
    )
    def test_current_release_patch_is_byte_identical_and_roundtrips(self) -> None:
        original = (ROM_DIR / "yellow.nes").read_bytes()
        modified = (ROM_DIR / FINAL_ROM).read_bytes()
        expected_patch = (ROM_DIR / FINAL_IPS).read_bytes()
        actual_patch, _, _ = self.roundtrip(original, modified)
        self.assertEqual(actual_patch, expected_patch)


if __name__ == "__main__":
    unittest.main()
