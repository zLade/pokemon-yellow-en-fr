#!/usr/bin/env python3
"""Static contracts for the PowerShell Mesen scenario runner."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tools" / "run-mesen-pokemon-scenario.ps1"


class MesenScenarioRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = RUNNER_PATH.read_text(encoding="utf-8")

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
