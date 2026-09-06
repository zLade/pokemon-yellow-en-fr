#!/usr/bin/env python3
"""Regressions for explicit 17/19-column dialogue layout."""

from __future__ import annotations

import unittest

from tools.dialogue_layout import (
    DIALOGUE_LAYOUT,
    INTRO_DIALOGUE_LAYOUT,
    POKEDEX_LAYOUT,
    POKEDEX_LINE_WIDTH,
    POKEDEX_MAX_LINES,
    RAW_LAYOUT,
    dialogue_boundaries,
    format_game_text,
    midword_boundary_positions,
    text_midword_boundary_positions,
    wrap_dialogue_19_19,
    wrap_dialogue_17_19,
    wrap_dialogue_lines,
    wrap_pokedex_13x4,
    wrap_pokedex_lines,
)


class DialogueLayoutTests(unittest.TestCase):
    def test_unmarked_text_is_byte_for_byte_legacy_encoding(self) -> None:
        self.assertEqual(format_game_text("Bonjour le monde"), b"Bonjour le monde")

    def test_word_moves_whole_to_second_line(self) -> None:
        encoded = wrap_dialogue_19_19("1234567890123 motlong")
        self.assertEqual(encoded[:19], b"1234567890123      ")
        self.assertEqual(encoded[19:], b"motlong")
        self.assertEqual(midword_boundary_positions(encoded), ())

    def test_every_regular_line_has_19_columns(self) -> None:
        encoded = wrap_dialogue_19_19(
            "alpha beta gamma delta epsilon zeta eta theta iota"
        )
        self.assertEqual(dialogue_boundaries(len(encoded))[:2], (19, 38))
        self.assertEqual(len(encoded[:19]), 19)
        self.assertEqual(len(encoded[19:38]), 19)
        self.assertEqual(midword_boundary_positions(encoded), ())
        lines = wrap_dialogue_lines(
            "alpha beta gamma delta epsilon zeta eta theta iota"
        )
        self.assertTrue(all(len(line) == 19 for line in lines[:-1]))
        self.assertLessEqual(len(lines[-1]), 19)

    def test_bubble_boundary_does_not_split_word(self) -> None:
        encoded = wrap_dialogue_19_19(
            "un deux trois quatre cinq six sept huit neuf dix onze"
        )
        self.assertIn(38, dialogue_boundaries(len(encoded)))
        self.assertEqual(midword_boundary_positions(encoded), ())

    def test_newline_forces_a_readable_regular_dialogue_page(self) -> None:
        lines = wrap_dialogue_lines(
            "Une phrase brève\nUne autre phrase",
            DIALOGUE_LAYOUT,
        )
        self.assertEqual(
            lines,
            (
                b"Une phrase br|ve   ",
                b"Une autre phrase",
            ),
        )
        self.assertEqual(
            b" ".join(line.rstrip(b" ") for line in lines),
            b"Une phrase br|ve Une autre phrase",
        )

    def test_empty_forced_dialogue_page_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "forcée vide"):
            wrap_dialogue_19_19("Première page\n\nDernière page")

    def test_french_punctuation_stays_with_previous_unit(self) -> None:
        encoded = wrap_dialogue_19_19("RÉGIS : Salut ! Ça va ?")
        self.assertIn(b"R*GIS :", encoded)
        self.assertIn(b"Salut !", encoded)
        self.assertIn(b"va ?", encoded)

    def test_apostrophe_and_hyphen_are_not_split(self) -> None:
        encoded = wrap_dialogue_19_19(
            "Voici aujourd'hui un arc-en-ciel magnifique"
        )
        self.assertIn(b"aujourd'hui", encoded)
        self.assertIn(b"arc-en-ciel", encoded)
        self.assertEqual(encoded[:19], b"Voici aujourd'hui  ")
        self.assertTrue(encoded[19:].startswith(b"un arc-en-ciel"))

    def test_introduction_keeps_17_then_19_columns(self) -> None:
        encoded = wrap_dialogue_17_19(
            "1234567890123 motlong encore du texte"
        )
        self.assertEqual(
            dialogue_boundaries(
                len(encoded),
                INTRO_DIALOGUE_LAYOUT,
            )[:2],
            (17, 36),
        )
        self.assertEqual(encoded[:17], b"1234567890123    ")
        self.assertEqual(
            midword_boundary_positions(
                encoded,
                INTRO_DIALOGUE_LAYOUT,
            ),
            (),
        )

    def test_accented_glyph_is_one_column(self) -> None:
        encoded = format_game_text(
            "ÀÂÉÎÇàâçèéêîïôùû",
            DIALOGUE_LAYOUT,
        )
        self.assertEqual(
            encoded,
            b'"#*<;{~[|@}\\]^_`',
        )
        self.assertEqual(len(encoded), 16)

    def test_midword_detection_understands_accents_and_connectors(self) -> None:
        self.assertEqual(
            text_midword_boundary_positions("123456789012345678éx"),
            (19,),
        )
        self.assertEqual(
            midword_boundary_positions(
                format_game_text("123456789012345678éx"),
            ),
            (19,),
        )
        self.assertEqual(
            text_midword_boundary_positions("123456789012345678'hui"),
            (19,),
        )

    def test_ligature_fallback_uses_two_columns(self) -> None:
        self.assertEqual(format_game_text("cœur"), b"coeur")

    def test_lexical_unit_over_19_columns_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "trop longue"):
            wrap_dialogue_19_19("anticonstitutionnellement")

    def test_pokedex_wraps_four_lines_without_splitting_words(self) -> None:
        source = "Pris pour des rochers, on leur marche dessus."
        lines = wrap_pokedex_lines(source)
        self.assertEqual(
            lines,
            (
                b"Pris pour des",
                b"rochers, on  ",
                b"leur marche  ",
                b"dessus.",
            ),
        )
        self.assertEqual(
            wrap_pokedex_13x4(source),
            b"".join(lines),
        )
        self.assertEqual(
            format_game_text(source, POKEDEX_LAYOUT),
            b"".join(lines),
        )
        self.assertEqual(POKEDEX_LINE_WIDTH, 13)
        self.assertEqual(POKEDEX_MAX_LINES, 4)

    def test_pokedex_rejects_fifth_line(self) -> None:
        with self.assertRaisesRegex(ValueError, "trop longue"):
            wrap_pokedex_13x4(
                "aaaaaaaaaaaaa bbbbbbbbbbbbb ccccccccccccc "
                "ddddddddddddd eeeeeeeeeeeee"
            )

    def test_pokedex_rejects_word_over_13_columns(self) -> None:
        with self.assertRaisesRegex(ValueError, "trop longue"):
            wrap_pokedex_13x4("électromagnétique")

    def test_unknown_layout_is_fatal(self) -> None:
        with self.assertRaisesRegex(ValueError, "inconnu"):
            format_game_text("Bonjour", "dialogue_magique")

    def test_explicit_raw_layout_is_not_reflowed(self) -> None:
        self.assertEqual(
            format_game_text("Bonjour   monde", RAW_LAYOUT),
            b"Bonjour   monde",
        )

    def test_layout_is_deterministic(self) -> None:
        source = "Un texte français : toujours identique !"
        self.assertEqual(
            wrap_dialogue_19_19(source),
            wrap_dialogue_19_19(source),
        )


if __name__ == "__main__":
    unittest.main()
