#!/usr/bin/env python3
"""Regressions for the HZK16-free fidelity derivative refresh."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from rom_traduction_assistant import (
    TRANSLATION_BASE_ROM,
    cpu_addr_for_offset,
    pair_for_offset,
    verified_dialogue_restoration_payloads,
)
from tools.export_creator_cameo_inventory import exhaustive_rows
from tools.export_dialogue_review_table import write_csv as write_review_csv

from tools.refresh_chinese_fidelity_derivatives import (
    DEFAULT_EXTRACTION_DIRECTORY,
    DERIVED_DATA_FILENAMES,
    DERIVED_FILENAMES,
    EXPECTED_ENGLISH_REMOVED_POINTERS,
    EXPECTED_MAIN_DIALOGUES,
    EXPECTED_RESTORATIONS,
    IMMUTABLE_GLYPH_MAP_SHA256,
    IMMUTABLE_RECORDS_SHA256,
    PROVENANCE_MODE,
    ROM_DIR,
    build_refresh,
    verify_published_refresh,
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FidelityDerivativeRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.temporary_path = Path(cls.temporary.name)
        cls.review_csv = cls.temporary_path / "current-review.csv"
        write_review_csv(cls.review_csv, exhaustive_rows())

        english = bytearray((ROM_DIR / TRANSLATION_BASE_ROM).read_bytes())
        payloads = verified_dialogue_restoration_payloads(bytes(english))
        next_target_by_pair: dict[int, int] = {}
        for reference, payload in sorted(payloads.items()):
            pair = pair_for_offset(reference)
            target = next_target_by_pair.setdefault(
                pair,
                16 + pair * 0x8000 + 0x6000,
            )
            english[target:target + len(payload)] = payload
            english[target + len(payload)] = 0x0D
            english[reference:reference + 2] = cpu_addr_for_offset(
                target
            ).to_bytes(2, "little")
            next_target_by_pair[pair] = target + len(payload) + 1
        cls.french_rom = cls.temporary_path / "french-restoration-fixture.nes"
        cls.french_rom.write_bytes(english)
        cls.current_inputs = {
            "french_rom": cls.french_rom,
            "review_csv": cls.review_csv,
        }

        cls.refresh_directory = cls.temporary_path / "refresh"
        cls.refresh_directory.mkdir()
        for filename in ("chinese_records.csv", "chinese_glyph_map.csv"):
            shutil.copy2(
                DEFAULT_EXTRACTION_DIRECTORY / filename,
                cls.refresh_directory / filename,
            )
        cls.immutable_before = {
            filename: file_sha256(cls.refresh_directory / filename)
            for filename in ("chinese_records.csv", "chinese_glyph_map.csv")
        }
        cls.summary = build_refresh(
            source_extraction_directory=cls.refresh_directory,
            output_directory=cls.refresh_directory,
            **cls.current_inputs,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_provenance_is_explicit_and_no_false_absence_survives(self) -> None:
        summary_path = self.refresh_directory / "summary.json"
        stored = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(stored, self.summary)
        self.assertEqual(stored["provenance_mode"], PROVENANCE_MODE)
        self.assertEqual(stored["provenance"]["mode"], PROVENANCE_MODE)
        self.assertFalse(stored["provenance"]["immutable_source_reextracted"])
        self.assertFalse(stored["provenance"]["hzk16_input_used_for_refresh"])
        self.assertEqual(
            stored["source_dialogue_pointers_invalidated_in_english"],
            EXPECTED_ENGLISH_REMOVED_POINTERS,
        )
        self.assertEqual(
            stored["source_dialogue_pointers_restored_in_french"],
            EXPECTED_ENGLISH_REMOVED_POINTERS,
        )
        self.assertEqual(
            stored["source_dialogues_absent_from_english_and_french"],
            0,
        )
        self.assertEqual(stored["review_dialogue_rows"], 1055)
        self.assertEqual(
            stored["review_main_dialogues"],
            EXPECTED_MAIN_DIALOGUES,
        )
        self.assertEqual(
            stored["review_restored_dialogues"],
            EXPECTED_RESTORATIONS,
        )
        self.assertEqual(
            stored["restored_payloads_verified_in_french_rom"],
            EXPECTED_RESTORATIONS,
        )
        with (
            self.refresh_directory / "dialogues_absent_from_english_and_french.csv"
        ).open(newline="", encoding="utf-8") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), 0)

    def test_derived_hash_manifest_matches_every_published_csv(self) -> None:
        self.assertEqual(
            set(self.summary["derived_artifacts_sha256"]),
            set(DERIVED_DATA_FILENAMES),
        )
        for filename in DERIVED_DATA_FILENAMES:
            with self.subTest(filename=filename):
                self.assertEqual(
                    self.summary["derived_artifacts_sha256"][filename],
                    file_sha256(self.refresh_directory / filename),
                )

    def test_creator_cameos_are_refreshed_from_current_review_table(self) -> None:
        cameo_path = self.refresh_directory / "creator_cameo_dialogues.csv"
        with cameo_path.open(newline="", encoding="utf-8-sig") as handle:
            cameos = list(csv.DictReader(handle))
        with self.review_csv.open(
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            review_by_key = {
                row["cle_stable"]: row for row in csv.DictReader(handle)
            }
        self.assertEqual(len(cameos), 17)
        self.assertEqual(self.summary["creator_cameo_dialogues"], 17)
        for row in cameos:
            with self.subTest(stable_key=row["cle_stable"]):
                review = review_by_key[row["cle_stable"]]
                self.assertEqual(row["id"], review["id"])
                self.assertEqual(
                    row["texte_chinois_source"],
                    review["texte_chinois_source"],
                )
                self.assertEqual(
                    row["texte_francais_actuel"],
                    review["texte_francais"],
                )

    def test_restored_inventory_keeps_all_source_and_target_texts(self) -> None:
        path = self.refresh_directory / "restored_chinese_dialogues.csv"
        with path.open(newline="", encoding="utf-8-sig") as handle:
            restored = list(csv.DictReader(handle))
        with self.review_csv.open(
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            review_by_key = {
                row["cle_stable"]: row
                for row in csv.DictReader(handle)
                if row["cle_stable"].startswith("RESTORED:")
            }
        self.assertEqual(len(restored), EXPECTED_RESTORATIONS)
        self.assertEqual(
            set(review_by_key),
            {row["cle_stable"] for row in restored},
        )
        for row in restored:
            with self.subTest(stable_key=row["cle_stable"]):
                review = review_by_key[row["cle_stable"]]
                self.assertEqual(
                    row["texte_chinois_source"],
                    review["texte_chinois_source"],
                )
                self.assertEqual(
                    row["traduction_anglaise_rom_anglaise"],
                    review["traduction_anglaise_rom_anglaise"],
                )
                self.assertEqual(
                    row["texte_francais_actuel"],
                    review["texte_francais"],
                )

    def test_english_removal_inventory_survives_french_restoration(self) -> None:
        path = self.refresh_directory / "dialogues_removed_from_english.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            removed = list(csv.DictReader(handle))
        with (
            self.refresh_directory / "restored_chinese_dialogues.csv"
        ).open(newline="", encoding="utf-8-sig") as handle:
            restored_by_reference = {
                row["pointer_reference_hex"]: row
                for row in csv.DictReader(handle)
            }
        self.assertEqual(len(removed), EXPECTED_ENGLISH_REMOVED_POINTERS)
        self.assertEqual(
            len({row["pointer_reference_hex"] for row in removed}),
            EXPECTED_ENGLISH_REMOVED_POINTERS,
        )
        self.assertTrue(
            all(row["english_pointer_status"] == "invalid" for row in removed)
        )
        self.assertTrue(
            all(
                row["source_status"] == "removed_from_english_rom"
                for row in removed
            )
        )
        for row in removed:
            with self.subTest(reference=row["pointer_reference_hex"]):
                restored = restored_by_reference[
                    row["pointer_reference_hex"]
                ]
                self.assertEqual(
                    restored["texte_chinois_source"],
                    row["chinese_text"].lstrip("\n"),
                )
                self.assertTrue(
                    restored["traduction_anglaise_rom_anglaise"].startswith(
                        "ABSENT"
                    )
                )

    def test_immutable_unicode_extraction_is_preserved(self) -> None:
        self.assertEqual(
            self.immutable_before["chinese_records.csv"],
            IMMUTABLE_RECORDS_SHA256,
        )
        self.assertEqual(
            self.immutable_before["chinese_glyph_map.csv"],
            IMMUTABLE_GLYPH_MAP_SHA256,
        )
        self.assertEqual(
            {
                filename: file_sha256(self.refresh_directory / filename)
                for filename in (
                    "chinese_records.csv",
                    "chinese_glyph_map.csv",
                )
            },
            self.immutable_before,
        )

    def test_every_declared_derived_file_is_published(self) -> None:
        for filename in DERIVED_FILENAMES:
            with self.subTest(filename=filename):
                self.assertTrue((self.refresh_directory / filename).is_file())

    def test_refresh_is_byte_deterministic(self) -> None:
        second = self.temporary_path / "second"
        build_refresh(
            source_extraction_directory=self.refresh_directory,
            output_directory=second,
            **self.current_inputs,
        )
        for filename in DERIVED_FILENAMES:
            with self.subTest(filename=filename):
                self.assertEqual(
                    (self.refresh_directory / filename).read_bytes(),
                    (second / filename).read_bytes(),
                )

    def test_check_mode_accepts_current_published_derivatives(self) -> None:
        checked = verify_published_refresh(
            source_extraction_directory=self.refresh_directory,
            published_directory=self.refresh_directory,
            **self.current_inputs,
        )
        self.assertEqual(checked, self.summary)

    def test_check_mode_rejects_one_mutated_derivative(self) -> None:
        target = self.refresh_directory / "dialogues_absent_from_french.csv"
        original = target.read_bytes()
        try:
            target.write_bytes(original + b"stale\n")
            with self.assertRaisesRegex(
                ValueError,
                "dérivé publié périmé.*dialogues_absent_from_french",
            ):
                verify_published_refresh(
                    source_extraction_directory=self.refresh_directory,
                    published_directory=self.refresh_directory,
                    **self.current_inputs,
                )
        finally:
            target.write_bytes(original)

    def test_mutated_immutable_extraction_is_rejected(self) -> None:
        source = self.temporary_path / "mutated-source"
        source.mkdir()
        for filename in ("chinese_records.csv", "chinese_glyph_map.csv"):
            shutil.copy2(
                DEFAULT_EXTRACTION_DIRECTORY / filename,
                source / filename,
            )
        records = source / "chinese_records.csv"
        payload = bytearray(records.read_bytes())
        payload[-2] ^= 1
        records.write_bytes(payload)
        with self.assertRaisesRegex(ValueError, "records.*non canonique"):
            build_refresh(
                source_extraction_directory=source,
                output_directory=self.temporary_path / "rejected-source-output",
                **self.current_inputs,
            )

    def test_invalidated_french_restoration_is_rejected_before_publish(self) -> None:
        french_rom = self.temporary_path / "broken-french.nes"
        payload = bytearray(self.french_rom.read_bytes())
        payload[0x033137:0x033139] = b"00"
        french_rom.write_bytes(payload)
        output = self.temporary_path / "rejected-rom-output"
        with self.assertRaisesRegex(
            ValueError,
            "restaurations françaises non publiables",
        ):
            build_refresh(
                source_extraction_directory=DEFAULT_EXTRACTION_DIRECTORY,
                output_directory=output,
                french_rom=french_rom,
                review_csv=self.review_csv,
            )
        self.assertFalse((output / "summary.json").exists())

    def test_stale_review_csv_is_rejected(self) -> None:
        stale_review = self.temporary_path / "stale-review.csv"
        with self.review_csv.open(
            newline="",
            encoding="utf-8-sig",
        ) as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        rows[0]["texte_francais"] += " périmé"
        with stale_review.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        with self.assertRaisesRegex(ValueError, "table de relecture périmée"):
            build_refresh(
                source_extraction_directory=DEFAULT_EXTRACTION_DIRECTORY,
                output_directory=self.temporary_path / "rejected-review-output",
                review_csv=stale_review,
                french_rom=self.french_rom,
            )



class PublishedFidelityDerivativeTests(unittest.TestCase):
    def test_repository_published_derivatives_are_current(self) -> None:
        verify_published_refresh()


if __name__ == "__main__":
    unittest.main()
