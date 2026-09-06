#!/usr/bin/env python3
"""Tests for the deterministic BPS implementation."""

from __future__ import annotations

import random
import binascii
import struct
import unittest

from tools.bps_patch import (
    BpsError,
    apply_patch,
    create_patch,
    decode_number,
    encode_number,
    inspect_patch,
)


class BpsPatchTests(unittest.TestCase):
    @staticmethod
    def _external_style_patch(
        source: bytes,
        target: bytes,
        actions: bytes,
    ) -> bytes:
        patch = bytearray(b"BPS1")
        patch.extend(encode_number(len(source)))
        patch.extend(encode_number(len(target)))
        patch.extend(encode_number(0))
        patch.extend(actions)
        patch.extend(struct.pack("<I", binascii.crc32(source) & 0xFFFFFFFF))
        patch.extend(struct.pack("<I", binascii.crc32(target) & 0xFFFFFFFF))
        patch.extend(
            struct.pack("<I", binascii.crc32(patch) & 0xFFFFFFFF)
        )
        return bytes(patch)

    def test_number_codec_boundaries(self) -> None:
        values = [0, 1, 0x7F, 0x80, 0x3FFF, 0x4000, 2**32, 2**63 - 1]
        for value in values:
            with self.subTest(value=value):
                encoded = encode_number(value)
                decoded, offset = decode_number(encoded, 0)
                self.assertEqual(decoded, value)
                self.assertEqual(offset, len(encoded))

    def test_roundtrip_identical_shorter_and_longer(self) -> None:
        cases = [
            (b"", b""),
            (b"same", b"same"),
            (b"source is longer", b"short"),
            (b"short", b"target is considerably longer"),
            (bytes(range(256)), bytes(reversed(range(256)))),
        ]
        for source, target in cases:
            with self.subTest(source=len(source), target=len(target)):
                patch = create_patch(source, target, metadata=b"test")
                self.assertEqual(apply_patch(source, patch), target)
                info = inspect_patch(patch)
                self.assertEqual(info.source_size, len(source))
                self.assertEqual(info.target_size, len(target))
                self.assertEqual(info.metadata, b"test")

    def test_randomized_roundtrips_are_deterministic(self) -> None:
        rng = random.Random(0xB5A163)
        for index in range(250):
            source = bytes(rng.randrange(256) for _ in range(rng.randrange(512)))
            target = bytearray(source)
            for _ in range(rng.randrange(40)):
                if target and rng.randrange(3) == 0:
                    del target[rng.randrange(len(target))]
                elif rng.randrange(3) == 0:
                    target.insert(rng.randrange(len(target) + 1), rng.randrange(256))
                elif target:
                    target[rng.randrange(len(target))] = rng.randrange(256)
            expected = bytes(target)
            patch = create_patch(source, expected)
            with self.subTest(index=index):
                self.assertEqual(patch, create_patch(source, expected))
                self.assertEqual(apply_patch(source, patch), expected)

    def test_wrong_source_and_corruption_are_rejected(self) -> None:
        source = b"canonical source"
        patch = create_patch(source, b"translated target")
        with self.assertRaisesRegex(BpsError, "source checksum mismatch"):
            apply_patch(b"canonical sourcf", patch)

        corrupted = bytearray(patch)
        corrupted[len(corrupted) // 2] ^= 0x80
        with self.assertRaisesRegex(BpsError, "patch checksum mismatch"):
            apply_patch(source, bytes(corrupted))

        with self.assertRaises(BpsError):
            apply_patch(source, patch[:-1])

    def test_real_rom_roundtrip_can_be_added_without_special_cases(self) -> None:
        source = b"NES\x1a" + bytes(4092)
        target = source[:1024] + b"FR" + source[1026:] + b"extended"
        self.assertEqual(apply_patch(source, create_patch(source, target)), target)

    def test_reader_accepts_source_copy_and_target_copy_actions(self) -> None:
        source = b"abc123abc"
        target = b"abc123123abcabc"
        actions = b"".join(
            (
                encode_number(((3 - 1) << 2) | 0),  # SourceRead abc
                encode_number(((3 - 1) << 2) | 2),  # SourceCopy 123
                encode_number(3 << 1),
                encode_number(((3 - 1) << 2) | 3),  # TargetCopy 123
                encode_number(3 << 1),
                encode_number(((3 - 1) << 2) | 2),  # SourceCopy abc
                encode_number(0),
                encode_number(((3 - 1) << 2) | 3),  # TargetCopy abc
                encode_number((6 << 1) | 1),
            )
        )
        patch = self._external_style_patch(source, target, actions)

        self.assertEqual(apply_patch(source, patch), target)

    def test_invalid_copy_offsets_are_rejected(self) -> None:
        source = b"abc"
        actions = b"".join(
            (
                encode_number(((1 - 1) << 2) | 3),
                encode_number(0),
            )
        )
        patch = self._external_style_patch(source, b"a", actions)
        with self.assertRaisesRegex(BpsError, "outside target data"):
            apply_patch(source, patch)


if __name__ == "__main__":
    unittest.main()
