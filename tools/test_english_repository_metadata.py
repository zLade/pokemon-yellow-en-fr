#!/usr/bin/env python3
"""ROM-free checks for English metadata and pinned translation payloads."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/source/chinese-english-fidelity"
LOCALE = ROOT / "locales/en-US"
LEDGER_HEADERS = [
    "id", "stable_key", "category", "source_offset_or_pointer", "script_line",
    "layout", "speaker", "french_reference_text", "chinese_text", "english_2015",
    "alignment_confidence", "translation_history", "naturalized",
    "chinese_fidelity_corrected", "review_verdict", "review_comment",
]
# These are language samples, not interface labels or editorial annotations.
REFERENCE_COLUMNS = {
    "french_reference_text", "french_text", "literal_french", "fr_text",
    "french_v2_gloss", "chinese_text", "candidate_chinese_text",
    "selected_chinese_text", "source_text", "source_en", "unicode",
    "english_2015", "english_text", "english_v2", "previous_english",
    "reviewed_english", "english_before_reference_pass", "previous_english_v2",
    "revised_english_v2",
}
PAYLOAD_COLUMNS = (
    "stable_key", "chinese_text", "english_2015", "french_v2_gloss",
    "english_v2", "source_offset_or_pointer", "pointer_references",
    "selected_pointer_references", "layout",
)
# A regression tripwire for the terminology found during the metadata review;
# this supplements human review, rather than claiming full language detection.
FRENCH_METADATA = re.compile(
    r"\b(?:les|une|dans|avec|pour|sans|aucun|aucune|fichier|fichiers|"
    r"erreur|erreurs|attendu|attendue|sortie|supprimé|supprimés|"
    r"restauré|restaurés|référence|références|traduction|"
    r"naturalisation|adapté|corrigé|vérifié|vérifiée|"
    r"texte|actuel|vide|dupliqué|incohérent|absente|introuvable)\b",
    re.IGNORECASE,
)


def digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or ()), list(reader)


class EnglishRepositoryMetadataTests(unittest.TestCase):
    def test_review_ledger_uses_the_english_schema(self) -> None:
        fields, rows = read_csv(ROOT / "LISTE_EXHAUSTIVE_DIALOGUES.csv")
        self.assertEqual(fields, LEDGER_HEADERS)
        self.assertEqual(len(rows), 1055)
        for row in rows:
            self.assertIn(row["naturalized"], ("yes", "no"))
            self.assertIn(row["chinese_fidelity_corrected"], ("yes", "no"))

    def test_csv_headers_and_annotations_are_english(self) -> None:
        paths = sorted({*ROOT.glob("*.csv"), *SOURCE.glob("*.csv"),
                        *LOCALE.glob("*.csv")})
        for path in paths:
            fields, rows = read_csv(path)
            for field in fields:
                with self.subTest(path=path.name, field=field):
                    self.assertRegex(field, r"^[a-z][a-z0-9_]*$")
                    self.assertIsNone(FRENCH_METADATA.search(field.replace("_", " ")))
            for index, row in enumerate(rows, 2):
                for field, value in row.items():
                    if field in REFERENCE_COLUMNS:
                        continue
                    with self.subTest(path=path.name, row=index, field=field):
                        self.assertIsNotNone(field, "Extra CSV cells without a header")
                        self.assertIsNotNone(value, "Missing CSV cell")
                        self.assertIsNone(FRENCH_METADATA.search(value), value)

    def test_review_batch_annotations_are_english(self) -> None:
        for path in sorted((LOCALE / "review_batches").glob("*.input.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            for row in document["entries"]:
                for field, value in row.items():
                    if field in REFERENCE_COLUMNS or not isinstance(value, str):
                        continue
                    with self.subTest(batch=path.name, key=row["stable_key"], field=field):
                        self.assertIsNone(FRENCH_METADATA.search(value), value)

    def test_metadata_migration_preserves_catalogue_payloads_and_pointers(self) -> None:
        _, rows = read_csv(LOCALE / "catalog.csv")
        self.assertEqual(len(rows), 1929)
        self.assertEqual(
            digest([[row[key] for key in PAYLOAD_COLUMNS] for row in rows]),
            "89ecb4fda346d429c5b1ba89f3f6db38cbfb8cdce26a80558c83f09f924b3de1",
        )

    def test_french_reference_patch_calls_and_line_numbers_are_unchanged(self) -> None:
        tree = ast.parse((ROOT / "script.py").read_text(encoding="utf-8-sig"))
        calls = [
            (node.lineno, ast.dump(node, include_attributes=False))
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "p"
        ]
        self.assertEqual(len(calls), 1844)
        self.assertEqual(digest(calls),
                         "d7cf673c5270ae27f815cec98e57eb182075693ab897bdafc78e198164719485")

    def test_published_derivative_hashes_match_tracked_inputs(self) -> None:
        summary = json.loads((SOURCE / "summary.json").read_text(encoding="utf-8"))
        files = {
            ROOT / "script.py": summary["script_sha256"],
            ROOT / "LISTE_EXHAUSTIVE_DIALOGUES.csv": summary["review_csv_sha256"],
            **{SOURCE / name: expected
               for name, expected in summary["derived_artifacts_sha256"].items()},
        }
        for path, expected in files.items():
            with self.subTest(path=path.name):
                # Git normalizes Python sources to LF on checkout.
                payload = path.read_bytes()
                if path.suffix == ".py":
                    payload = payload.replace(b"\r\n", b"\n")
                self.assertEqual(hashlib.sha256(payload).hexdigest(), expected)


if __name__ == "__main__":
    unittest.main()
