#!/usr/bin/env python3
"""Unit tests for the codec-independent English NJ046 formatter."""

from __future__ import annotations

import unittest

from tools.locales.english_layout import (
    DIALOGUE_LAYOUT,
    FIXED_GRID_7X3_CAPACITY,
    FIXED_GRID_7X3_LAYOUT,
    INTRO_DIALOGUE_LAYOUT,
    POKEDEX_LAYOUT,
    POKEDEX_LINE_WIDTH,
    POKEDEX_MAX_LINES,
    RAW_LAYOUT,
    bind_encoder,
    dialogue_line_width,
    format_game_text,
    normalize_english_spacing,
    semantic_units,
    wrap_dialogue_17_19,
    wrap_dialogue_19_19,
    wrap_dialogue_lines,
    wrap_pokedex_13x4,
    wrap_pokedex_lines,
)


def encode_english_fixture(text: str) -> bytes:
    """Minimal strict one-byte fixture; the production codec is separate."""
    encoded = bytearray()
    for index, character in enumerate(text):
        if character == "\u00e9":
            encoded.append(0x40)
        elif " " <= character <= "~":
            encoded.append(ord(character))
        else:
            raise UnicodeEncodeError(
                "english-layout-fixture",
                text,
                index,
                index + 1,
                "unsupported character",
            )
    return bytes(encoded)


