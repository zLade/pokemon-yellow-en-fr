#!/usr/bin/env python3
"""Static contracts for the assisted critical-restoration runtime harness."""

from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path

from tools.prepare_critical_restoration_runtime import CASES


TOOLS = Path(__file__).resolve().parent
RUNTIME_PATH = TOOLS / "critical_restoration_runtime.lua"
PAIR6_PATH = TOOLS / "mesen_critical_restorations_pair6_probe.lua"
PAIR7_PATH = TOOLS / "mesen_critical_restorations_pair7_probe.lua"
SUITE_PATH = TOOLS / "run-mesen-english-regression-suite.ps1"
ASSISTED_MODE = "assisted_transient_prg_pointer_patch"


class CriticalRestorationRuntimeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        cls.pair6 = PAIR6_PATH.read_text(encoding="utf-8")
        cls.pair7 = PAIR7_PATH.read_text(encoding="utf-8")
        cls.suite = SUITE_PATH.read_text(encoding="utf-8")

    def test_target_map_has_exact_pair_group_counts(self) -> None:
        self.assertEqual(
            Counter(group for group, _key, _reference in CASES),
            {"pair6": 3, "pair7": 4},
        )

    def test_pair_probes_pin_markers_groups_counts_and_restore_calls(self) -> None:
        expectations = (
            (
                "pair6",
                self.pair6,
                3,
                "POKEMON_CRITICAL_RESTORATIONS_PAIR6_PASS",
                2,
            ),
            (
                "pair7",
                self.pair7,
                4,
                "POKEMON_CRITICAL_RESTORATIONS_PAIR7_PASS",
                1,
            ),
        )
        for group, source, count, marker, minimum_restores in expectations:
            with self.subTest(group=group):
                self.assertRegex(
                    source,
                    rf"Runtime\.new\(\{{group = \"{group}\", "
                    rf"expectedCount = {count}\}}\)",
                )
                self.assertIn(marker, source)
                self.assertIn(f"payloads={count}", source)
                self.assertIn(ASSISTED_MODE, source)
                self.assertGreaterEqual(
                    len(re.findall(r"\bruntime:restore\(\)", source)),
                    minimum_restores,
                )

    def test_runtime_writes_loaded_prg_only_and_never_game_ram(self) -> None:
        harness_sources = self.runtime + self.pair6 + self.pair7
        self.assertNotIn("emu.memType.nesDebug", harness_sources)
        self.assertNotIn("emu.write", self.pair6)
        self.assertNotIn("emu.write", self.pair7)

        write_calls = re.findall(
            r"emu\.write\s*\((.*?)\)",
            self.runtime,
            flags=re.DOTALL,
        )
        self.assertEqual(len(write_calls), 1)
        self.assertIn("emu.memType.nesPrgRom", write_calls[0])
        self.assertNotRegex(
            write_calls[0],
            r"(?i)nesDebug|nesMemory|workRam|saveRam",
        )
        self.assertIn('"writes_to_game_ram=0"', self.runtime)

    def test_suite_wires_both_exact_assisted_scenarios(self) -> None:
        self.assertRegex(
            self.suite,
            r"\[string\]\$CriticalRestorationTargetsPath",
        )
        self.assertIn("$CriticalRestorationTargetsPath,", self.suite)
        scenarios = (
            (
                "09-critical-restorations-pair6-assisted",
                "CriticalPair6Probe",
                "POKEMON_CRITICAL_RESTORATIONS_PAIR6_PASS",
            ),
            (
                "10-critical-restorations-pair7-assisted",
                "CriticalPair7Probe",
                "POKEMON_CRITICAL_RESTORATIONS_PAIR7_PASS",
            ),
        )
        for name, probe, marker in scenarios:
            with self.subTest(scenario=name):
                self.assertRegex(
                    self.suite,
                    rf"@\(\s*'{re.escape(name)}'\s*,\s*\${probe}\s*,\s*"
                    rf"'{marker}'\s*,\s*\$CriticalRestorationTargetsPath\s*\)",
                )

    def test_assisted_qualification_is_explicitly_documented(self) -> None:
        self.assertIn("Shared assisted-runtime support", self.runtime)
        self.assertIn("Assisted renderer proof", self.pair6)
        self.assertIn("Assisted renderer proof", self.pair7)
        self.assertIn(
            "Critical restoration coverage uses an assisted transient "
            "loaded-PRG pointer patch.",
            self.suite,
        )
        self.assertIn(
            "Critical restoration qualification: assisted transient "
            "loaded-PRG ",
            self.suite,
        )
        self.assertIn("pointers restored; no game RAM writes", self.suite)


if __name__ == "__main__":
    unittest.main()
