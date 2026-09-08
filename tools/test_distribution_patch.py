"""Distribution reconstructs the French release directly from Chinese."""
import hashlib
from pathlib import Path
import unittest
from tools import build_french_release as builder
from tools.rom_builder import parse_ips, apply_ips, make_ips

ROOT = Path(__file__).resolve().parent.parent
CHINESE = ROOT / "Lei Dian Huang Bi Ka Qiu Chuan Shuo (NJ046) (Ch) [!].nes"
ENGLISH = ROOT / "Pokemon Yellow English 9-23-2015.nes"
RELEASE = ROOT / "releases/fr/2.0.13"
PATCH = RELEASE / "Pokemon_Jaune_NJ046_FR_v2.0.13.ips"
ROM_SHA = "2846fac5738ad24bc65dd1c24622fe4a1e9fffe94062052e84bfbae1cd34fae3"
IPS_SHA = "c05525ad4bbc628f5f97c9005ff85751236be282913ce835d25d350f6dccec0c"
SOURCE_SHA = "450d40c0d648f8651ac6b42f1c094921cb2202ed420194e65271e2f7b40c65ed"

class DistributionTests(unittest.TestCase):
    def test_patch_structure_and_checksum_without_rom(self):
        records, truncate = parse_ips(PATCH)
        self.assertTrue(records)
        self.assertIsNone(truncate)
        self.assertEqual(hashlib.sha256(PATCH.read_bytes()).hexdigest(), IPS_SHA)
        self.assertEqual((RELEASE / "VERSION").read_text().strip(), "2.0.13")
        self.assertEqual((RELEASE / "SHA256SUMS").read_text().strip(), IPS_SHA + "  " + PATCH.name)

    def test_only_two_source_roms_are_needed(self):
        self.assertEqual(len(builder.DEFAULT_ROMS), 2)
        self.assertEqual(set(builder.DEFAULT_ROMS.values()), {CHINESE, ENGLISH})

    @unittest.skipUnless(CHINESE.is_file(), "Original Chinese ROM not supplied")
    def test_only_version_tiles_change_from_2_0_12(self):
        source = CHINESE.read_bytes()
        previous = ROOT / "releases/fr/2.0.12/Pokemon_Jaune_NJ046_FR_v2.0.12.ips"
        old = apply_ips(source, *parse_ips(previous))
        new = apply_ips(source, *parse_ips(PATCH))
        self.assertEqual(hashlib.sha256(old).hexdigest(),
                         "efc7ba0837a65d06e0658348d3debaa1194b9cf03b59492a1a8d4dfab346327e")
        changed = {i for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(len(old), len(new))
        self.assertEqual(len(changed), 73)
        self.assertTrue(changed <= set(range(0x07150B, 0x07155B)))
        self.assertEqual(new[0x07150B:0x07155B], bytes.fromhex(
            "0053525257222300ffacadada8dd54770063545663515600f79caba99caea9ff"
            "0049555555554900ffb6aaaaaaaab6ff0020a0a060602000f8d858589898d8f8"
            "0f030000000000001c07010000000000"))

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
