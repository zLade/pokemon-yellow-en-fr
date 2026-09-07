#!/usr/bin/env python3

from __future__ import annotations

import unittest

from tools.validate_branch_separation import PROFILES, validate


class BranchSeparationTests(unittest.TestCase):
    def fixture(self, language: str) -> set[str]:
        return set(PROFILES[language]["required"]) | {"README.md"}

    def test_english_layout_passes(self) -> None:
        self.assertEqual(validate("en", self.fixture("en")), [])

    def test_crossed_release_is_rejected(self) -> None:
        files = self.fixture("en") | {"releases/fr/2.0.1/game.ips"}
        self.assertTrue(any("foreign-language" in item for item in validate("en", files)))

    def test_complete_rom_is_rejected(self) -> None:
        files = self.fixture("en") | {"private/game.nes"}
        self.assertTrue(any("complete ROM" in item for item in validate("en", files)))

    def test_french_only_documentation_is_rejected_on_english(self) -> None:
        files = self.fixture("en") | {"MODE_EMPLOI_TRADUCTION.md"}
        self.assertTrue(
            any("French-only documentation" in item for item in validate("en", files))
        )


if __name__ == "__main__":
    unittest.main()
