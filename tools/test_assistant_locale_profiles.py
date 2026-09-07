#!/usr/bin/env python3
"""Focused integration tests for locale-aware assistant build inputs."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tools.rom_builder as assistant
from tools.locales.profiles import (
    ENGLISH_TEXT_PROFILE,
    FRENCH_TEXT_PROFILE,
)
from tools.restoration_topology import RESTORATION_REFERENCES


ROOT = Path(__file__).resolve().parent.parent
ENGLISH_BASE = ROOT / "Pokemon Yellow English 9-23-2015.nes"
ASSISTANT = ROOT / "tools/rom_builder.py"


class TranslationCsvProfileTests(unittest.TestCase):
    def _write_csv(
        self,
        path: Path,
        fieldnames: list[str],
        rows: list[dict[str, str]],
    ) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


    def test_english_prefers_en_v2_then_english_v2_and_never_french_gloss(
        self,
    ) -> None:
        fields = [
            "record_type",
            "source_offset_or_pointer",
            "source_capacity_bytes",
            "layout",
            "en_v2",
            "english_v2",
            "french_v2_gloss",
            "review_status",
        ]
        rows = [
            {
                "record_type": "MAIN",
                "source_offset_or_pointer": "0x0301F9",
                "source_capacity_bytes": "9",
                "layout": "",
                "en_v2": "Primary",
                "english_v2": "Secondary",
                "french_v2_gloss": "Jamais compilé",
                "review_status": "reviewed",
            },
            {
                "record_type": "MAIN",
                "source_offset_or_pointer": "0x030203",
                "source_capacity_bytes": "12",
                "layout": "",
                "en_v2": "",
                "english_v2": "Fallback",
                "french_v2_gloss": "Toujours ignoré",
                "review_status": "approved",
            },
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.csv"
            self._write_csv(path, fields, rows)
            loaded = assistant.read_translation_csv(
                path,
                text_profile=ENGLISH_TEXT_PROFILE,
                skip_restoration_rows=True,
            )

        self.assertEqual([row.text for row in loaded], ["Primary", "Fallback"])
        self.assertEqual([row.max_len for row in loaded], [9, 12])

    def test_english_pending_or_empty_review_status_is_fatal(self) -> None:
        for status in ("", "pending", "draft", "unreviewed"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "catalog.csv"
                self._write_csv(
                    path,
                    [
                        "record_type",
                        "source_offset_or_pointer",
                        "layout",
                        "english_v2",
                        "review_status",
                    ],
                    [
                        {
                            "record_type": "MAIN",
                            "source_offset_or_pointer": "0x0301F9",
                            "layout": "",
                            "english_v2": "Reviewed-looking text",
                            "review_status": status,
                        }
                    ],
                )
                with self.assertRaisesRegex(ValueError, "review_status"):
                    assistant.read_translation_csv(
                        path,
                        text_profile=ENGLISH_TEXT_PROFILE,
                    )


class RestorationProfileTests(unittest.TestCase):
    def _write_catalogue(self, path: Path, *, omit: int | None = None) -> None:
        fields = [
            "record_type",
            "stable_key",
            "source_offset_or_pointer",
            "selected_pointer_references",
            "layout",
            "english_v2",
            "french_v2_gloss",
            "review_status",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow(
                {
                    "record_type": "MAIN",
                    "stable_key": "MAIN:0x0301F9",
                    "source_offset_or_pointer": "0x0301F9",
                    "layout": "",
                    "english_v2": "Fainted!",
                    "french_v2_gloss": "K.O. !",
                    "review_status": "reviewed",
                }
            )
            for reference in sorted(RESTORATION_REFERENCES):
                if reference == omit:
                    continue
                rendered = f"0x{reference:06X}"
                writer.writerow(
                    {
                        "record_type": "RESTORED",
                        "stable_key": f"RESTORED:{rendered}",
                        "source_offset_or_pointer": rendered,
                        "selected_pointer_references": rendered,
                        "layout": "dialogue_19_19",
                        "english_v2": "Restored",
                        "french_v2_gloss": "Glossaire français ignoré",
                        "review_status": "reviewed",
                    }
                )

    def test_unified_catalogue_splits_main_and_exactly_85_restorations(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.csv"
            self._write_catalogue(path)
            main_rows = assistant.read_translation_csv(
                path,
                text_profile=ENGLISH_TEXT_PROFILE,
                skip_restoration_rows=True,
            )
            restorations = assistant.load_restoration_texts_csv(
                path,
                text_profile=ENGLISH_TEXT_PROFILE,
            )

        self.assertEqual(len(main_rows), 1)
        self.assertEqual(main_rows[0].offset, 0x0301F9)
        self.assertEqual(set(restorations), set(RESTORATION_REFERENCES))
        self.assertEqual(set(restorations.values()), {"Restored"})

    def test_missing_restoration_is_rejected_by_neutral_topology(self) -> None:
        missing = min(RESTORATION_REFERENCES)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalog.csv"
            self._write_catalogue(path, omit=missing)
            with self.assertRaisesRegex(
                ValueError,
                f"missing 0x{missing:06X}",
            ):
                assistant.load_restoration_texts_csv(
                    path,
                    text_profile=ENGLISH_TEXT_PROFILE,
                )

    @unittest.skipUnless(ENGLISH_BASE.is_file(), "canonical English base absent")
    def test_english_restorations_never_load_french_payloads(self) -> None:
        original = ENGLISH_BASE.read_bytes()
        texts = {
            reference: "Restored"
            for reference in RESTORATION_REFERENCES
        }
        self.assertFalse(hasattr(assistant, "_load_french_restoration_texts"))
        payloads = assistant.verified_dialogue_restoration_payloads(
            original,
            texts,
            text_profile=ENGLISH_TEXT_PROFILE,
        )
        self.assertEqual(len(payloads), 85)
        self.assertEqual(set(payloads.values()), {b"Restored"})



class AssistantProfilePolicyTests(unittest.TestCase):
    def test_cli_defaults_to_english_and_rejects_french(self) -> None:
        parser = assistant.build_parser()
        default = parser.parse_args(["build-repacked"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["build-repacked", "--profile", "fr-FR"])
        english = parser.parse_args(
            [
                "build-repacked",
                "--profile",
                "en-US",
                "--restorations-csv",
                "restorations.csv",
            ]
        )
        self.assertEqual(default.profile, "en-US")
        self.assertEqual(default.csv, "translation")
        self.assertIs(assistant.resolve_text_profile(), ENGLISH_TEXT_PROFILE)
        self.assertEqual(english.profile, "en-US")
        self.assertEqual(english.restorations_csv, "restorations.csv")

    def test_english_rejects_literal_at(self) -> None:
        self.assertEqual(
            assistant.profile_literal_slot_conflicts(
                "literal @",
                text_profile=ENGLISH_TEXT_PROFILE,
            ),
            {"@"},
        )
        with self.assertRaisesRegex(ValueError, "reserved é glyph slot"):
            assistant.format_profile_text(
                "literal @",
                text_profile=ENGLISH_TEXT_PROFILE,
            )

    @unittest.skipUnless(ENGLISH_BASE.is_file(), "canonical English base absent")
    def test_english_font_policy_is_a_true_noop_without_chr_export(self) -> None:
        original = ENGLISH_BASE.read_bytes()
        candidate = bytearray(original)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "english.nes"
            export_path, changed = assistant.apply_profile_font_and_export(
                original,
                candidate,
                output,
                text_profile=ENGLISH_TEXT_PROFILE,
            )
            self.assertFalse(output.exists())
        self.assertIsNone(export_path)
        self.assertEqual(changed, 0)
        self.assertEqual(bytes(candidate), original)



if __name__ == "__main__":
    unittest.main()
