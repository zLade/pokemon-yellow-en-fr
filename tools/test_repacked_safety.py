"""English repacker safety checks; local ROM tests skip when the base is absent."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import rom_builder as builder
from tools.catalogue_io import open_csv
from tools.english_pointer_manifest import build_manifest
from tools.validate_english_bank_budget import validate_budget, DEFAULT_POLICY
from tools.validate_english_repacked import validate_candidate, EnglishRepackedError

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / builder.TRANSLATION_BASE_ROM
CATALOG = ROOT / "translation"
VARIANTS = ROOT / "translation/pointer_variants.csv"
MOVES = ROOT / "translation/move_labels_two_line.csv"
INVENTORY = ROOT / "data/validation/structural_pointer_inventory.json"
TABLE_HOLES = ((0x033193, 0x03319B), (0x0331B3, 0x0331CB),
               (0x038313, 0x038327), (0x03AF94, 0x03AFAE),
               (0x03AFEA, 0x03B002), (0x03CF3E, 0x03CF5A),
               (0x03D07A, 0x03D082))
FALSE_REFS = {0x031C9C, 0x0332F6, 0x03338C, 0x033FE6, 0x034010,
              0x034074, 0x03409A, 0x0340A5, 0x0340D2, 0x034185,
              0x034279, 0x0345C0, 0x034649, 0x034698, 0x0352F4,
              0x0354B0, 0x035A6D, 0x035AD6, 0x035B0E, 0x035B54,
              0x035BB6, 0x03A815, 0x03EC3B}


def read_rows(path):
    with open_csv(path) as handle:
        return list(csv.DictReader(handle))


def build_at(directory, *, catalogue=CATALOG, seed="1"):
    directory.mkdir(parents=True, exist_ok=True)
    arguments = [
        sys.executable, "-B", str(ROOT / "tools/rom_builder.py"), "build-repacked",
        "--csv", str(catalogue), "--pointer-variants-csv", str(VARIANTS),
        "--move-labels-csv", str(MOVES), "--input-rom", str(BASE),
        "--output-rom", str(directory / "text.nes"),
        "--output-ips", str(directory / "text.ips"),
        "--fixed-overflow-output", str(directory / "overflow.csv"),
        "--allocation-output", str(directory / "allocation.csv"),
        "--bank-budget-output", str(directory / "budget.csv"),
    ]
    return subprocess.run(arguments, cwd=ROOT, capture_output=True, text=True,
                          timeout=90, env={**os.environ, "PYTHONHASHSEED": seed,
                                           "PYTHONDONTWRITEBYTECODE": "1"})


@unittest.skipUnless(BASE.is_file(), "supply the canonical English 2015 ROM")
class EnglishRepackedSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="nj046-en-safety-")
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.first = cls.root / "first"
        result = build_at(cls.first)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.base = BASE.read_bytes()
        cls.candidate = (cls.first / "text.nes").read_bytes()
        cls.allocations = read_rows(cls.first / "allocation.csv")
        cls.manifest = build_manifest(
            rom_path=cls.first / "text.nes", catalogue_path=CATALOG,
            variants_path=VARIANTS, inventory_path=INVENTORY, move_labels_path=MOVES)

    def test_exact_rebuild_and_python_hash_seed_determinism(self):
        for seed in ("777", "random"):
            directory = self.root / seed
            result = build_at(directory, seed=seed)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for name in ("text.nes", "text.ips", "allocation.csv", "budget.csv"):
                self.assertEqual((self.first / name).read_bytes(),
                                 (directory / name).read_bytes(), name)

    def test_bank_tails_font_and_overflow_remain_safe(self):
        self.assertEqual(len(self.candidate), len(self.base))
        for pair in (6, 7):
            start, end = builder.protected_bank_tail(pair)
            self.assertEqual(self.candidate[start:end], self.base[start:end])
        self.assertEqual(self.candidate[0x078210:0x078810],
                         self.base[0x078210:0x078810])
        self.assertEqual(read_rows(self.first / "overflow.csv"), [])
        validate_budget(self.first / "allocation.csv", self.first / "budget.csv",
                        DEFAULT_POLICY)

    def test_allocations_avoid_table_holes_tails_and_neutral_glyphs(self):
        glyphs = builder.verified_all_graphical_text_records(self.base)
        main = {int(row["source_offset_or_pointer"], 16)
                for row in read_rows(CATALOG) if row["record_type"] == "MAIN"}
        protected = list(TABLE_HOLES)
        protected.extend(builder.protected_bank_tail(pair) for pair in (6, 7))
        protected.extend((start, end) for start, end, _, _ in glyphs if start not in main)
        for row in self.allocations:
            start = int(row["target_offset_hex"], 16)
            end = start + int(row["terminated_bytes"])
            self.assertEqual(row["source_pair"], row["target_pair"])
            self.assertEqual(builder.pair_for_offset(start), builder.pair_for_offset(end-1))
            self.assertEqual(self.candidate[end-1], 0x0D)
            for left, right in protected:
                self.assertFalse(start < right and end > left, (row["stable_key"], hex(left)))
        for left, right in protected[len(TABLE_HOLES):]:
            self.assertEqual(self.candidate[left:right], self.base[left:right])

    def test_all_live_pointers_and_restorations_have_reviewed_owners(self):
        records = self.manifest["records"]
        self.assertEqual(len(records), 1912)
        refs = {int(row["reference"], 16) for row in records}
        self.assertEqual(len(refs), 1912)
        self.assertTrue(FALSE_REFS.isdisjoint(refs))
        self.assertEqual(sum(row["kind"] == "restoration" for row in records), 85)
        self.assertEqual(sum(row["record_type"] == "RESTORED" for row in self.allocations), 85)
        self.assertEqual(sum(row["record_type"] == "POINTER_VARIANT" for row in self.allocations), 4)

    def test_mutated_tail_is_rejected_by_exact_validator(self):
        changed = bytearray(self.candidate)
        changed[builder.protected_bank_tail(6)[0]] ^= 1
        candidate = self.root / "mutated.nes"
        candidate.write_bytes(changed)
        with self.assertRaisesRegex(EnglishRepackedError, "differs from exact rebuild"):
            validate_candidate(candidate_path=candidate, base_path=BASE,
                               catalogue_path=CATALOG, variants_path=VARIANTS,
                               move_labels_path=MOVES)

    def test_oversized_translation_fails_without_artifacts(self):
        rows = read_rows(CATALOG)
        row = next(r for r in rows if r["stable_key"] == "MAIN:0x03041D")
        row["english_v2"] = "A" * 65536
        row["layout"] = "raw"
        path = self.root / "oversized.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        destination = self.root / "rejected"
        result = build_at(destination, catalogue=path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(destination.iterdir()), [], result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
