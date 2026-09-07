#!/usr/bin/env python3
"""Regression tests for the archived defaults of the PowerShell CHR wrapper."""

from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path


ROM_DIR = Path(__file__).resolve().parent.parent
WRAPPER = ROM_DIR / "tools" / "build-chr-modular.ps1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def powershell_string(source: str, variable: str) -> str:
    match = re.search(
        rf"\${re.escape(variable)}\s*=\s*(?:\(\s*)?'([^']+)'",
        source,
    )
    if match is None:
        raise AssertionError(f"Missing PowerShell variable: {variable}")
    return match.group(1)


class ChrDefaultBindingTests(unittest.TestCase):
    def test_archived_wrapper_defaults_form_one_hash_bound_snapshot(self) -> None:
        source = WRAPPER.read_text(encoding="utf-8")
        snapshot_id = powershell_string(source, "DefaultSnapshotId")
        expected_hash = powershell_string(
            source,
            "DefaultSnapshotSha256",
        )
        relative_rom = powershell_string(
            source,
            "DefaultSnapshotRomPath",
        ).replace("\\", "/")

        rom = ROM_DIR / relative_rom
        manifest = (
            ROM_DIR
            / "graphics"
            / "chr_modular"
            / f"manifest-{snapshot_id}.json"
        )
        pack_lock = (
            ROM_DIR
            / "graphics"
            / "chr_modular"
            / f"pack-{snapshot_id}"
            / "pack.lock.json"
        )
        self.assertTrue(rom.is_file())
        self.assertTrue(manifest.is_file())
        self.assertTrue(pack_lock.is_file())

        manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
        lock_data = json.loads(pack_lock.read_text(encoding="utf-8"))
        self.assertEqual(sha256(rom), expected_hash)
        self.assertEqual(manifest_data["source_sha256"], expected_hash)
        self.assertEqual(lock_data["source_sha256"], expected_hash)
        self.assertEqual(lock_data["manifest_sha256"], sha256(manifest))

    def test_wrapper_calls_both_preflight_hash_guards(self) -> None:
        source = WRAPPER.read_text(encoding="utf-8")
        self.assertRegex(
            source,
            r"Assert-ChrSnapshotBinding\s+`\s*\n\s*-Rom",
        )
        self.assertRegex(
            source,
            r"Assert-ChrPackBinding\s+`\s*\n\s*-Rom",
        )


if __name__ == "__main__":
    unittest.main()
