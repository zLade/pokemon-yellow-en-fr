"""Contrats du catalogue et du point d'entrée public ; intégration opt-in."""
from __future__ import annotations

import argparse
import contextlib
import csv
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import build_french_release as builder
from tools.french_font import encode_game_text, decode_game_text


class FrenchBuildTests(unittest.TestCase):
    def test_catalogue_without_rom(self):
        report = builder.check()
        self.assertEqual(report["catalogue"], 1931)
        self.assertEqual(report["restaurations"], 85)
        self.assertEqual(report["attaques_graphiques"], 94)
        self.assertEqual(report["variantes"], 5)
        self.assertEqual(builder.mapper.default_move_label_catalogue("fr-FR"),
                         builder.core.DEFAULT_MOVE_LABEL_CATALOG)

    def test_french_codec_without_rom(self):
        text = "À Â É Î Ç à â ç è é ê î ï ô ù û"
        self.assertEqual(decode_game_text(encode_game_text(text)), text)
        with self.assertRaises(UnicodeEncodeError):
            encode_game_text("⚡")

    @contextlib.contextmanager
    def modified_catalogue(self, mutate):
        with builder.CATALOGUE.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields, rows = reader.fieldnames, list(reader)
        mutate(rows)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "catalogue.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            with patch.object(builder, "CATALOGUE", path):
                yield path

    def test_changed_wording_is_not_pinned_to_release(self):
        def mutate(rows):
            rows[-1]["fr_text"] = "Bonjour !"
        with self.modified_catalogue(mutate) as path:
            self.assertEqual(builder.check()["statut"], "PASS")
            self.assertIn("Bonjour !", builder.core.load_restorations(path).values())

    def test_missing_duplicate_and_unknown_rows_are_rejected(self):
        for mutate in (lambda rows: rows.pop(), lambda rows: rows.append(rows[0]),
                       lambda rows: rows[0].update(stable_key="INCONNU")):
            with self.subTest(mutate=mutate), self.modified_catalogue(mutate):
                with self.assertRaisesRegex(ValueError, "Structure"):
                    builder.check()

    def test_blank_restoration_and_reserved_character_are_rejected(self):
        for text in ("", "Texte @ interdit"):
            with self.subTest(text=text), self.modified_catalogue(lambda rows: rows[-1].update(fr_text=text)):
                with self.assertRaises(ValueError):
                    builder.check()

    def test_pitch_changes_only_the_69_expected_bytes(self):
        source = b"\0" * builder.PITCH_START + builder.PITCH_BEFORE + b"suffixe"
        result = builder.apply_pitch(source)
        self.assertEqual(len(result), len(source))
        self.assertEqual(sum(a != b for a, b in zip(source, result)), 69)
        self.assertEqual(result[:builder.PITCH_START], source[:builder.PITCH_START])
        self.assertTrue(result.endswith(b"suffixe"))
        with self.assertRaisesRegex(ValueError, "musicale"):
            builder.apply_pitch(result)

    def test_destination_must_be_new_and_scoped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(builder, "ROOT", root), patch.object(builder.subprocess, "run") as git:
                git.return_value.returncode = 0
                git.return_value.stdout = b""
                allowed = root / "build" / "test"
                self.assertEqual(builder.safe_destination(allowed), allowed.resolve())
                allowed.mkdir(parents=True)
                sentinel = allowed / "source.txt"
                sentinel.write_text("conserver")
                for candidate in (root, root.parent / "outside", root / "releases", allowed):
                    with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                        builder.safe_destination(candidate)
                self.assertEqual(sentinel.read_text(), "conserver")
                git.return_value.stdout = b"build/tracked\0"
                with self.assertRaisesRegex(ValueError, "suivis"):
                    builder.safe_destination(root / "build" / "tracked")

    def test_wrong_source_creates_no_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wrong = root / "wrong.nes"
            wrong.write_bytes(b"NES\x1a")
            args = argparse.Namespace(english=wrong, chinese=wrong, yellow=wrong,
                                      output_dir=root / "output", verify_release=False)
            with self.assertRaisesRegex(ValueError, "source incorrecte"):
                builder.build(args)
            self.assertFalse(args.output_dir.exists())
            self.assertEqual(wrong.read_bytes(), b"NES\x1a")


@unittest.skipUnless(os.environ.get("NJ046_VERIFY_RELEASE") == "1" and
                     all(path.is_file() for path in builder.DEFAULT_ROMS.values()),
                     "Intégration : définir NJ046_VERIFY_RELEASE=1 et fournir les deux ROMs")
class FrenchReleaseIntegrationTests(unittest.TestCase):
    def test_exact_release_and_protected_second_build(self):
        parent = builder.ROOT / "build"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fr-integration-", dir=parent) as temporary:
            args = argparse.Namespace(**builder.DEFAULT_ROMS, output_dir=Path(temporary) / "result",
                                      verify_release=True)
            with contextlib.redirect_stdout(io.StringIO()):
                report = builder.build(args)
            self.assertEqual(report["rom_sha256"], builder.ROM_HASH)
            self.assertEqual(report["ips_sha256"], builder.IPS_HASH)
            self.assertEqual(report["pointeurs"]["entries"], 1916)
            self.assertEqual(report["emulation"], "NON_EXECUTEE")
            with self.assertRaisesRegex(ValueError, "vide"):
                builder.build(args)


if __name__ == "__main__":
    unittest.main()
