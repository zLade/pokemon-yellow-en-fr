#!/usr/bin/env python3
"""Regression tests for canonical French accents and source layouts."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rom_traduction_assistant import (
    DIALOGUE_LAYOUT,
    PATCH_SCRIPT,
    parse_patch_entries,
)
from tools.audit_french_accents import (
    A_GRAVE_ALL_OFFSETS,
    CA_OFFSETS,
    CONTEXT_PHRASE_RULES,
    CONTEXT_WORD_RULES,
    WORD_REPLACEMENTS,
    audit,
)
from tools.canonicalize_french_accents import (
    _text_chunks,
    canonicalized_source,
)
from tools.dialogue_inventory import load_dialogue_inventory
from tools.dialogue_layout import (
    INTRO_DIALOGUE_LAYOUT,
    RAW_LAYOUT,
)
from tools.french_font import (
    FRENCH_GLYPH_LABELS,
    encode_game_text,
)


EXPECTED_ENTRY_COUNT = 1844
EXPECTED_AMBIGUOUS_OFFSETS: set[str] = set()


class FrenchAccentAuditTests(unittest.TestCase):
    def test_status_summary_keys_are_english(self) -> None:
        for key in (
            "replacement_occurrences_by_status",
            "replacement_offsets_by_status",
        ):
            self.assertEqual(
                set(self.report["summary"][key]),
                {"certain", "contextual", "ambiguous"},
            )

    def test_ambiguous_status_keeps_priority_and_does_not_apply_unsafe_fix(self) -> None:
        fixture = 'p(0x0321DD, "tres equilib")\n'
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "accent_fixture.py"
            script.write_text(fixture, encoding="utf-8")
            report = audit(script)

        record = report["records"][0]
        self.assertEqual(record["status"], "ambiguous")
        self.assertTrue(record["corrected_text"].endswith("equilib"))
        replacements = {item["status"]: item for item in record["replacements"]}
        self.assertEqual(set(replacements), {"certain", "ambiguous"})
        self.assertTrue(replacements["certain"]["applied_to_proposal"])
        self.assertFalse(replacements["ambiguous"]["applied_to_proposal"])
        self.assertEqual(report["summary"]["ambiguous_offsets"], ["0x0321DD"])
        self.assertEqual(
            report["summary"]["record_status_counts"], {"ambiguous": 1}
        )

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = audit()
        cls.raw_entries = parse_patch_entries(
            apply_dialogue_inventory=False,
        )
        cls.effective_entries = parse_patch_entries()

    def test_source_has_expected_unique_canonical_entries(self) -> None:
        self.assertEqual(len(self.raw_entries), EXPECTED_ENTRY_COUNT)
        self.assertEqual(
            len({entry.offset for entry in self.raw_entries}),
            EXPECTED_ENTRY_COUNT,
        )
        self.assertEqual(self.raw_entries, self.effective_entries)

        inventory_offsets = set(load_dialogue_inventory())
        inventory_entries = [
            entry
            for entry in self.raw_entries
            if entry.offset in inventory_offsets
        ]
        self.assertEqual(len(inventory_entries), len(inventory_offsets))
        self.assertEqual(
            sum(
                entry.layout == DIALOGUE_LAYOUT
                for entry in inventory_entries
            ),
            498,
        )
        self.assertEqual(
            {
                entry.offset
                for entry in inventory_entries
                if entry.layout == INTRO_DIALOGUE_LAYOUT
            },
            {0x035DCC, 0x035E82},
        )
        self.assertEqual(
            sum(
                entry.layout == RAW_LAYOUT
                for entry in inventory_entries
            ),
            6,
        )

    def test_native_glyph_report_is_derived_from_charset(self) -> None:
        expected = [
            FRENCH_GLYPH_LABELS[code][1]
            for code in sorted(FRENCH_GLYPH_LABELS)
        ]
        self.assertEqual(
            self.report["native_single_byte_glyphs"],
            expected,
        )
        self.assertIn("Ç", expected)

    def test_all_safe_rules_preserve_encoded_length(self) -> None:
        pairs: set[tuple[str, str]] = set(WORD_REPLACEMENTS.items())
        pairs.update(
            (source, target)
            for rules in CONTEXT_PHRASE_RULES.values()
            for source, target, _ in rules
        )
        pairs.update(
            (source, target)
            for rules in CONTEXT_WORD_RULES.values()
            for source, target, _ in rules
        )
        if A_GRAVE_ALL_OFFSETS:
            pairs.add(("a", "à"))
        if CA_OFFSETS:
            pairs.update({("ca", "ça"), ("Ca", "Ça")})

        for source, target in sorted(pairs):
            with self.subTest(source=source, target=target):
                self.assertEqual(
                    len(encode_game_text(source)),
                    len(encode_game_text(target)),
                )

        for record in self.report["records"]:
            with self.subTest(offset=record["offset_hex"]):
                self.assertEqual(
                    record["encoded_bytes_before"],
                    record["encoded_bytes_after"],
                )

    def test_uppercase_ca_is_contextual_and_applied(self) -> None:
        fixture = (
            'p(0x03427E, "Ca arrive a cause des maitres Pokémon")\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "accent_fixture.py"
            script.write_text(fixture, encoding="utf-8")
            report = audit(script)

        self.assertEqual(report["summary"]["ambiguous_offsets"], [])
        self.assertEqual(report["summary"]["proposal_changed_offsets"], 1)
        record = report["records"][0]
        self.assertEqual(
            record["corrected_text"],
            "Ça arrive à cause des maîtres Pokémon",
        )
        ca_replacement = next(
            item
            for item in record["replacements"]
            if item["source"] == "Ca"
        )
        self.assertEqual(ca_replacement["status"], "contextual")
        self.assertTrue(ca_replacement["applied_to_proposal"])

    def test_imperative_aie_is_not_treated_as_interjection(self) -> None:
        fixture = 'p(0x03E565, "N\'aie pas peur.")\n'
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "accent_fixture.py"
            script.write_text(fixture, encoding="utf-8")
            report = audit(script)

        self.assertEqual(report["summary"]["proposal_changed_offsets"], 0)
        self.assertEqual(report["records"], [])

    def test_no_accent_ambiguity_remains(self) -> None:
        summary = self.report["summary"]
        self.assertEqual(summary["proposal_changed_offsets"], 0)
        self.assertEqual(
            summary["replacement_occurrences_by_status"]["certain"],
            0,
        )
        self.assertEqual(
            summary["replacement_occurrences_by_status"]["contextual"],
            0,
        )
        self.assertEqual(
            set(summary["ambiguous_offsets"]),
            EXPECTED_AMBIGUOUS_OFFSETS,
        )
        self.assertEqual(
            summary["replacement_occurrences_by_status"]["ambiguous"],
            len(EXPECTED_AMBIGUOUS_OFFSETS),
        )
        for record in self.report["records"]:
            self.assertEqual(record["status"], "ambiguous")
            self.assertEqual(
                record["effective_text_before"],
                record["corrected_text"],
            )
            self.assertTrue(
                all(
                    not replacement["applied_to_proposal"]
                    for replacement in record["replacements"]
                )
            )

    def test_canonicalizer_is_idempotent(self) -> None:
        updated, summary = canonicalized_source(PATCH_SCRIPT)
        self.assertEqual(
            updated,
            Path(PATCH_SCRIPT).read_bytes(),
        )
        self.assertEqual(summary["entries"], EXPECTED_ENTRY_COUNT)
        self.assertEqual(summary["rewritten_calls"], 0)
        self.assertEqual(summary["accent_rewrites"], 0)
        self.assertEqual(summary["dialogue_rewrites"], 0)
        self.assertEqual(summary["field_dialogue_rewrites"], 0)
        self.assertEqual(summary["field_padding_rewrites"], 0)
        self.assertEqual(summary["readability_rewrites"], 0)

    def test_dialogue_source_chunks_do_not_split_words(self) -> None:
        for entry in self.raw_entries:
            if entry.layout != DIALOGUE_LAYOUT:
                continue
            chunks = _text_chunks(entry.text)
            self.assertEqual("".join(chunks), entry.text)
            for left, right in zip(chunks, chunks[1:]):
                with self.subTest(offset=f"0x{entry.offset:06X}"):
                    self.assertFalse(
                        left[-1].isalnum() and right[0].isalnum(),
                        (left[-12:], right[:12]),
                    )


if __name__ == "__main__":
    unittest.main()
