from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / "run-mesen-english-regression-suite.ps1"


class EnglishMesenSuiteSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_candidate_hash_and_mapper_contract_are_mandatory(self) -> None:
        self.assertRegex(
            self.source,
            r"\[Parameter\(Mandatory = \$true\)\]\s*\[string\]"
            r"\$ExpectedRomSha256",
        )
        self.assertIn("$Mapper -ne 163", self.source)
        self.assertIn("$PrgBytes -ne 2097152", self.source)
        self.assertIn("$ChrBytes -ne 0", self.source)

    def test_all_regions_and_required_runtime_domains_are_present(self) -> None:
        self.assertIn("@('Dendy', 'Ntsc', 'Pal')", self.source)
        expected_markers = {
            "POKEMON_MESEN_PASS",
            "MAPPER163_PASS",
            "POKEMON_INTRO_PASS",
            "POKEMON_ENGLISH_INTRO_PROMPTS_PASS",
            "POKEMON_ENGLISH_CHARSET_PASS",
            "TITLE_YELLOW_VERSION_PASS",
            "POKEMON_PLAYER_MENU_EN_PASS",
            "POKEMON_CRITICAL_RESTORATIONS_PAIR6_PASS",
        }
        for marker in expected_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertIn("mesen_pokemon_intro_prompt_en_probe.lua", self.source)
        self.assertIn("Invoke-EnglishBattery -Region $Region", self.source)
        self.assertIn("en2-battery-isolation", self.source)
        self.assertIn(
            "assisted transient loaded-PRG pointer patch",
            self.source,
        )

    def test_no_french_only_probe_is_invoked(self) -> None:
        forbidden = (
            "mesen_intro_french_accents_probe.lua",
            "mesen_pokemon_intro_prompt_probe.lua",
            "mesen_player_menu_french_probe.lua",
            "mesen_title_en_menu_fr_probe.lua",
            "POKEMON_FRENCH_CHARSET",
            "POKEMON_PLAYER_MENU_FR",
        )
        for value in forbidden:
            with self.subTest(value=value):
                self.assertNotIn(value, self.source)

    def test_manifest_disclaims_full_campaign_and_exhaustive_runtime(self) -> None:
        self.assertIn("targeted checks only; no automated playthrough", self.source)
        self.assertIn(
            "controller/runtime evidence is not static ",
            self.source,
        )
        self.assertRegex(self.source, re.escape("Result: $Result"))

    def test_all_declared_probes_exist_and_no_bot_is_required(self) -> None:
        probes = re.findall(r"'([^']+\.lua)'", self.source)
        self.assertEqual(len(probes), 8)
        for name in probes:
            self.assertTrue((ROOT / name).is_file(), name)
        for obsolete in ("$CampaignProbe", "$Route1InputPath", "$CriticalPair7Probe", ".inputs.bin"):
            self.assertNotIn(obsolete, self.source)


if __name__ == "__main__":
    unittest.main()
