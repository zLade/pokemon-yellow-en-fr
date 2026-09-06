#!/usr/bin/env python3
"""Static contracts for the PowerShell Mesen scenario runner."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tools" / "run-mesen-pokemon-scenario.ps1"
REGRESSION_SUITE_PATH = (
    ROOT / "tools" / "run-mesen-pokemon-regression-suite.ps1"
)
CAMPAIGN_PATH = ROOT / "tools" / "campaign" / "mesen_campaign_prototype.lua"

LUA_DEPENDENCY_PATTERN = re.compile(
    r"""(?:loadModule|dofile|require)\s*\(\s*
        ["'](?P<path>[^"']+\.lua)["']\s*\)""",
    flags=re.IGNORECASE | re.VERBOSE,
)


def local_lua_dependencies(root_script: Path) -> set[Path]:
    pending = [root_script.resolve()]
    seen = {pending[0]}
    dependencies: set[Path] = set()
    while pending:
        current = pending.pop()
        source = current.read_text(encoding="utf-8")
        for match in LUA_DEPENDENCY_PATTERN.finditer(source):
            candidate = Path(match.group("path"))
            if not candidate.is_absolute():
                candidate = current.parent / candidate
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            if not candidate.is_file():
                raise AssertionError(
                    f"dépendance Lua locale absente : {candidate}"
                )
            seen.add(candidate)
            dependencies.add(candidate)
            pending.append(candidate)
    return dependencies


class MesenScenarioRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = RUNNER_PATH.read_text(encoding="utf-8")
        cls.regression_suite = REGRESSION_SUITE_PATH.read_text(
            encoding="utf-8"
        )

    def test_manifest_is_written_before_failure_is_rethrown(self) -> None:
        manifest_write = self.runner.index(
            "Set-Content -LiteralPath $ManifestPath -Encoding UTF8"
        )
        failure_branch = self.runner.index(
            "if ($ScenarioResult -ne 'PASS')"
        )
        self.assertLess(manifest_write, failure_branch)
        self.assertIn("} catch {", self.runner)
        self.assertIn("$CapturedError = $_", self.runner)
        self.assertIn("throw $CapturedError", self.runner)
        self.assertIn('"Result: $ScenarioResult"', self.runner)
        self.assertIn(
            '"Failure $($Index + 1): $($FailureMessages[$Index])"',
            self.runner,
        )

    def test_manifest_records_process_and_timeout_outcome(self) -> None:
        required = (
            '"Mesen process exit code: $ProcessExitCode"',
            '"Timed out: $([bool]$TimedOut)"',
            '"Expected marker observed: $([bool]$ExpectedMarkerObserved)"',
            (
                '"Expected effective region observed: '
                '$ExpectedRegionObservation"'
            ),
            '"Mesen stdout SHA-256: $StdoutHash"',
            '"Mesen stderr SHA-256: $StderrHash"',
            '"Mesen terminal output: $TerminalOutput"',
            "$ScenarioResult = if ($FailureMessages.Count -eq 0)",
        )
        for snippet in required:
            self.assertIn(snippet, self.runner)

    def test_mesen_timeout_uses_the_supported_equals_switch(self) -> None:
        self.assertIn(
            "('--timeout={0}' -f $TimeoutSeconds)",
            self.runner,
        )
        self.assertNotIn("'--testRunnerTimeout'", self.runner)
        self.assertNotIn("'--luaScript'", self.runner)
        self.assertIn(
            '"Mesen test-runner timeout seconds: $TimeoutSeconds"',
            self.runner,
        )

    def test_lua_source_and_modules_are_hashed_before_and_after(self) -> None:
        required = (
            "Get-LocalLuaDependencyPaths",
            "(?:loadModule|dofile|require)",
            '"Lua scenario SHA-256 before: $LuaScriptHashBefore"',
            '"Lua scenario SHA-256 after: $LuaScriptHashAfter"',
            '"Lua local module count: $($LuaModules.Count)"',
            '"Lua local module $Number path: $($Module.Path)"',
            (
                '"Lua local module $Number SHA-256 before: '
                '$($Module.HashBefore)"'
            ),
            (
                '"Lua local module $Number SHA-256 after: '
                '$($Module.HashAfter)"'
            ),
            "Lua scenario changed during Mesen scenario:",
            "Lua module changed during Mesen scenario:",
        )
        for snippet in required:
            self.assertIn(snippet, self.runner)

    def test_campaign_dependency_set_is_complete(self) -> None:
        dependencies = local_lua_dependencies(CAMPAIGN_PATH)
        self.assertEqual(
            {path.name for path in dependencies},
            {
                "engine.lua",
                "input_queue.lua",
                "memory_guard.lua",
                "ram_map.lua",
            },
        )

    def test_static_contract_runs_inside_the_full_regression_suite(self) -> None:
        for snippet in (
            "Get-ChildItem",
            "-Filter 'test_*.py'",
            "'discover'",
            "'-s'",
            "'tools'",
            "'-p'",
            "'test_*.py'",
            "'static/full-python-test-suite'",
        ):
            self.assertIn(snippet, self.regression_suite)

    def test_completion_gate_bootstrap_is_scoped_to_test_discovery(self) -> None:
        self.assertIn(
            "[switch]$BootstrapCompletionGate",
            self.regression_suite,
        )
        self.assertIn(
            "@('env', 'POKEMON_MESEN_BOOTSTRAP=1', 'python3')",
            self.regression_suite,
        )
        self.assertEqual(
            self.regression_suite.count("POKEMON_MESEN_BOOTSTRAP=1"),
            1,
        )
        discovery_start = self.regression_suite.index(
            "Invoke-RegressionStep -Name 'static/full-python-test-suite'"
        )
        discovery_end = self.regression_suite.index(
            "Invoke-RegressionStep",
            discovery_start + 1,
        )
        discovery_block = self.regression_suite[
            discovery_start:discovery_end
        ]
        self.assertIn(
            "-BootstrapCompletionGateEnvironment:$BootstrapCompletionGate",
            discovery_block,
        )
        self.assertIn(
            '"Bootstrap completion gate: $([bool]$BootstrapCompletionGate)"',
            self.regression_suite,
        )

    def test_full_suite_passes_canonical_csv_to_static_validators(self) -> None:
        self.assertIn(
            "$script:LinuxCanonicalCsvPath = Convert-ToWslPath",
            self.regression_suite,
        )
        for validator in (
            "tools/audit_quality_ambitious.py",
            "tools/validate_repacked.py",
            "tools/audit_translation_coverage.py",
        ):
            start = self.regression_suite.index(validator)
            next_step = self.regression_suite.find(
                "Invoke-RegressionStep",
                start,
            )
            block = self.regression_suite[
                start:next_step if next_step >= 0 else None
            ]
            self.assertIn("'--csv'", block, validator)
            self.assertIn("$script:LinuxCanonicalCsvPath", block, validator)

    def test_campaign_gallery_is_kept_per_region(self) -> None:
        for snippet in (
            "'campaign\\mesen_campaign_prototype.lua'",
            '"mesen/$TestRegion/campaign-prototype"',
            "'07-campaign-prototype'",
            "'POKEMON_CAMPAIGN_PROTOTYPE_PASS'",
        ):
            self.assertIn(snippet, self.regression_suite)

    def test_route1_fm3_is_explicitly_opt_in_and_input_hashed(self) -> None:
        for snippet in (
            "$IncludeExperimentalRoute1Viridian",
            "'mesen_fm3_route1_viridian_after_prototype.lua'",
            "'POKEMON_FM3_ROUTE1_VIRIDIAN_TRACE_PASS'",
            "Get-LowerSha256 -Path $Route1InputPath",
            "its FM3 stream was frozen",
            "transient ",
            "blank screenshots",
            "route-alignment timeouts",
        ):
            self.assertIn(snippet, self.regression_suite)


if __name__ == "__main__":
    unittest.main()
