#!/usr/bin/env python3
"""Static safety and alignment contracts for the Route 1 Mesen probe."""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROM_DIR / "tools"
TRACE_PATH = TOOLS_DIR / "mesen_fm3_route1_viridian_trace.lua"
BRIDGE_PATH = TOOLS_DIR / "mesen_fm3_route1_viridian_after_prototype.lua"
CONTINUATION_PATH = (
    TOOLS_DIR
    / "mesen_fm3_viridian_continuation_after_prototype.lua"
)
PARCEL_PROBE_PATH = (
    TOOLS_DIR / "mesen_fm3_parcel_route_probe_after_prototype.lua"
)
PROTOTYPE_PATH = TOOLS_DIR / "campaign" / "mesen_campaign_prototype.lua"
INPUT_PATH = (
    ROM_DIR
    / "build"
    / "campaign-reference"
    / "LeiDianHuangBiKaQiuChuanShuo-WIP1.inputs.bin"
)


class MesenFm3Route1ViridianTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.trace = TRACE_PATH.read_text(encoding="utf-8")
        cls.bridge = BRIDGE_PATH.read_text(encoding="utf-8")
        cls.continuation = CONTINUATION_PATH.read_text(encoding="utf-8")
        cls.parcel_probe = PARCEL_PROBE_PATH.read_text(encoding="utf-8")
        cls.prototype = PROTOTYPE_PATH.read_text(encoding="utf-8")

    def test_probe_is_controller_only(self) -> None:
        combined = "\n".join(
            (
                self.trace,
                self.bridge,
                self.continuation,
                self.prototype,
            )
        )
        forbidden = (
            r"\bemu\s*\.\s*write\s*\(",
            r"\bmemory\s*:\s*write\s*\(",
            r"\bemu\s*\.\s*(?:loadState|setState|rewind)\s*\(",
        )
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, combined))
        self.assertIn("emu.setInput", self.trace)
        self.assertIn("writes_to_game=0", self.trace)
        self.assertIn("mode=controller", self.prototype)

    def test_continuation_window_is_bounded_and_configurable(self) -> None:
        required_trace = (
            'rawget(_G, "POKEMON_FM3_ROUTE1_TRACE_FIRST")',
            'rawget(_G, "POKEMON_FM3_ROUTE1_TRACE_LAST")',
            'rawget(_G, "POKEMON_FM3_ROUTE1_CONTROL_START")',
            'rawget(_G, "POKEMON_FM3_ROUTE1_STOP_FRAME")',
            'rawget(_G, "POKEMON_FM3_ROUTE1_PASS_MARKER")',
            'rawget(_G, "POKEMON_FM3_ROUTE1_FINAL_LABEL")',
            "STOP_FRAME > 43160",
        )
        for snippet in required_trace:
            self.assertIn(snippet, self.trace)

        required_continuation = (
            "POKEMON_FM3_ROUTE1_TRACE_FIRST = 7100",
            "POKEMON_FM3_ROUTE1_TRACE_LAST = 43150",
            "POKEMON_FM3_ROUTE1_CONTROL_START = 6407",
            "POKEMON_FM3_ROUTE1_STOP_FRAME = 43159",
            '"POKEMON_FM3_VIRIDIAN_CONTINUATION_PASS"',
            '"full_reference_continuation_trace_end"',
            'loadModule("mesen_fm3_route1_viridian_after_prototype.lua")',
        )
        for snippet in required_continuation:
            self.assertIn(snippet, self.continuation)

        self.assertIn("if traceFrame or controlFrame then", self.trace)
        self.assertIn("and frame >= CONTROL_START", self.trace)

    def test_continuation_passively_traces_natural_pokedex_writes(
        self,
    ) -> None:
        required = (
            'kind = "caught"',
            "first = 0x609F",
            "last = 0x60B1",
            'kind = "seen"',
            "first = 0x60B3",
            "last = 0x60C5",
            "emu.callbackType.write",
            '"fm3_route1_viridian_pokedex_events.tsv"',
            "tableKeyCount(naturallySeen)",
            "tableKeyCount(naturallyCaught)",
            "newly_seen=%d newly_caught=%d",
        )
        for snippet in required:
            self.assertIn(snippet, self.trace)

    def test_alignment_dismisses_single_page_dialogues_by_controller(
        self,
    ) -> None:
        required = (
            "local function dialogueBoxVisible()",
            ") == 0xCB",
            ") == 0xCC",
            ") == 0xCD",
            "middle >= 8",
            "if viridianDialogueVisible then",
            "currentInput = phase <= 1 and 0x01 or 0",
            "and not viridianDialogueVisible",
            '"viridian_dialogue_dismiss_"',
            "alignment_dialogues_dismissed=%d",
        )
        for snippet in required:
            self.assertIn(snippet, self.trace)

    def test_campaign_dialogues_are_controller_dismissed(self) -> None:
        required = (
            "campaignDialogueDismissCount",
            "lastCampaignDialogueVisible",
            "and viridianDialogueVisible",
            '"campaign_dialogue_dismiss_"',
            "campaign_dialogues_dismissed=%d",
        )
        for snippet in required:
            self.assertIn(snippet, self.trace)

    def test_parcel_route_is_controller_only_and_opt_in(self) -> None:
        required = (
            'rawget(_G, "POKEMON_FM3_PARCEL_ROUTE") == true',
            "local PARCEL_SHOP_NAMETABLE = 0x389CD31A",
            "local PARCEL_ROUTE = {",
            "parcelRouteInput(parcelRouteTick)",
            '"parcel_route_start"',
            '"parcel_route_complete"',
            "parcel_route_done=%s",
        )
        for snippet in required:
            self.assertIn(snippet, self.trace)
        self.assertNotIn(
            "POKEMON_FM3_PARCEL_ROUTE = true",
            self.continuation,
        )
        self.assertIn(
            "POKEMON_FM3_PARCEL_ROUTE = true",
            self.parcel_probe,
        )

    def test_reference_controller_stream_is_frozen(self) -> None:
        payload = INPUT_PATH.read_bytes()
        self.assertEqual(len(payload), 43160)
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "ee79b39f3556a2acc316545614d77c910d"
            "c17b34e67ca7bbc17f803c13c46d9b",
        )

    def test_route_exit_alignment_uses_bounded_controller_dfs(self) -> None:
        required = (
            "local VIRIDIAN_CITY_NAMETABLE = 0x4E5109FA",
            "local VIRIDIAN_DFS_MAX_NODES = 128",
            "local VIRIDIAN_DFS_MAX_FRAMES = 3600",
            "local VIRIDIAN_DFS_ACTION_TIMEOUT = 64",
            "local VIRIDIAN_DFS_SETTLE_FRAMES = 12",
            "local VIRIDIAN_DFS_DIRECTIONS = {",
            '"explore",',
            '"return_seen"',
            '"viridian_dfs_seen_current_"',
            "signature ==\n                                    currentNode.signature",
            '"backtrack"',
            "table.remove(viridianDfsStack)",
            "viridianDfsVisited[signature]",
            "completed.opposite",
            "completed.opposite_name",
            '"viridian_dfs_node_%03d_%08X_%02X_%02X"',
            '"viridian_dfs_try_%03d_%s"',
            '"viridian_dfs_blocked_%03d_%s"',
            '"viridian_dfs_city_reached"',
            "viridianDfsFrames >= VIRIDIAN_DFS_MAX_FRAMES",
        )
        for snippet in required:
            self.assertIn(snippet, self.trace)
        direction_positions = [
            re.search(
                rf'(?m)^\s+name = "{name}",$',
                self.trace,
            ).start()
            for name in ("up", "right", "left", "down")
        ]
        self.assertEqual(direction_positions, sorted(direction_positions))

    def test_targeted_left_route_precedes_dfs_fallback(self) -> None:
        required = (
            "local VIRIDIAN_TARGET_MAX_STEPS = 16",
            'primary_left = "left"',
            'fallback_down = "down"',
            'fallback_left = "left"',
            'fallback_up = "up"',
            'up_to_warp = "up"',
            '"viridian_target_try_" .. stage',
            '"viridian_target_blocked_"',
            '"viridian_target_complete_"',
            'startViridianTargetStage(\n                "primary_left"',
            'if blockedStage == "primary_left" then',
            '"fallback_down"',
            '"fallback_left"',
            '"fallback_up"',
            '"up_to_warp"',
            "startViridianDfs(",
            "and viridianDfsStarted",
        )
        for snippet in required:
            self.assertIn(snippet, self.trace)

        target_start = self.trace.index(
            'startViridianTargetStage(\n                "primary_left"'
        )
        dfs_gate = self.trace.index("and viridianDfsStarted", target_start)
        self.assertLess(target_start, dfs_gate)

    def test_bridge_starts_from_natural_lab_exit(self) -> None:
        required = (
            "POKEMON_FM3_ROUTE1_BOOTSTRAP = true",
            "POKEMON_FM3_ROUTE1_STATE_DRIVEN = true",
            'loadModule("campaign/mesen_campaign_prototype.lua")',
            'loadModule("mesen_fm3_route1_viridian_trace.lua")',
        )
        for snippet in required:
            self.assertIn(snippet, self.bridge)
        self.assertNotIn(
            "POKEMON_FM3_ALLOW_MISSING_DIALOGUE_TARGETS",
            self.bridge,
        )
        self.assertNotIn(
            "POKEMON_FM3_EXTRA_DIALOGUE_TARGETS",
            self.bridge,
        )

    def test_post_battle_return_capture_waits_out_the_fade(self) -> None:
        self.assertIn(
            "ctx.rival_battle_return_capture_pending = false",
            self.prototype,
        )
        self.assertIn(
            "frame - ctx.battle_return_signature_since >= 120",
            self.prototype,
        )
        delayed_capture = self.prototype.index(
            'captureCheckpoint("12_rival_battle_returned")'
        )
        signature_update = self.prototype.index(
            "if signature ~= ctx.battle_return_signature then"
        )
        self.assertGreater(delayed_capture, signature_update)

    def test_battle_recovery_covers_the_whole_campaign_window(self) -> None:
        self.assertIn(
            "frame >= 6200 and frame < STOP_FRAME",
            self.trace,
        )
        self.assertNotIn("frame < 6760", self.trace)

    def test_transition_frame_keeps_dump_but_skips_black_screenshot(self) -> None:
        self.assertIn(
            "local function captureCheckpoint(label, arrow, "
            "includeScreenshot)",
            self.trace,
        )
        self.assertIn("if includeScreenshot ~= false then", self.trace)
        move_capture = re.search(
            r'"viridian_dfs_move_%s_%s_".*?'
            r'arrow,\s*false\s*\)',
            self.trace,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(move_capture)
        self.assertRegex(
            self.trace,
            r'captureCheckpoint\(\s*'
            r'"viridian_target_start",\s*arrow,\s*false\s*\)',
        )
        self.assertRegex(
            self.trace,
            r'captureCheckpoint\(\s*'
            r'"viridian_target_try_" \.\. stage,\s*arrow,\s*false\s*\)',
        )


if __name__ == "__main__":
    unittest.main()
