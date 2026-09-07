#!/usr/bin/env python3
"""ROM-free source, schema and ownership checks for the English repository."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRANSLATION = ROOT / "translation"
REFERENCE_COLUMNS = {
    "chinese_text", "candidate_chinese_text", "selected_chinese_text",
    "source_text", "source_en", "unicode", "english_2015", "english_text",
    "english_v2", "french_v2_gloss", "french_text", "literal_french", "french_reference_text",
}
FRENCH_METADATA = re.compile(
    r"\b(?:les|une|dans|avec|pour|sans|aucun|aucune|fichier|fichiers|"
    r"erreur|erreurs|attendu|attendue|sortie|supprimé|supprimés|"
    r"restauré|restaurés|référence|références|traduction|"
    r"naturalisation|adapté|corrigé|vérifié|vérifiée|"
    r"texte|actuel|vide|dupliqué|incohérent|absente|introuvable)\b",
    re.IGNORECASE,
)


def rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


class EnglishRepositoryMetadataTests(unittest.TestCase):
    def test_single_translation_directory(self) -> None:
        self.assertEqual(
            {path.name for path in TRANSLATION.glob("*.csv")},
            {"catalog.csv", "pointer_variants.csv", "move_labels_two_line.csv"},
        )
        self.assertFalse((ROOT / "locales" / "en-US" / "catalog.csv").exists())
        self.assertFalse((ROOT / "script.py").exists())
        self.assertFalse((ROOT / "traduction_base.csv").exists())

    def test_csv_headers_and_annotations_are_english(self) -> None:
        paths = [*TRANSLATION.glob("*.csv"), *(ROOT / "data").rglob("*.csv")]
        self.assertGreater(len(paths), 3)
        for path in paths:
            fields, records = rows(path)
            for field in fields:
                with self.subTest(path=path.name, field=field):
                    self.assertRegex(field, r"^[a-z][a-z0-9_]*$")
                    self.assertIsNone(FRENCH_METADATA.search(field.replace("_", " ")))
            for index, record in enumerate(records, 2):
                for field, value in record.items():
                    with self.subTest(path=path.name, row=index, field=field):
                        self.assertIsNotNone(field, "Extra CSV cells without a header")
                        self.assertIsNotNone(value, "Missing CSV cell")
                        if field not in REFERENCE_COLUMNS:
                            self.assertIsNone(FRENCH_METADATA.search(value), value)

    def test_catalogue_ownership_is_preserved(self) -> None:
        fields, records = rows(TRANSLATION / "catalog.csv")
        self.assertFalse(set(fields) & {
            "script_line", "french_v2_gloss", "secondary_french_provenance",
            "encoded_length",
        }, "The editing table must not regain obsolete or computed columns")
        self.assertEqual(len(records), 1929)
        self.assertEqual(sum(row["record_type"] == "MAIN" for row in records), 1844)
        self.assertEqual(sum(row["record_type"] == "RESTORED" for row in records), 85)
        # Text is intentionally editable. This pins ownership, not wording.
        keys = ("stable_key", "record_type", "source_offset_or_pointer",
                "pointer_references", "selected_pointer_references", "layout")
        payload = json.dumps([[row[key] for key in keys] for row in records],
                             ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                         "058625f0c6607d2624f110c6b3f95941614eb49278e865e315ccebf0eff0efe8")

    def test_pinned_chinese_extraction(self) -> None:
        expected = {
            "chinese_records.csv": "89e7f91d2102533a47ac6c58ab5aab1471b13bebb66e20737796863e247f1cca",
            "chinese_glyph_map.csv": "5fa49b098eee1fab8ff854a899c3e3f3cb8111d5686dd2a131f52941acbcc1bd",
        }
        for name, sha256 in expected.items():
            with self.subTest(name=name):
                payload = (ROOT / "data" / "source" / name).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), sha256)


if __name__ == "__main__":
    unittest.main()
