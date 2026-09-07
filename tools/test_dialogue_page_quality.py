#!/usr/bin/env python3
"""Regressions for the opt-in French dialogue page optimiser."""

from __future__ import annotations

import unittest

from tools.dialogue_layout import (
    DIALOGUE_LAYOUT,
    INTRO_DIALOGUE_LAYOUT,
    semantic_units,
    wrap_dialogue_lines,
    wrap_dialogue_lines_greedy,
)
from tools.dialogue_page_quality import (
    assess_page_boundary,
    audit_dialogue_pages,
    compare_script_dialogue_quality,
    optimise_dialogue_pages,
    quality_vector_dialogue_pages,
    wrap_dialogue_lines_dp,
)
from tools.french_font import encode_game_text


def semantic_bytes(text: str) -> bytes:
    return b" ".join(
        encode_game_text(unit)
        for unit in semantic_units(text)
    )


class DialoguePageQualityTests(unittest.TestCase):
    def assertSemanticIdentity(
        self,
        source: str,
        lines: tuple[bytes, ...],
    ) -> None:
        visible = b" ".join(line.rstrip(b" ") for line in lines)
        self.assertEqual(visible, semantic_bytes(source))

    def test_dp_preserves_units_order_and_19_column_limit(self) -> None:
        source = (
            "Tu vas affronter le Conseil des 4 ? "
            "Prépare bien tes Pokémon !"
        )
        lines = wrap_dialogue_lines_dp(source)
        self.assertTrue(all(0 < len(line) <= 19 for line in lines))
        self.assertTrue(all(len(line) == 19 for line in lines[:-1]))
        self.assertSemanticIdentity(source, lines)

    def test_dp_moves_article_with_its_noun(self) -> None:
        source = "Tu vas affronter le Conseil des 4 ?"
        greedy = wrap_dialogue_lines_greedy(source)
        optimised = wrap_dialogue_lines_dp(
            source,
            preserve_encoded_length=False,
        )
        self.assertEqual(greedy[0].rstrip(), b"Tu vas affronter le")
        self.assertEqual(optimised[0].rstrip(), b"Tu vas affronter")
        self.assertEqual(optimised[1].rstrip(), b"le Conseil des 4 ?")
        self.assertFalse(audit_dialogue_pages(optimised))

    def test_dp_keeps_negation_together_after_short_sentence(self) -> None:
        source = "Attends ! Ne sors pas ! C'est dangereux !"
        greedy = wrap_dialogue_lines_greedy(source)
        optimised = wrap_dialogue_lines_dp(
            source,
            preserve_encoded_length=False,
        )
        self.assertEqual(greedy[0].rstrip(), b"Attends ! Ne sors")
        self.assertEqual(
            tuple(line.rstrip() for line in optimised),
            (
                b"Attends !",
                b"Ne sors pas !",
                b"C'est dangereux !",
            ),
        )
        self.assertLess(
            quality_vector_dialogue_pages(optimised),
            quality_vector_dialogue_pages(greedy),
        )

    def test_audit_finds_strong_end_and_start_orphans(self) -> None:
        issue = assess_page_boundary(
            "Tu vas affronter le",
            "Conseil des 4 ?",
        )
        self.assertIsNotNone(issue)
        self.assertEqual(issue.severity, "strong")
        self.assertIn("trailing function word", " ".join(issue.reasons))

        issue = assess_page_boundary("Ne sors", "pas !")
        self.assertIsNotNone(issue)
        self.assertEqual(issue.severity, "strong")
        self.assertIn("leading complement", " ".join(issue.reasons))

    def test_sentence_boundary_is_not_a_false_positive(self) -> None:
        self.assertIsNone(
            assess_page_boundary(
                "Tout va bien.",
                "Mais reste prudent !",
            )
        )

    def test_title_abbreviation_is_not_treated_as_sentence_end(self) -> None:
        issue = assess_page_boundary("Le Prof.", "Chen arrive.")
        self.assertIsNotNone(issue)
        self.assertEqual(issue.severity, "strong")
        self.assertIn("trailing abbreviated title", " ".join(issue.reasons))

    def test_english_reason_labels_preserve_protected_boundary_scores(self) -> None:
        for pages in (("Le Prof.", "Chen arrive."), ("Mont", "Sélénite")):
            with self.subTest(pages=pages):
                vector = quality_vector_dialogue_pages(pages)
                self.assertEqual(vector[:2], (1, 1))

    def test_audit_exposes_short_unpunctuated_fragment(self) -> None:
        issue = assess_page_boundary("trouvé", "les Pokémon")
        self.assertIsNotNone(issue)
        self.assertEqual(issue.severity, "weak")
        self.assertIn("very short trailing fragment", " ".join(issue.reasons))

    def test_explicit_newlines_remain_authoritative_pages(self) -> None:
        source = (
            "Maman : C'est vrai.\n"
            "Tous les garçons\n"
            "partent un jour."
        )
        plan = optimise_dialogue_pages(source)
        self.assertEqual(
            tuple(line.rstrip() for line in plan.lines),
            (
                b"Maman : C'est vrai.",
                b"Tous les gar[ons",
                b"partent un jour.",
            ),
        )
        self.assertEqual(plan.forced_page_breaks, 2)
        self.assertSemanticIdentity(source, plan.lines)

    def test_explicit_page_over_19_columns_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "forced dialogue page too long"):
            optimise_dialogue_pages(
                "Cette page explicite dépasse dix-neuf colonnes\nSuite"
            )

    def test_introduction_keeps_17_column_first_page(self) -> None:
        source = "1234567890123 motlong encore du texte"
        lines = wrap_dialogue_lines_dp(
            source,
            INTRO_DIALOGUE_LAYOUT,
        )
        self.assertEqual(len(lines[0]), 17)
        self.assertTrue(all(len(line) == 19 for line in lines[1:-1]))
        self.assertSemanticIdentity(source, lines)

    def test_oversized_lexical_unit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "too long"):
            wrap_dialogue_lines_dp("anticonstitutionnellement")

    def test_dp_is_deterministic(self) -> None:
        source = (
            "Je suis Olga du Conseil des 4 ! "
            "Tes Pokémon vont combattre."
        )
        first = optimise_dialogue_pages(source, DIALOGUE_LAYOUT)
        second = optimise_dialogue_pages(source, DIALOGUE_LAYOUT)
        self.assertEqual(first, second)

    def test_release_wrapper_uses_size_safe_dp_plan(self) -> None:
        source = "Tu vas affronter le Conseil des 4 ?"
        self.assertEqual(
            wrap_dialogue_lines(source),
            wrap_dialogue_lines_dp(source),
        )

    def test_representative_quality_strictly_improves(self) -> None:
        samples = (
            "Tu as tous les Badges. Pas mal !",
            "Bienvenue ! Je suis Olga du Conseil des 4 !",
            "Sacha, nous allons tous gagner ensemble !",
            "Je n'arrive pas à croire que mes dragons aient perdu !",
        )
        improved = 0
        for source in samples:
            with self.subTest(source=source):
                greedy = wrap_dialogue_lines_greedy(source)
                optimised = wrap_dialogue_lines_dp(
                    source,
                    preserve_encoded_length=False,
                )
                before = quality_vector_dialogue_pages(greedy)
                after = quality_vector_dialogue_pages(optimised)
                self.assertLessEqual(after, before)
                improved += (
                    after < before
                )
                self.assertSemanticIdentity(source, optimised)
        self.assertGreaterEqual(improved, 3)

    def test_default_keeps_greedy_minimum_page_count(self) -> None:
        source = (
            "RÉGIS : J'ai baissé ma garde. Zut ! À ce niveau, tu ne "
            "gagneras jamais la Ligue. Entraîne-toi encore ! "
            "Bon, j'y vais. À plus !"
        )
        greedy = wrap_dialogue_lines_greedy(source)
        optimised = wrap_dialogue_lines_dp(source)
        self.assertEqual(len(optimised), len(greedy))
        self.assertLessEqual(
            sum(len(line) for line in optimised),
            sum(len(line) for line in greedy),
        )
        audit_mode = wrap_dialogue_lines_dp(
            source,
            preserve_encoded_length=False,
        )
        self.assertEqual(len(audit_mode), len(greedy))
        self.assertGreater(
            sum(len(line) for line in audit_mode),
            sum(len(line) for line in greedy),
        )

    def test_opt_out_and_max_pages_control_page_growth(self) -> None:
        source = (
            "RÉGIS : J'ai baissé ma garde. Zut ! À ce niveau, tu ne "
            "gagneras jamais la Ligue. Entraîne-toi encore ! "
            "Bon, j'y vais. À plus !"
        )
        minimum = optimise_dialogue_pages(source)
        unrestricted = optimise_dialogue_pages(
            source,
            preserve_minimum_page_count=False,
            preserve_encoded_length=False,
        )
        capped = optimise_dialogue_pages(
            source,
            preserve_minimum_page_count=False,
            preserve_encoded_length=False,
            max_pages=8,
        )
        self.assertEqual(len(minimum.lines), 7)
        self.assertEqual(len(capped.lines), 8)
        self.assertGreater(len(unrestricted.lines), len(capped.lines))
        with self.assertRaisesRegex(ValueError, "7 minimum"):
            optimise_dialogue_pages(
                source,
                preserve_minimum_page_count=False,
                preserve_encoded_length=False,
                max_pages=6,
            )

    def test_full_report_exposes_residual_and_growth_schema(self) -> None:
        report = compare_script_dialogue_quality(
            "script.py",
            sample_limit=0,
        )
        self.assertEqual(report["common_dialogue_rows"], 967)
        residuals = report["residual_strong_rows"]
        self.assertEqual(
            sum(row["strong_issue_count"] for row in residuals),
            report["dynamic_programming"]["issue_counts"]["strong"],
        )
        self.assertEqual(
            report["dynamic_programming"]["issue_counts"]["strong"],
            0,
        )
        for row in residuals:
            self.assertIn(row["prg_pair"], {6, 7})
            self.assertTrue(row["dp_pages"])
            self.assertEqual(
                row["strong_issue_count"],
                len(row["strong_boundaries"]),
            )
            self.assertTrue(
                all(
                    boundary["severity"] == "strong"
                    and boundary["reasons"]
                    for boundary in row["strong_boundaries"]
                )
            )

        candidates = report["encoded_growth_candidates"]
        self.assertIsInstance(candidates, list)
        for row in candidates:
            self.assertGreater(row["delta_encoded_bytes"], 0)
            self.assertGreater(row["strong_gain"], 0)
            self.assertEqual(
                row["strong_gain"],
                row["strong_before"] - row["strong_after"],
            )
        summary = report["encoded_growth_candidate_summary"]
        self.assertEqual(summary["candidate_rows"], len(candidates))
        self.assertEqual(
            summary["delta_encoded_bytes"],
            sum(row["delta_encoded_bytes"] for row in candidates),
        )
        self.assertEqual(
            summary["strong_gain"],
            sum(row["strong_gain"] for row in candidates),
        )


if __name__ == "__main__":
    unittest.main()
