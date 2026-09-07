"""Distribution must reconstruct the unchanged game directly from Chinese."""
import hashlib
from pathlib import Path
import unittest
from tools import build_english_release as builder
from tools.rom_builder import parse_ips, apply_ips, make_ips

ROOT = Path(__file__).resolve().parent.parent
CHINESE = ROOT / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
ENGLISH = ROOT / "Pokemon Yellow English 9-23-2015.nes"
RELEASE = ROOT / "releases/en/2.0.3"
PATCH = RELEASE / "Pokemon_Yellow_NJ046_EN_v2.0.3.ips"
ROM_SHA = "703662c3739884513bf6493b748743eff0933b2479dc21644433699891f9d0f3"
IPS_SHA = "6f42637770fd4fc4971ef90d156d6f5959bb88e546122e2747b6b34c8cd168da"
SOURCE_SHA = "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed"

class DistributionTests(unittest.TestCase):
    def test_patch_structure_and_checksum_without_rom(self):
        records, truncate = parse_ips(PATCH)
        self.assertTrue(records)
        self.assertIsNone(truncate)
        self.assertEqual(hashlib.sha256(PATCH.read_bytes()).hexdigest(), IPS_SHA)
        self.assertEqual((RELEASE / "VERSION").read_text().strip(), "2.0.3")
        self.assertEqual((RELEASE / "SHA256SUMS").read_text().strip(), IPS_SHA + "  " + PATCH.name)

    def test_only_two_source_roms_are_needed(self):
        self.assertEqual(len(builder.DEFAULT_ROMS), 2)
        self.assertEqual(set(builder.DEFAULT_ROMS.values()), {CHINESE, ENGLISH})

    @unittest.skipUnless(CHINESE.is_file(), "Original Chinese ROM not supplied")
    def test_original_chinese_reconstructs_exact_game(self):
        original = CHINESE.read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), SOURCE_SHA)
        records, truncate = parse_ips(PATCH)
        result = apply_ips(original, records, truncate)
        self.assertEqual(len(result), 2097168)
        self.assertEqual(hashlib.sha256(result).hexdigest(), ROM_SHA)
        self.assertEqual(make_ips(original, result), PATCH.read_bytes())

    @unittest.skipUnless(ENGLISH.is_file(), "2015 technical ROM not supplied")
    def test_intermediate_translation_is_not_the_application_base(self):
        records, truncate = parse_ips(PATCH)
        wrong_result = apply_ips(ENGLISH.read_bytes(), records, truncate)
        self.assertNotEqual(hashlib.sha256(wrong_result).hexdigest(), ROM_SHA)
