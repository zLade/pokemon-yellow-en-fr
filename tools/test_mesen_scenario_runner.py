from __future__ import annotations
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER_PATH = ROOT / "tools/run-mesen-pokemon-scenario.ps1"

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
                    f"Missing local Lua dependency: {candidate}"
                )
            seen.add(candidate)
            dependencies.add(candidate)
            pending.append(candidate)
    return dependencies

class MesenScenarioRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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

    def test_expected_marker_is_recorded_before_process_stop(self) -> None:
        marker = "$ExpectedMarkerObserved = $true"
        marker_index = self.runner.index(marker)
        stop_index = self.runner.index(
            "Stop-Process -Id $Process.Id -Force", marker_index
        )
        self.assertLess(marker_index, stop_index)

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

    def test_targeted_probe_dependency_sets_are_complete(self) -> None:
        for script in (ROOT / "tools").glob("mesen_*.lua"):
            with self.subTest(script=script.name):
                local_lua_dependencies(script)

if __name__ == "__main__":
    unittest.main()
