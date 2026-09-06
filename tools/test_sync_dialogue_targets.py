#!/usr/bin/env python3
"""Tests du synchroniseur des cibles de dialogue Mesen."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from tools.dialogue_layout import DIALOGUE_LAYOUT
from tools.sync_dialogue_targets import synchronise


FIXTURE = """return {
    {
        source_offset = 0x123456,
        label = "fixture",
        required = true,
        payload_hex =
            "00",
    },
}
"""


class SyncDialogueTargetsTests(unittest.TestCase):
    def test_payload_follows_real_compiled_pages_and_is_idempotent(self) -> None:
        entries = {
            0x123456: SimpleNamespace(
                text="Bonjour Sacha ! Comment vas-tu ?",
                layout=DIALOGUE_LAYOUT,
            )
        }
        updated, changed = synchronise(FIXTURE, entries)
        self.assertEqual(changed, (0x123456,))
        self.assertIn(
            '"426f6e6a6f7572205361636861202120202020" ..',
            updated,
        )
        self.assertIn(
            '"436f6d6d656e74207661732d7475203f0d",',
            updated,
        )
        repeated, repeated_changed = synchronise(updated, entries)
        self.assertEqual(repeated, updated)
        self.assertEqual(repeated_changed, ())

    def test_missing_script_entry_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "0x123456"):
            synchronise(FIXTURE, {})


if __name__ == "__main__":
    unittest.main()