class EnglishLayoutTests(unittest.TestCase):
    def test_english_spacing_removes_french_punctuation_spaces(self) -> None:
        source = "Hello ! Are you ready ? Yes : now ; go ."
        self.assertEqual(
            normalize_english_spacing(source),
            "Hello! Are you ready? Yes: now; go.",
        )
        self.assertEqual(
            semantic_units(source),
            ("Hello!", "Are", "you", "ready?", "Yes:", "now;", "go."),
        )

    def test_spacing_normalizes_brackets_and_keeps_newlines(self) -> None:
        self.assertEqual(
            normalize_english_spacing("Wait ( now ) !\nNext : page"),
            "Wait (now)!\nNext: page",
        )

    def test_regular_dialogue_moves_a_complete_word(self) -> None:
        encoded = wrap_dialogue_19_19(
            "1234567890123 longword",
            encode_text=encode_english_fixture,
        )
        self.assertEqual(encoded[:19], b"1234567890123      ")
        self.assertEqual(encoded[19:], b"longword")

    def test_regular_dialogue_lines_are_19_columns_except_last(self) -> None:
        source = "alpha beta gamma delta epsilon zeta eta theta iota"
        lines = wrap_dialogue_lines(
            source,
            encode_text=encode_english_fixture,
        )
        self.assertTrue(all(len(line) == 19 for line in lines[:-1]))
        self.assertLessEqual(len(lines[-1]), 19)
        self.assertEqual(
            b" ".join(line.rstrip(b" ") for line in lines),
            encode_english_fixture(source),
        )

    def test_explicit_newline_forces_a_padded_page(self) -> None:
        lines = wrap_dialogue_lines(
            "First page\nSecond page",
            encode_text=encode_english_fixture,
        )
        self.assertEqual(lines, (b"First page         ", b"Second page"))

    def test_empty_forced_page_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty forced"):
            wrap_dialogue_19_19(
                "First page\n\nLast page",
                encode_text=encode_english_fixture,
            )

    def test_introduction_uses_17_then_19_columns(self) -> None:
        lines = wrap_dialogue_lines(
            "1234567890123 longword more text",
            INTRO_DIALOGUE_LAYOUT,
            encode_text=encode_english_fixture,
        )
        self.assertEqual(lines[0], b"1234567890123    ")
        self.assertEqual(len(lines[0]), 17)
        self.assertEqual(lines[1], b"longword more text")
        self.assertEqual(dialogue_line_width(0, INTRO_DIALOGUE_LAYOUT), 17)
        self.assertEqual(dialogue_line_width(1, INTRO_DIALOGUE_LAYOUT), 19)
        self.assertEqual(
            wrap_dialogue_17_19(
                "1234567890123 longword more text",
                encode_text=encode_english_fixture,
            ),
            b"".join(lines),
        )

    def test_pokedex_fits_at_most_four_13_column_lines(self) -> None:
        source = "Often mistaken for rocks, people step on them."
        lines = wrap_pokedex_lines(
            source,
            encode_text=encode_english_fixture,
        )
        self.assertEqual(
            lines,
            (
                b"Often        ",
                b"mistaken for ",
                b"rocks, people",
                b"step on them.",
            ),
        )
        self.assertEqual(POKEDEX_LINE_WIDTH, 13)
        self.assertEqual(POKEDEX_MAX_LINES, 4)
        self.assertEqual(
            wrap_pokedex_13x4(source, encode_text=encode_english_fixture),
            b"".join(lines),
        )

    def test_pokedex_rejects_a_fifth_line(self) -> None:
        with self.assertRaisesRegex(ValueError, "more than 4 lines"):
            wrap_pokedex_13x4(
                "aaaaaaaaaaaaa bbbbbbbbbbbbb ccccccccccccc "
                "ddddddddddddd eeeeeeeeeeeee",
                encode_text=encode_english_fixture,
            )

    def test_overlong_units_are_rejected_instead_of_split(self) -> None:
        with self.assertRaisesRegex(ValueError, "unit is too long"):
            wrap_dialogue_19_19(
                "antidisestablishmentarianism",
                encode_text=encode_english_fixture,
            )
        with self.assertRaisesRegex(ValueError, "unit is too long"):
            wrap_pokedex_13x4(
                "electromagnetic",
                encode_text=encode_english_fixture,
            )

    def test_widths_are_measured_after_codec_encoding(self) -> None:
        # The fixture mirrors the production requirement that \u00e9 occupies
        # the existing one-byte @ glyph slot in the unmodified English font.
        encoded = wrap_dialogue_19_19(
            "Pok\u00e9mon is ready !",
            encode_text=encode_english_fixture,
        )
        self.assertEqual(encoded, b"Pok@mon is ready!")

    def test_codec_errors_propagate_without_lossy_replacement(self) -> None:
        for source in (
            "Unsupported \u0153 glyph",
            "Unsupported\u00a0space",
            "Unsupported\ttab",
        ):
            with self.subTest(source=source):
                with self.assertRaises(UnicodeEncodeError):
                    wrap_dialogue_19_19(
                        source,
                        encode_text=encode_english_fixture,
                    )

    def test_raw_layout_preserves_source_bytes_exactly(self) -> None:
        source = "Hello   world !"
        self.assertEqual(
            format_game_text(
                source,
                RAW_LAYOUT,
                encode_text=encode_english_fixture,
            ),
            encode_english_fixture(source),
        )

    def test_fixed_item_grid_accepts_21_cells_and_rejects_22(self) -> None:
        self.assertEqual(FIXED_GRID_7X3_CAPACITY, 21)
        self.assertEqual(
            format_game_text(
                "X" * 21,
                FIXED_GRID_7X3_LAYOUT,
                encode_text=encode_english_fixture,
            ),
            b"X" * 21,
        )
        with self.assertRaisesRegex(ValueError, "fixed 7x3 text is too long"):
            format_game_text(
                "X" * 22,
                FIXED_GRID_7X3_LAYOUT,
                encode_text=encode_english_fixture,
            )

    def test_each_named_layout_dispatches_to_its_wrapper(self) -> None:
        regular = "A short English sentence."
        intro = "A short introduction sentence."
        pokedex = "Small and quick."
        self.assertEqual(
            format_game_text(
                regular,
                DIALOGUE_LAYOUT,
                encode_text=encode_english_fixture,
            ),
            wrap_dialogue_19_19(
                regular,
                encode_text=encode_english_fixture,
            ),
        )
        self.assertEqual(
            format_game_text(
                intro,
                INTRO_DIALOGUE_LAYOUT,
                encode_text=encode_english_fixture,
            ),
            wrap_dialogue_17_19(
                intro,
                encode_text=encode_english_fixture,
            ),
        )
        self.assertEqual(
            format_game_text(
                pokedex,
                POKEDEX_LAYOUT,
                encode_text=encode_english_fixture,
            ),
            wrap_pokedex_13x4(
                pokedex,
                encode_text=encode_english_fixture,
            ),
        )

    def test_bound_formatter_has_profile_friendly_signature(self) -> None:
        formatter = bind_encoder(encode_english_fixture)
        self.assertEqual(formatter("Pok\u00e9mon", RAW_LAYOUT), b"Pok@mon")
        self.assertEqual(
            formatter("Hello !", DIALOGUE_LAYOUT),
            b"Hello!",
        )

    def test_bad_encoder_contract_is_rejected_when_bound(self) -> None:
        def two_byte_space(text: str) -> bytes:
            return text.replace(" ", "  ").encode("ascii")

        with self.assertRaisesRegex(ValueError, "space as exactly one byte"):
            bind_encoder(two_byte_space)

    def test_unknown_layout_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown English text layout"):
            format_game_text(
                "Hello",
                "dialogue_magic",
                encode_text=encode_english_fixture,
            )


if __name__ == "__main__":
    unittest.main()
