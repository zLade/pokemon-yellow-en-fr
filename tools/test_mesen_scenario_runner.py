#!/usr/bin/env python3
"""Static contracts for the PowerShell Mesen scenario runner."""

from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "tools" / "run-mesen-pokemon-scenario.ps1"
REGRESSION_SUITE_PATH = (
    ROOT / "tools" / "run-mesen-pokemon-regression-suite.ps1"
)
EXPLORER_PROFILE_RUNNER_PATH = ROOT / "tools" / "run_mesen_explorer_profile.ps1"
PROFILE_SCAN_PATH = ROOT / "tools" / "scan_explorer_profiles.ps1"
ARTIFACT_VERIFIER_PATH = ROOT / "tools" / "verify_explorer_artifacts.py"
SMOKE_TEST_PATH = ROOT / "tools" / "test_explorer_smoke.ps1"
ADAPTIVE_RUNNER_PATH = ROOT / "tools" / "run_adaptive_dojo_explorer.ps1"
COMPARATOR_PATH = ROOT / "tools" / "compare_explorer_runs.py"
FRONTIER_ANALYZER_PATH = ROOT / "tools" / "analyze_explorer_frontier.py"
FRONTIER_CYCLE_PATH = ROOT / "tools" / "run_frontier_cycle.ps1"
FRONTIER_CAMPAIGN_PATH = ROOT / "tools" / "run_frontier_campaign.ps1"
MENU_TIMEOUT_PROFILE_PATH = ROOT / "tools" / "campaign" / "menu_timeout_smoke_profile.txt"
ALTERNATE_BATTLE_PROFILE_PATH = ROOT / "tools" / "campaign" / "battle_action_alternate_smoke_profile.txt"
STORY_PROGRESS_PROFILE_PATH = ROOT / "tools" / "campaign" / "story_progress_battle_profile.txt"
ALTERNATE_BATTLE_RUNNER_PATH = ROOT / "tools" / "run_alternate_battle_smoke.ps1"
EXPLORER_LUA_PATH = ROOT / "tools" / "mesen_campaign_explorer.lua"
ROUTE_BOT_LUA_PATH = ROOT / "tools" / "mesen_route_bot.lua"
ADAPTIVE_PROFILE_PATH = ROOT / "tools" / "campaign" / "explorer_adaptive_dojo_profile.txt"
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
        cls.explorer_profile_runner = EXPLORER_PROFILE_RUNNER_PATH.read_text(
            encoding="utf-8"
        )
        cls.profile_scan = PROFILE_SCAN_PATH.read_text(encoding="utf-8")
        cls.artifact_verifier = ARTIFACT_VERIFIER_PATH.read_text(encoding="utf-8")
        cls.smoke_test = SMOKE_TEST_PATH.read_text(encoding="utf-8")
        cls.adaptive_runner = ADAPTIVE_RUNNER_PATH.read_text(encoding="utf-8")
        cls.comparator = COMPARATOR_PATH.read_text(encoding="utf-8")
        cls.frontier_analyzer = FRONTIER_ANALYZER_PATH.read_text(encoding="utf-8")
        cls.frontier_cycle = FRONTIER_CYCLE_PATH.read_text(encoding="utf-8")
        cls.frontier_campaign = FRONTIER_CAMPAIGN_PATH.read_text(encoding="utf-8")
        cls.menu_timeout_profile = MENU_TIMEOUT_PROFILE_PATH.read_text(encoding="utf-8")
        cls.alternate_battle_profile = ALTERNATE_BATTLE_PROFILE_PATH.read_text(encoding="utf-8")
        cls.story_progress_profile = STORY_PROGRESS_PROFILE_PATH.read_text(encoding="utf-8")
        cls.alternate_battle_runner = ALTERNATE_BATTLE_RUNNER_PATH.read_text(encoding="utf-8")
        cls.explorer_lua = EXPLORER_LUA_PATH.read_text(encoding="utf-8")
        cls.route_bot_lua = ROUTE_BOT_LUA_PATH.read_text(encoding="utf-8")

    def test_route_bot_uses_ram_guided_topology(self) -> None:
        for contract in (
            'POKEMON_ROUTE_X_ADDR", 0x0304',
            'POKEMON_ROUTE_Y_ADDR", 0x0306',
            'POKEMON_ROUTE_MAP_RAM_START", 0x0308',
            "local function nodeKey",
            "local function chooseDirection",
            'result = transitioned and "transition"',
            "route_bot_edges.tsv",
            "route_bot_ram_probe.tsv",
        ):
            self.assertIn(contract, self.route_bot_lua)
        self.assertNotIn("frame < start + 1500", self.route_bot_lua)
        self.assertNotIn("frame < start + 3000", self.route_bot_lua)

    def test_route_bot_battle_detector_is_stable_and_configurable(self) -> None:
        for contract in (
            "POKEMON_ROUTE_BATTLE_ADDR",
            "POKEMON_ROUTE_BATTLE_MASK",
            "POKEMON_ROUTE_BATTLE_VALUE",
            "BATTLE_CONFIRM",
            "BATTLE_RELEASE",
            "battleCandidateFrames",
            "battleReleaseFrames",
            "battles_completed",
            "pc_stationary_fallback",
        ):
            self.assertIn(contract, self.route_bot_lua)

    def test_explorer_profile_forwards_configurable_timeout(self) -> None:
        self.assertIn("[int]$TimeoutSeconds = 1800", self.explorer_profile_runner)
        self.assertIn("-TimeoutSeconds $TimeoutSeconds", self.explorer_profile_runner)
        self.assertIn("TimeoutSeconds must be at least 5", self.explorer_profile_runner)
        self.assertIn("[string]$MesenPath = ''", self.explorer_profile_runner)
        self.assertIn("-MesenPath $MesenPath", self.explorer_profile_runner)

    def test_frontier_campaign_propagates_interior_stop(self) -> None:
        self.assertIn("[switch]$StopOnInterior", self.frontier_campaign)
        self.assertIn("-StopOnInterior:$StopOnInterior", self.frontier_campaign)
        self.assertIn("[switch]$StopOnInterior", self.frontier_cycle)
        self.assertIn("POKEMON_EXPLORER_STOP_ON_INTERIOR=1", self.frontier_cycle)
        self.assertIn("[switch]$StopOnMenuTimeout", self.frontier_campaign)
        self.assertIn("-StopOnMenuTimeout:$StopOnMenuTimeout", self.frontier_campaign)
        self.assertIn("$BattleAlternateButton", self.frontier_campaign)
        self.assertIn("-BattlePeriod $BattlePeriod", self.frontier_campaign)
        self.assertIn("[switch]$StopOnMenuTimeout", self.frontier_cycle)
        self.assertIn("POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1", self.frontier_cycle)
        self.assertIn("$BattleAlternateButton", self.frontier_cycle)
        self.assertIn("--battle-alternate-button", self.frontier_cycle)
        self.assertIn("--battle-period", self.frontier_cycle)
        self.assertIn("$terminationReason -eq 'menu-timeout'", self.frontier_campaign)
        self.assertIn("$terminationPath = Join-Path $cycleDir", self.frontier_campaign)
        self.assertLess(
            self.frontier_campaign.index("$terminationReason -eq 'menu-timeout'"),
            self.frontier_campaign.index("$StopOnNoGrowth -and $previousMaps"),
        )
        self.assertIn("menu-timeout`t", self.frontier_campaign)

    def test_frontier_campaign_supports_resume_without_overwriting_history(self) -> None:
        self.assertIn("[switch]$Resume", self.frontier_campaign)
        self.assertIn("if (-not $Resume -or -not (Test-Path -LiteralPath $history", self.frontier_campaign)
        self.assertIn("$startCycle", self.frontier_campaign)
        self.assertIn("$cycle -lt ($startCycle + $MaxCycles)", self.frontier_campaign)
        self.assertIn("$latestFrontier", self.frontier_campaign)
        self.assertIn("exploration_frontier.tsv", self.frontier_campaign)
        self.assertIn("[int]$Matches[1]", self.frontier_campaign)
        self.assertIn("failed-missing-summary", self.frontier_campaign)
        self.assertIn("$previousMaps = [int]$historyFields[3]", self.frontier_campaign)

    def test_explorer_profile_records_reproducibility_manifest(self) -> None:
        for field in (
            "rom_sha256",
            "input_sha256",
            "script_sha256",
            "profile_sha256",
            "timeout_seconds",
            "explorer_run_manifest.tsv",
        ):
            self.assertIn(field, self.explorer_profile_runner)

    def test_profile_scan_uses_explorer_runner(self) -> None:
        self.assertIn("run_mesen_explorer_profile.ps1", self.profile_scan)
        self.assertIn("-ProfilePath $profile", self.profile_scan)
        self.assertNotIn("-ScriptPath", self.profile_scan)
        self.assertIn("$runError = $null", self.profile_scan)
        self.assertIn("failed", self.profile_scan)
        self.assertIn("$runStarted = Get-Date", self.profile_scan)
        self.assertIn("termination_reason", self.profile_scan)
        self.assertIn("direction_seed", self.profile_scan)
        self.assertIn("'interior' { 3; break }", self.profile_scan)
        self.assertIn("'battle' { 2; break }", self.profile_scan)
        self.assertIn("menu-timeout", self.profile_scan)
        self.assertIn("[int]$TimeoutSeconds = 120", self.profile_scan)
        self.assertIn("-TimeoutSeconds $TimeoutSeconds", self.profile_scan)
        self.assertIn("[int]$DirectionSeed = 0", self.profile_scan)
        self.assertIn("$BattleAlternateButton", self.profile_scan)
        self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_PERIOD", self.profile_scan)
        self.assertIn("POKEMON_EXPLORER_DIRECTION_SEED=' + $DirectionSeed", self.profile_scan)
        self.assertIn("POKEMON_EXPLORER_DIRECTION_SEED=' + $best.direction_seed", self.profile_scan)
        self.assertIn("[switch]$CaptureAllTransitions", self.profile_scan)
        self.assertIn("[switch]$TracePc", self.profile_scan)
        self.assertIn("[switch]$StopOnBattle", self.profile_scan)
        self.assertIn("[switch]$StopOnInterior", self.profile_scan)
        self.assertIn("[switch]$StopOnMenuTimeout", self.profile_scan)

    def test_artifact_verifier_checks_checkpoint_and_manifest(self) -> None:
        self.assertIn("exploration_checkpoint.tsv", self.artifact_verifier)
        self.assertIn("explorer_run_manifest.tsv", self.artifact_verifier)
        self.assertIn("script_sha256", self.artifact_verifier)
        self.assertIn(r"[0-9A-Fa-f]{64}", self.artifact_verifier)
        self.assertIn("interior_stop.tsv", self.artifact_verifier)
        self.assertIn("summary invalid integer: direction_seed", self.artifact_verifier)
        self.assertIn("direction_seed={values['direction_seed']}", self.artifact_verifier)
        self.assertIn("summary incomplete menu recovery configuration", self.artifact_verifier)
        self.assertIn("menu_recovery_timeout.tsv", self.artifact_verifier)
        self.assertIn("menu_recovery_timed_out", self.artifact_verifier)
        self.assertIn("menu_timed_out", self.artifact_verifier)
        self.assertIn("menu_timeout_screen.png missing", self.artifact_verifier)
        self.assertIn("st_size == 0", self.artifact_verifier)
        self.assertIn("termination_reason.tsv", self.artifact_verifier)
        self.assertIn("battle_config.tsv", self.artifact_verifier)
        self.assertIn("0xFF", self.artifact_verifier)
        self.assertIn("alternate_button", self.artifact_verifier)
        self.assertIn("battle screenshot missing", self.artifact_verifier)
        self.assertIn("interior screenshot missing", self.artifact_verifier)

    def test_explorer_smoke_can_require_confirmed_interior(self) -> None:
        self.assertIn("[switch]$ExpectInterior", self.smoke_test)
        self.assertIn("interior_visual_seen", self.smoke_test)
        self.assertIn("interior_stop.tsv", self.smoke_test)
        self.assertIn("explorer_run_manifest.tsv", self.smoke_test)
        self.assertIn("battle_config.tsv", self.smoke_test)
        self.assertIn("[switch]$ExpectMenuTimeout", self.smoke_test)
        self.assertIn("menu-timeout", self.smoke_test)
        self.assertIn("menu_timeout_screen.png", self.smoke_test)
        self.assertIn("[switch]$ExpectAlternateBattle", self.smoke_test)
        self.assertIn("alternate_button", self.smoke_test)
        self.assertIn("$ExpectBattle -or $ExpectAlternateBattle", self.smoke_test)
        self.assertIn("stale summary", self.smoke_test)
        self.assertIn("[string]$MesenPath = ''", self.smoke_test)

    def test_menu_timeout_profile_enables_controlled_stop(self) -> None:
        self.assertIn("POKEMON_EXPLORER_MENU_HASH=0xAAD2FACE", self.menu_timeout_profile)
        self.assertIn("POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1", self.menu_timeout_profile)
        self.assertIn("POKEMON_EXPLORER_MENU_RECOVERY_MAX_FRAMES=60", self.menu_timeout_profile)

    def test_alternate_battle_profile_is_ready(self) -> None:
        self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_BUTTON=0x01", self.alternate_battle_profile)
        self.assertIn("POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON=0x02", self.alternate_battle_profile)
        self.assertIn("POKEMON_EXPLORER_STOP_ON_BATTLE=1", self.alternate_battle_profile)

    def test_story_progress_profile_continues_after_battle(self) -> None:
        self.assertIn("POKEMON_EXPLORER_STOP_ON_BATTLE=0", self.story_progress_profile)
        self.assertIn("POKEMON_EXPLORER_BATTLE_MAX_FRAMES=1800", self.story_progress_profile)
        self.assertIn("POKEMON_EXPLORER_BATTLE_COOLDOWN_FRAMES=240", self.story_progress_profile)
        self.assertIn("-ExpectAlternateBattle", self.alternate_battle_runner)
        self.assertIn("-MesenPath $MesenPath", self.alternate_battle_runner)
        self.assertIn("battle_action_alternate_smoke_profile.txt", self.alternate_battle_runner)
        self.assertIn("ValidateRange(5, 86400)", self.alternate_battle_runner)
        self.assertIn("[switch]$ValidateOnly", self.alternate_battle_runner)
        self.assertIn("alternate-battle-smoke=VALID", self.alternate_battle_runner)
        self.assertIn("secondary button", self.alternate_battle_runner)
        self.assertIn("primary button", self.alternate_battle_runner)
        self.assertIn("invalid action period", self.alternate_battle_runner)
        self.assertIn("invalid action hold", self.alternate_battle_runner)

    def test_adaptive_dojo_runner_checks_visual_interior(self) -> None:
        self.assertIn("explorer_adaptive_dojo_profile.txt", self.adaptive_runner)
        self.assertIn("interior_visual_seen", self.adaptive_runner)
        self.assertIn("adaptive-dojo=PASS", self.adaptive_runner)
        self.assertIn("stale summary", self.adaptive_runner)
        self.assertIn("termination_reason.tsv", self.adaptive_runner)
        self.assertIn("did not terminate on the confirmed interior", self.adaptive_runner)

    def test_run_comparator_reports_seed_and_actual_budget(self) -> None:
        self.assertIn('"direction_seed"', self.comparator)
        self.assertIn('"exploration_budget"', self.comparator)
        self.assertIn('"stagnation_resets"', self.comparator)
        self.assertIn("termination_reason", self.comparator)
        self.assertIn("invalid termination reason", self.comparator)
        self.assertIn("menu-timeout", self.comparator)

    def test_frontier_profiles_accept_direction_seed(self) -> None:
        self.assertIn('"--direction-seed"', self.frontier_analyzer)
        self.assertIn("POKEMON_EXPLORER_DIRECTION_SEED={args.direction_seed}", self.frontier_analyzer)
        self.assertIn("--battle-alternate-button", self.frontier_analyzer)
        self.assertIn("POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON", self.frontier_analyzer)
        self.assertIn("--battle-button", self.frontier_analyzer)
        self.assertIn("--battle-period", self.frontier_analyzer)
        self.assertIn("--battle-hold", self.frontier_analyzer)
        self.assertIn('"--menu-button"', self.frontier_analyzer)
        self.assertIn("POKEMON_EXPLORER_MENU_RECOVERY_BUTTON", self.frontier_analyzer)
        self.assertIn('"--menu-period"', self.frontier_analyzer)
        self.assertIn('"--max-frames"', self.frontier_analyzer)
        self.assertIn('"--stop-on-interior"', self.frontier_analyzer)
        self.assertIn('"--stop-on-menu-timeout"', self.frontier_analyzer)
        self.assertIn('"--stop-on-battle"', self.frontier_analyzer)
        self.assertIn('"--capture-all-transitions"', self.frontier_analyzer)
        self.assertIn('"--trace-pc"', self.frontier_analyzer)
        self.assertIn('"--checkpoint-period"', self.frontier_analyzer)

    def test_frontier_analyzer_emits_battle_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            profile = root / "profile.txt"
            frontier.write_text(
                "node\tremaining\nAABBCCDD:10:20\tright,left\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3", str(FRONTIER_ANALYZER_PATH), str(frontier),
                    "--write-profile", str(profile),
                    "--battle-button", "1",
                    "--battle-alternate-button", "2",
                    "--battle-period", "30",
                    "--battle-hold", "8",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = profile.read_text(encoding="utf-8")
            self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_BUTTON=0x01", generated)
            self.assertIn("POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON=0x02", generated)
            self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_PERIOD=30", generated)
            self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_HOLD=8", generated)

    def test_frontier_analyzer_clamps_battle_strategy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            profile = root / "profile.txt"
            frontier.write_text("node\tremaining\nAABBCCDD:10:20\tright\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier), "--write-profile", str(profile),
                 "--battle-button", "511", "--battle-alternate-button", "-4",
                 "--battle-period", "0", "--battle-hold", "-3"],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            generated = profile.read_text(encoding="utf-8")
            self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_BUTTON=0xFF", generated)
            self.assertIn("POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON=0x00", generated)
            self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_PERIOD=1", generated)
            self.assertIn("POKEMON_EXPLORER_BATTLE_ACTION_HOLD=0", generated)

    def test_frontier_analyzer_rejects_malformed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            frontier.write_text("node\tremaining\nnot-a-node\tright\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frontier invalid node", result.stderr)

    def test_frontier_analyzer_rejects_unknown_direction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            frontier.write_text("node\tremaining\nAABBCCDD:10:20\tteleport\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier), "--write-profile", str(root / "p.txt")],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frontier invalid direction", result.stderr)

    def test_frontier_analyzer_rejects_out_of_range_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            frontier.write_text("node\tremaining\nAABBCCDD:100:20\tright\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frontier coordinates out of range", result.stderr)

    def test_frontier_analyzer_rejects_out_of_range_map_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            frontier.write_text("node\tremaining\n100000000:10:20\tright\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frontier map hash out of range", result.stderr)

    def test_frontier_analyzer_keeps_exhausted_frontier_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frontier = Path(directory) / "frontier.tsv"
            frontier.write_text("node\tremaining\n", encoding="utf-8")
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)

    def test_frontier_analyzer_uses_selected_node_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            profile = root / "profile.txt"
            frontier.write_text(
                "node\tremaining\n11111111:10:10\tright\n22222222:80:80\tleft\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier), "--write-profile", str(profile)],
                check=False, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("POKEMON_EXPLORER_FRONTIER_PROBE_HASH=0x11111111", profile.read_text(encoding="utf-8"))

    def test_frontier_analyzer_validates_unselected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            frontier = Path(directory) / "frontier.tsv"
            frontier.write_text(
                "node\tremaining\n11111111:10:10\tright\n22222222:80:80\tunknown\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                ["python3", str(FRONTIER_ANALYZER_PATH), str(frontier)],
                check=False, capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frontier invalid direction", result.stderr)
        self.assertIn("POKEMON_EXPLORER_MAX_BUDGET={max(max(1, args.max_frames), args.max_budget)}", self.frontier_analyzer)
        self.assertIn("POKEMON_EXPLORER_MENU_RECOVERY_HOLD={max(0, args.menu_hold)}", self.frontier_analyzer)

    def test_frontier_analyzer_writes_seeded_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frontier = root / "frontier.tsv"
            profile = root / "profile.txt"
            frontier.write_text(
                "node\ttried\tremaining\n"
                "C3601464:80:70\tup\tright,down\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    "python3",
                    str(FRONTIER_ANALYZER_PATH),
                    str(frontier),
                    "--write-profile",
                    str(profile),
                    "--direction-seed",
                    "7",
                    "--menu-button",
                    "0x08",
                    "--menu-period",
                    "40",
                    "--menu-hold",
                    "5",
                    "--max-frames",
                    "12000",
                    "--max-budget",
                    "45000",
                    "--stop-on-interior",
                    "--stop-on-menu-timeout",
                    "--stop-on-battle",
                    "--capture-all-transitions",
                    "--trace-pc",
                    "--checkpoint-period",
                    "300",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            generated = profile.read_text(encoding="utf-8")
            self.assertIn("POKEMON_EXPLORER_DIRECTION_SEED=7", generated)
            self.assertIn("POKEMON_EXPLORER_MENU_RECOVERY_BUTTON=0x08", generated)
            self.assertIn("POKEMON_EXPLORER_MENU_RECOVERY_PERIOD=40", generated)
            self.assertIn("POKEMON_EXPLORER_MENU_RECOVERY_HOLD=5", generated)
            self.assertIn("POKEMON_EXPLORER_MAX_FRAMES=12000", generated)
            self.assertIn("POKEMON_EXPLORER_MAX_BUDGET=45000", generated)
            self.assertIn("POKEMON_EXPLORER_CHECKPOINT_PERIOD=300", generated)
            self.assertIn("POKEMON_EXPLORER_STOP_ON_INTERIOR=1", generated)
            self.assertIn("POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT=1", generated)
            self.assertIn("POKEMON_EXPLORER_STOP_ON_BATTLE=1", generated)
            self.assertIn("POKEMON_EXPLORER_CAPTURE_ALL_TRANSITIONS=1", generated)
            self.assertIn("POKEMON_EXPLORER_TRACE_PC=1", generated)

    def test_comparator_rejects_invalid_termination_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary_a = root / "a.tsv"
            summary_b = root / "b.tsv"
            minimal = "frames\t1\n"
            summary_a.write_text(minimal, encoding="utf-8")
            summary_b.write_text(minimal, encoding="utf-8")
            (root / "termination_reason.tsv").write_text(
                "reason\nunknown\n", encoding="utf-8"
            )
            result = subprocess.run(
                ["python3", str(COMPARATOR_PATH), str(summary_a), str(summary_b)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid termination reason", result.stderr)

    def test_explorer_battle_stop_has_duplicate_guard(self) -> None:
        self.assertIn('POKEMON_EXPLORER_STOP_ON_BATTLE', self.explorer_lua)
        self.assertIn('local battleStopTriggered = false', self.explorer_lua)
        self.assertIn('if not battleMode and not battleStopTriggered then', self.explorer_lua)

    def test_battle_stop_marks_interior_when_hash_matches(self) -> None:
        marker = 'if interiorConfirmHash ~= 0 and checksumNametable() == interiorConfirmHash then'
        start = self.explorer_lua.index(marker)
        summary = self.explorer_lua.index('writeSummary()', start)
        block = self.explorer_lua[start:summary]
        self.assertIn('buildingEntered = true', block)
        self.assertIn('interiorSeen = true', block)
        self.assertIn('interiorVisualSeen = true', block)

    def test_battle_action_cadence_is_profile_configurable(self) -> None:
        self.assertIn('POKEMON_EXPLORER_BATTLE_ACTION_PERIOD', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_BATTLE_ACTION_HOLD', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_BATTLE_ACTION_BUTTON', self.explorer_lua)
        self.assertIn('battleActionPeriod', self.explorer_lua)
        self.assertIn('battleFrame % battleActionPeriod', self.explorer_lua)
        self.assertIn('math.min(0xFF', self.explorer_lua)

    def test_battle_mode_has_configurable_timeout_and_resets(self) -> None:
        self.assertIn('POKEMON_EXPLORER_BATTLE_MAX_FRAMES', self.explorer_lua)
        self.assertIn('battleFrame = battleFrame + 1', self.explorer_lua)
        self.assertIn('logBattle("timeout"', self.explorer_lua)
        self.assertIn('battleFrame = 0', self.explorer_lua)

    def test_new_map_discovery_can_extend_bounded_exploration(self) -> None:
        self.assertIn('POKEMON_EXPLORER_EXTEND_ON_NEW_MAP', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_NEW_MAP_EXTENSION_FRAMES', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_MAX_BUDGET', self.explorer_lua)
        self.assertIn('budget_extensions.tsv', self.explorer_lua)
        self.assertIn('math.min(explorationMaxBudget', self.explorer_lua)

    def test_adaptive_dojo_profile_enables_bounded_extension(self) -> None:
        profile = ADAPTIVE_PROFILE_PATH.read_text(encoding="utf-8")
        self.assertIn("POKEMON_EXPLORER_EXTEND_ON_NEW_MAP=1", profile)
        self.assertIn("POKEMON_EXPLORER_MAX_BUDGET=60000", profile)
        self.assertIn("POKEMON_EXPLORER_INTERIOR_CONFIRM_HASH=0x9BA474C0", profile)
        self.assertIn("POKEMON_EXPLORER_STOP_ON_INTERIOR=1", profile)

    def test_exploration_persists_periodic_frontier_checkpoints(self) -> None:
        self.assertIn('POKEMON_EXPLORER_CHECKPOINT_PERIOD', self.explorer_lua)
        self.assertIn('exploration_checkpoint.tsv', self.explorer_lua)
        self.assertIn('writeGraph()', self.explorer_lua)
        self.assertIn('writeFrontier()', self.explorer_lua)

    def test_explorer_can_stop_on_confirmed_interior(self) -> None:
        self.assertIn('POKEMON_EXPLORER_STOP_ON_INTERIOR', self.explorer_lua)
        self.assertIn('POKEMON_CAMPAIGN_EXPLORER_INTERIOR_PASS', self.explorer_lua)
        self.assertIn('emu.stop(0)', self.explorer_lua)

    def test_battle_detector_has_reentry_cooldown(self) -> None:
        self.assertIn('POKEMON_EXPLORER_BATTLE_COOLDOWN_FRAMES', self.explorer_lua)
        self.assertIn('battleCooldown = battleCooldownLength', self.explorer_lua)
        self.assertIn('battleCooldown == 0', self.explorer_lua)

    def test_battle_actions_can_alternate_buttons(self) -> None:
        self.assertIn('POKEMON_EXPLORER_BATTLE_ALTERNATE_BUTTON', self.explorer_lua)
        self.assertIn('battleAlternateButton', self.explorer_lua)
        self.assertIn('alternate_button', self.explorer_lua)

    def test_explorer_config_accepts_hex_values(self) -> None:
        self.assertIn('[0-9A-Fa-fxX]+', self.explorer_lua)

    def test_direction_order_can_be_seeded_reproducibly(self) -> None:
        self.assertIn('POKEMON_EXPLORER_DIRECTION_SEED', self.explorer_lua)
        self.assertIn('directionSeed % #directions', self.explorer_lua)
        self.assertIn('direction_seed\\t%d', self.explorer_lua)
        self.assertIn('menu_recovery_period\\t%d', self.explorer_lua)
        self.assertIn('menu_recovery_max_frames\\t%d', self.explorer_lua)
        self.assertIn('menu_recovery_timed_out\\t%s', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_STOP_ON_MENU_TIMEOUT', self.explorer_lua)
        self.assertIn('menu_recovery_timeout.tsv', self.explorer_lua)
        self.assertIn('menu_timeout_screen.png', self.explorer_lua)

    def test_menu_recovery_button_is_configurable(self) -> None:
        self.assertIn('POKEMON_EXPLORER_MENU_RECOVERY_BUTTON', self.explorer_lua)
        self.assertIn('decode(button)', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_MENU_RECOVERY_PERIOD', self.explorer_lua)
        self.assertIn('POKEMON_EXPLORER_MENU_RECOVERY_HOLD', self.explorer_lua)
        self.assertIn('math.min(0xFF', self.explorer_lua)

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
