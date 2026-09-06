#!/usr/bin/env python3
"""Unit tests for the strict English one-byte codec."""

from __future__ import annotations

import unittest

from tools.locales.english_codec import (
    EnglishCodecError,
    decode_english_text,
    decode_terminated_english_text,
    encode_english_text,
    encode_terminated_english_text,
)


class EnglishCodecTests(unittest.TestCase):
    def test_printable_ascii_is_byte_exact_except_reserved_at(self) -> None:
        source = "".join(chr(value) for value in range(0x20, 0x7F) if value != 0x40)
        expected = bytes(value for value in range(0x20, 0x7F) if value != 0x40)
        self.assertEqual(encode_english_text(source), expected)
        self.assertEqual(decode_english_text(expected), source)

    def test_unicode_e_acute_uses_reserved_at_glyph_slot(self) -> None:
        self.assertEqual(encode_english_text("Pokémon"), b"Pok@mon")
        self.assertEqual(decode_english_text(b"Pok@mon"), "Pokémon")

    def test_explicit_battle_line_break_round_trips_as_0a(self) -> None:
        self.assertEqual(
            encode_english_text("Pikachu\nwas caught!"),
            b"Pikachu\x0Awas caught!",
        )
        self.assertEqual(
            decode_english_text(b"Pikachu\x0Awas caught!"),
            "Pikachu\nwas caught!",
        )

    def test_literal_at_is_rejected_as_ambiguous(self) -> None:
        with self.assertRaisesRegex(EnglishCodecError, "reserved é glyph slot"):
            encode_english_text("trainer@example.test")

    def test_unsupported_unicode_and_controls_are_never_normalized(self) -> None:
        unsupported = (
            "É",
            "œ",
            "e\N{COMBINING ACUTE ACCENT}",
            "smart ’ quote",
            "no\N{NO-BREAK SPACE}break",
            "tab\tcharacter",
            "vertical\vtab",
            "emoji 🎮",
        )
        for source in unsupported:
            with self.subTest(source=source):
                with self.assertRaises(EnglishCodecError):
                    encode_english_text(source)

    def test_decoder_rejects_non_printable_bytes(self) -> None:
        for payload in (b"\x00", b"\x0d", b"\x1f", b"\x7f", b"\xff"):
            with self.subTest(payload=payload):
                with self.assertRaises(EnglishCodecError):
                    decode_english_text(payload)

    def test_terminated_payload_has_exactly_one_final_0d(self) -> None:
        payload = encode_terminated_english_text("Pokémon")
        self.assertEqual(payload, b"Pok@mon\x0d")
        self.assertEqual(decode_terminated_english_text(payload), "Pokémon")
        with self.assertRaisesRegex(EnglishCodecError, "missing"):
            decode_terminated_english_text(b"Pok@mon")
        with self.assertRaisesRegex(EnglishCodecError, "early"):
            decode_terminated_english_text(b"Pok\x0dmon\x0d")

    def test_empty_payload_round_trips_with_only_terminator(self) -> None:
        self.assertEqual(encode_terminated_english_text(""), b"\x0d")
        self.assertEqual(decode_terminated_english_text(b"\x0d"), "")


if __name__ == "__main__":
    unittest.main()
