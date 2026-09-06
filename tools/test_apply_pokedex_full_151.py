#!/usr/bin/env python3
"""Regression tests for the controlled full-Pokédex source migration."""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path

from tools.apply_pokedex_full_151 import migrated_source
from tools.audit_pokedex_full_151 import KANTO_COUNT
from tools.dialogue_layout import POKEDEX_LAYOUT, wrap_pokedex_lines


ROOT = Path(__file__).resolve().parents[1]


def _records(data: bytes) -> dict[int, tuple[str, str]]:
    tree = ast.parse(data.decode("utf-8"))
    records: dict[int, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "p"
            and len(node.args) >= 2
        ):
            continue
        try:
            offset = ast.literal_eval(node.args[0])
            text = ast.literal_eval(node.args[1])
        except Exception:
            continue
        if not isinstance(offset, int) or not isinstance(text, str):
            continue
        layout = ""
        for keyword in node.keywords:
            if keyword.arg == "layout":
                layout = ast.literal_eval(keyword.value)
        records[offset] = (text, layout)
    return records


class ApplyPokedexFull151Tests(unittest.TestCase):
    def test_migration_targets_exactly_151_accessible_descriptions(self) -> None:
        updated, summary = migrated_source()
        self.assertEqual(summary["accessible_descriptions"], KANTO_COUNT)
        records = _records(updated)
        anchors = {
            0x030898,
            0x036950,
            0x036978,
            0x03217A,
            0x03789A,
        }
        for offset in anchors:
            with self.subTest(offset=f"0x{offset:06X}"):
                text, layout = records[offset]
                self.assertEqual(layout, POKEDEX_LAYOUT)
                self.assertLessEqual(len(wrap_pokedex_lines(text)), 4)

    def test_migration_is_idempotent(self) -> None:
        updated, _ = migrated_source()
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "script.py"
            script.write_bytes(updated)
            second, summary = migrated_source(script)
        self.assertEqual(second, updated)
        self.assertEqual(summary["rewritten_calls"], 0)


if __name__ == "__main__":
    unittest.main()
